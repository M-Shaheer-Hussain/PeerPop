import time
import uuid

import requests
from app.Auth.auth import get_current_user
from app.core.pairing import (
    active_outbound_sessions,
    active_pairing_sessions,
    generate_nonce,
    generate_pairing_code,
    sign_message,
    verify_signature,
)
from app.database.database import get_db
from app.models.models import Device, TrustedDevice, User
from app.schemas.schemas import (
    InitiatePairing,
    PairingRequest,
    PairingResponse,
    PairingVerify,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/pairing", tags=["Pairing"])

# ==========================================
# DEVICE B (RECEIVER) ENDPOINTS
# ==========================================

@router.post("/request", response_model=PairingResponse)
def receive_pairing_request(req: PairingRequest, db: Session = Depends(get_db)):
    # 1. Identity Pinning Check
    existing = db.query(TrustedDevice).filter(TrustedDevice.remote_device_id == req.device_id).first()
    if existing:
        if existing.remote_public_key != req.public_key:
            raise HTTPException(status_code=400, detail="Identity mismatch! Public key changed.")
        if existing.status == "TRUSTED":
            raise HTTPException(status_code=400, detail="Device is already trusted.")

    # 2. Generate Challenge
    session_id = str(uuid.uuid4())
    nonce = generate_nonce()
    code = generate_pairing_code()

    # 3. Store Session in Memory
    active_pairing_sessions[session_id] = {
        "device_id": req.device_id,
        "device_name": req.device_name,
        "public_key": req.public_key,
        "nonce": nonce,
        "code": code,
        "status": "AWAITING_SIGNATURE",
        "created_at": time.time()
    }
    return {"session_id": session_id, "nonce": nonce, "code": code}

@router.post("/verify")
def verify_pairing_signature(req: PairingVerify):
    session = active_pairing_sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session expired or invalid")

    is_valid = verify_signature(session["public_key"], session["nonce"], req.signature)
    if not is_valid:
        del active_pairing_sessions[req.session_id]
        raise HTTPException(status_code=401, detail="Cryptographic proof failed")

    session["status"] = "PENDING_HUMAN_APPROVAL"
    return {"message": "Signature valid. Waiting for human approval."}

@router.get("/pending")
def check_pending_requests():
    """Frontend polls this to see if someone wants to pair."""
    # Cleanup expired sessions (>60s old)
    current_time = time.time()
    expired = [sid for sid, data in active_pairing_sessions.items() if current_time - data["created_at"] > 60]
    for sid in expired:
        del active_pairing_sessions[sid]

    return [
        {"session_id": sid, "device_name": data["device_name"], "code": data["code"]} 
        for sid, data in active_pairing_sessions.items() 
        if data["status"] == "PENDING_HUMAN_APPROVAL"
    ]

@router.post("/approve/{session_id}")
def human_approve_pairing(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """User clicked 'Accept' on Device B."""
    session = active_pairing_sessions.get(session_id)
    if not session or session["status"] != "PENDING_HUMAN_APPROVAL":
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    # Establish persistent trust
    new_trust = TrustedDevice(
        owner_id=current_user.id,
        remote_device_id=session["device_id"],
        remote_public_key=session["public_key"],
        device_name=session["device_name"],
        status="TRUSTED"
    )
    db.add(new_trust)
    db.commit()
    
    session["status"] = "TRUSTED"  # Keep in memory briefly so Device A can see it was approved
    return {"message": "Trust established"}

@router.get("/status/{session_id}")
def check_session_status(session_id: str):
    """Device A polls this to see if Device B's human clicked Accept."""
    session = active_pairing_sessions.get(session_id)
    if session:
        return {"status": session["status"]}
    return {"status": "REJECTED_OR_EXPIRED"}

# ==========================================
# DEVICE A (INITIATOR) ENDPOINTS
# ==========================================

@router.post("/initiate")
def initiate_pairing(target: InitiatePairing, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    local_device = db.query(Device).filter(Device.is_local == True).first()
    if not local_device:
        raise HTTPException(status_code=500, detail="Local device identity not initialized.")

    target_url = f"http://{target.target_ip}:{target.target_port}/pairing"

    try:
        # 1. Ask B for a challenge
        payload = {
            "device_id": str(local_device.id),
            "device_name": str(local_device.device_name),
            "public_key": str(local_device.public_key)
        }
        res = requests.post(f"{target_url}/request", json=payload, timeout=5)
        
        # NEW: Catch Target Rejections gracefully instead of crashing
        if not res.ok:
            error_detail = res.json().get("detail", "Target rejected request")
            raise HTTPException(status_code=res.status_code, detail=error_detail)
            
        data = res.json()

        # 2. Cryptographically sign the challenge
        signature = sign_message(data["nonce"])

        # 3. Send signature back to B
        verify_payload = {"session_id": data["session_id"], "signature": signature}
        verify_res = requests.post(f"{target_url}/verify", json=verify_payload, timeout=5)
        
        if not verify_res.ok:
            error_detail = verify_res.json().get("detail", "Signature verification failed")
            raise HTTPException(status_code=verify_res.status_code, detail=error_detail)

        # 4. Track this outbound session
        active_outbound_sessions[data["session_id"]] = {
            "target_ip": target.target_ip,
            "target_port": target.target_port,
            "target_device_id": target.target_device_id,
            "target_device_name": target.target_device_name,
            "target_public_key": target.target_public_key,
            "owner_id": current_user.id
        }

        return {
            "message": "Waiting for remote approval",
            "session_id": data["session_id"],
            "code": data["code"]
        }

    # Catch actual network timeouts (e.g. device is turned off)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail="Target device is unreachable.")



@router.get("/status/outbound/{session_id}")
def check_outbound_status(session_id: str, db: Session = Depends(get_db)):
    """Device A uses this to ask Device B if the human clicked Accept."""
    outbound = active_outbound_sessions.get(session_id)
    if not outbound:
        return {"status": "REJECTED_OR_EXPIRED"}
    
    target_url = f"http://{outbound['target_ip']}:{outbound['target_port']}/pairing"
    
    try:
        # Ask Device B for the status
        res = requests.get(f"{target_url}/status/{session_id}", timeout=5)
        remote_status = res.json().get("status", "REJECTED_OR_EXPIRED")
        
        if remote_status == "TRUSTED":
            # Device B accepted! Save Device B's identity to Device A's database
            existing = db.query(TrustedDevice).filter(TrustedDevice.remote_device_id == outbound["target_device_id"]).first()
            if not existing:
                new_trust = TrustedDevice(
                    owner_id=outbound["owner_id"],
                    remote_device_id=outbound["target_device_id"],
                    remote_public_key=outbound["target_public_key"],
                    device_name=outbound["target_device_name"],
                    status="TRUSTED"
                )
                db.add(new_trust)
                db.commit()
                
            del active_outbound_sessions[session_id]
            return {"status": "TRUSTED"}
            
        elif remote_status == "REJECTED_OR_EXPIRED":
            del active_outbound_sessions[session_id]
            
        return {"status": remote_status}
        
    except requests.exceptions.RequestException:
        # Keep waiting if there is a minor network hiccup
        return {"status": "PENDING_HUMAN_APPROVAL"}