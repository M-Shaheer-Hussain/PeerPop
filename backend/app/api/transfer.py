import os
import time

from app.Auth.auth import get_current_user
from app.core.discovery import nearby_devices
from app.core.transfer import (
    UPLOADS_STAGING_DIR,
    new_transfer_id,
    outbound_transfer_status,
    pending_incoming_transfers,
    safe_filename,
)
from app.models.models import User
from app.p2p.handler import send_file_over_p2p
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

router = APIRouter(prefix="/transfer", tags=["Transfer"])

# ==========================================
# SENDER (DEVICE A) ENDPOINTS
# ==========================================

@router.post("/send")
async def send_file(
    background_tasks: BackgroundTasks,
    device_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),  # noqa: B008
):
    """Phase 7: File selection + transfer request kickoff.

    Stages the uploaded file, looks up the target peer on the local network
    radar, and starts the request/approval/streaming sequence in the
    background so the caller isn't blocked waiting on human approval.
    """
    peer = nearby_devices.get(device_id)
    if not peer or peer.get("status") != "Available":
        raise HTTPException(status_code=404, detail="Peer not found or currently offline.")

    transfer_id = new_transfer_id()
    filename = safe_filename(file.filename or "unnamed_file")
    staged_path = os.path.join(UPLOADS_STAGING_DIR, f"{transfer_id}_{filename}")

    contents = await file.read()
    with open(staged_path, "wb") as f:
        f.write(contents)
    size = len(contents)

    outbound_transfer_status[transfer_id] = {
        "status": "PENDING_APPROVAL",
        "filename": filename,
        "size": size,
        "target_device_id": device_id,
        "target_device_name": peer.get("device_name", "Unknown Device"),
        "file_path": staged_path,
        "error": None,
        "created_at": time.time(),
    }

    transfer_payload = {
        "transfer_id": transfer_id,
        "file_path": staged_path,
        "filename": filename,
        "size": size,
    }

    background_tasks.add_task(
        send_file_over_p2p,
        peer["ip_address"],
        peer.get("p2p_port", 8765),
        device_id,
        transfer_payload,
    )

    return {"transfer_id": transfer_id, "status": "PENDING_APPROVAL"}


@router.get("/status/{transfer_id}")
def get_outbound_status(transfer_id: str):
    """Device A polls this to track approval + streaming progress."""
    status = outbound_transfer_status.get(transfer_id)
    if not status:
        return {"status": "UNKNOWN"}
    return {
        "status": status["status"],
        "filename": status["filename"],
        "size": status["size"],
        "error": status.get("error"),
    }


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