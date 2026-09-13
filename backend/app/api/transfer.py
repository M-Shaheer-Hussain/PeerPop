import asyncio
import json
import time

from app.Auth.auth import get_current_user
from app.core.discovery import nearby_devices
from app.core.transfer import pending_incoming_transfers
from app.models.models import User
from app.p2p.handler import (
    active_secure_connections,
    connect_to_peer,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)

router = APIRouter(prefix="/transfer", tags=["Transfer"])

# ==========================================
# SENDER (DEVICE A) ENDPOINTS
# ==========================================

@router.websocket("/ws/stream/{target_device_id}")
async def direct_stream_passthrough(websocket: WebSocket, target_device_id: str):
    """
    Direct WebSocket Streaming (Bypass Staging):
    Pipes file chunks directly from the sender's browser to the remote peer
    over the secure Ed25519 P2P TLS tunnel, without saving to disk.
    """
    await websocket.accept()

    peer = nearby_devices.get(target_device_id)
    if not peer or peer.get("status") != "Available":
        await websocket.close(code=1008, reason="Peer not found or offline.")
        return

    # 1. Establish the secure P2P tunnel first (without disk payload)
    success = await connect_to_peer(
        target_ip=peer["ip_address"],
        target_p2p_port=peer.get("p2p_port", 8765),
        target_device_id=target_device_id
    )
    
    if not success:
        await websocket.close(code=1011, reason="Failed to connect to peer.")
        return

    peer_ws = active_secure_connections.get(target_device_id)

    # Ensure we have a valid connection object to satisfy Pylance
    if not peer_ws:
        await websocket.close(code=1011, reason="Secure connection lost or not established.")
        return

    try:
        # 2. Wait for the browser to send the initial file metadata (JSON)
        metadata = await websocket.receive_json()
        transfer_id = metadata.get("transfer_id")
        
        # 3. Request transfer approval from the remote peer
        request_frame = f"TRANSFER_REQUEST:{json.dumps(metadata)}"
        await peer_ws.send(request_frame)
        
        # 4. Wait for the remote human to Accept or Reject
        raw_reply = await asyncio.wait_for(peer_ws.recv(), timeout=120.0)
        reply = raw_reply.decode("utf-8") if isinstance(raw_reply, bytes) else raw_reply
            
        if not reply.startswith("TRANSFER_ACCEPT:"):
            await websocket.send_json({"status": "REJECTED"})
            await websocket.close(code=1008, reason="Transfer rejected")
            return
            
        # 5. Signal the browser to start piping data, and tell peer to prep file
        await websocket.send_json({"status": "ACCEPTED"})
        await peer_ws.send(f"TRANSFER_START:{transfer_id}")

        # 6. The Passthrough Loop: Browser -> Local Backend -> Remote Peer
        while True:
            chunk = await websocket.receive_bytes()
            if not chunk:
                break  # Frontend sends an empty byte frame to signal EOF
            await peer_ws.send(chunk)
            
        # 7. Complete the transfer
        await peer_ws.send(f"TRANSFER_END:{transfer_id}")
        await websocket.send_json({"status": "COMPLETED"})
        
    except WebSocketDisconnect:
        print("[PASSTHROUGH] Browser disconnected mid-transfer.")
    except Exception as e:  # noqa: BLE001
        print(f"[PASSTHROUGH] Streaming error: {e}")
        await websocket.send_json({"status": "FAILED", "error": str(e)})


# ==========================================
# RECEIVER (DEVICE B) ENDPOINTS
# ==========================================

@router.get("/incoming")
def check_incoming_transfers():
    """Frontend polls this to see if someone wants to send a file."""
    current_time = time.time()
    expired = [
        tid for tid, data in pending_incoming_transfers.items()
        if data["status"] == "PENDING" and current_time - data["created_at"] > 120
    ]
    for tid in expired:
        del pending_incoming_transfers[tid]

    return [
        {
            "transfer_id": tid,
            "filename": data["filename"],
            "size": data["size"],
            "sender_device_name": data["sender_device_name"],
        }
        for tid, data in pending_incoming_transfers.items()
        if data["status"] == "PENDING"
    ]


@router.post("/approve/{transfer_id}")
async def approve_transfer(transfer_id: str, current_user: User = Depends(get_current_user)):  # noqa: B008
    """User clicked 'Accept' on the incoming file transfer request."""
    record = pending_incoming_transfers.get(transfer_id)
    if not record or record["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Invalid or expired transfer request")

    websocket = record["websocket"]
    await websocket.send(f"TRANSFER_ACCEPT:{transfer_id}")
    record["status"] = "ACCEPTED"

    return {"message": "Transfer accepted. Receiving will begin shortly."}


@router.post("/reject/{transfer_id}")
async def reject_transfer(transfer_id: str, current_user: User = Depends(get_current_user)):  # noqa: B008
    """User clicked 'Reject' on the incoming file transfer request."""
    record = pending_incoming_transfers.get(transfer_id)
    if not record or record["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Invalid or expired transfer request")

    websocket = record["websocket"]
    await websocket.send(f"TRANSFER_REJECT:{transfer_id}")
    record["status"] = "REJECTED"
    del pending_incoming_transfers[transfer_id]

    return {"message": "Transfer rejected."}