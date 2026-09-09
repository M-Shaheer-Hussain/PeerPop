"""
Phase 7 — Basic file transfer state & helpers.

This module is purely additive: it introduces the in-memory registries and
small utility functions needed to support file-selection -> transfer request
-> receiver approval -> streaming -> save-to-disk, without touching any of
the existing pairing / discovery / auth code paths.
"""
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

# Where incoming files are written to on this device.
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Where outbound files are temporarily staged after upload, before being
# streamed out over the secure P2P channel.
UPLOADS_STAGING_DIR = os.path.join(os.getcwd(), "uploads_staging")
os.makedirs(UPLOADS_STAGING_DIR, exist_ok=True)

CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks

# ------------------------------------------------------------------
# Registries (all in-memory, mirroring the style of app.core.pairing)
# ------------------------------------------------------------------

# Receiver side: transfer_id -> {
#   "transfer_id", "filename", "size", "sender_device_id",
#   "sender_device_name", "status", "websocket", "created_at"
# }
# status: PENDING -> ACCEPTED/REJECTED -> RECEIVING -> COMPLETED/FAILED
pending_incoming_transfers = {}

# Receiver side: transfer_id -> {"handle": file_obj, "path": str, "received": int, "size": int}
# Populated when the sender signals TRANSFER_START, cleared on TRANSFER_END.
active_incoming_files = {}

# Sender side: transfer_id -> {
#   "status", "filename", "size", "target_device_id", "target_device_name",
#   "file_path", "error", "created_at"
# }
# status: PENDING_APPROVAL -> ACCEPTED/REJECTED -> SENDING -> COMPLETED/FAILED
outbound_transfer_status = {}


def new_transfer_id() -> str:
    return str(uuid.uuid4())


def safe_filename(name: str) -> str:
    """Strips any directory components to prevent path traversal."""
    cleaned = os.path.basename(name or "").strip()
    cleaned = cleaned.replace("..", "_")
    return cleaned or f"received_file_{int(time.time())}"


def cleanup_stale_transfers(max_age_seconds: int = 300):
    """Drops transfer bookkeeping entries that never got resolved."""
    now = time.time()

    stale_incoming = [
        tid for tid, data in pending_incoming_transfers.items()
        if data["status"] == "PENDING" and now - data["created_at"] > max_age_seconds
    ]
    for tid in stale_incoming:
        del pending_incoming_transfers[tid]

    stale_outbound = [
        tid for tid, data in outbound_transfer_status.items()
        if data["status"] in ("COMPLETED", "REJECTED", "FAILED") and now - data["created_at"] > max_age_seconds
    ]
    for tid in stale_outbound:
        del outbound_transfer_status[tid]