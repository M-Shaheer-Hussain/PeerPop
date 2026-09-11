import asyncio
import json
import logging
import os
import ssl

import websockets
from app.core.pairing import generate_nonce, sign_message, verify_signature
from app.core.transfer import (
    CHUNK_SIZE,
    DOWNLOADS_DIR,
    active_incoming_files,
    outbound_transfer_status,
    pending_incoming_transfers,
    safe_filename,
)
from app.database.database import localsession
from app.models.models import Device, TrustedDevice
from cryptography import x509
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)

# Active secure connection registry: { remote_device_id: websocket_connection }
active_secure_connections = {}

DOMAIN_SEPARATOR = "PEERPOP_CONNECTION_AUTH_V1"

# ==========================================
# SERVER-SIDE (Device B handling incoming A)
# ==========================================
async def handle_incoming_p2p(websocket):
    """
    Accepts an incoming WSS connection, performs application-layer 
    challenge-response mutual authentication, and upgrades to SECURE.
    """
    remote_addr = websocket.remote_address
    logger.info(f"[P2P SERVER] Connection received from {remote_addr}. State: TLS_ESTABLISHED")
    
    db = localsession()
    try:
        # 1. Issue a challenge nonce
        nonce = generate_nonce()
        challenge_payload = f"{DOMAIN_SEPARATOR}|{nonce}"
        
        await websocket.send(f"CHALLENGE:{challenge_payload}")
        
        # 2. Await client response (expects: DEVICE_ID:SIGNATURE)
        raw_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        response = raw_response.decode('utf-8') if isinstance(raw_response, bytes) else raw_response
        
        if not response.startswith("AUTH:"):
            logger.warning("[P2P SERVER] Malformed authentication frame. Closing connection.")
            await websocket.close(code=4001, reason="Malformed auth frame")
            return
            
        _, auth_data = response.split(":", 1)
        if "|" not in auth_data:
            await websocket.close(code=4002, reason="Invalid auth payload format")
            return
            
        remote_device_id, signature_hex = auth_data.split("|", 1)
        
        # 3. Verify that the connecting device is in our trusted_devices table
        trusted_record = db.query(TrustedDevice).filter(
            TrustedDevice.remote_device_id == remote_device_id,
            TrustedDevice.status == "TRUSTED"
        ).first()
        
        if not trusted_record:
            logger.warning(f"[P2P SERVER] Unknown or untrusted device ID: {remote_device_id}")
            await websocket.close(code=4003, reason="Device not trusted")
            return
            
        # 4. Cryptographically verify the signature against the pinned public key
        is_valid = verify_signature(
            public_key_pem=trusted_record.remote_public_key,
            message=challenge_payload,
            signature_hex=signature_hex
        )
        
        if not is_valid:
            logger.warning(f"[P2P SERVER] Cryptographic authentication failed for {remote_device_id}")
            await websocket.close(code=4004, reason="Authentication failed")
            return
            
        # 5. AUTHENTICATED & SECURE!
        logger.info(f"[P2P SERVER] ✅ Secure session established with {trusted_record.device_name} ({remote_device_id})")
        active_secure_connections[remote_device_id] = websocket
        
        await websocket.send("STATUS:SECURE")
        
        # PHASE 7: tracks which transfer_id is currently streaming binary
        # chunks into a file on this particular connection.
        current_receiving_transfer_id = None

        # Keep connection alive and process incoming secure messages (e.g. PING/PONG)
        async for message in websocket:
            if message == "PING":
                await websocket.send("PONG")

            elif isinstance(message, str) and message.startswith("TRANSFER_REQUEST:"):
                current_receiving_transfer_id = await _handle_transfer_request(
                    remote_device_id, trusted_record.device_name, websocket, message
                )

            elif isinstance(message, str) and message.startswith("TRANSFER_START:"):
                _, transfer_id = message.split(":", 1)
                _open_incoming_file(transfer_id)
                current_receiving_transfer_id = transfer_id

            elif isinstance(message, (bytes, bytearray)):
                _write_incoming_chunk(current_receiving_transfer_id, message)

            elif isinstance(message, str) and message.startswith("TRANSFER_END:"):
                _, transfer_id = message.split(":", 1)
                _close_incoming_file(transfer_id)
                current_receiving_transfer_id = None

            else:
                logger.info(f"[P2P SECURE MSG from {remote_device_id}]: {message}")
                
    except asyncio.TimeoutError:
        logger.warning("[P2P SERVER] Authentication handshake timed out.")
        await websocket.close(code=4005, reason="Handshake timeout")
    except websockets.exceptions.ConnectionClosed:
        logger.info("[P2P SERVER] Peer disconnected cleanly.")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[P2P SERVER] Error handling connection: {e}")
    finally:
        db.close()
        # Cleanup registry on disconnect
        for d_id, ws in list(active_secure_connections.items()):
            if ws == websocket:
                del active_secure_connections[d_id]
                logger.info(f"[P2P SERVER] Removed {d_id} from active secure connections.")


# ==========================================
# PHASE 7 — RECEIVER-SIDE TRANSFER HELPERS
# ==========================================
async def _handle_transfer_request(remote_device_id: str, sender_device_name: str, websocket, message: str):
    """Parses an incoming TRANSFER_REQUEST frame and stores it for human approval.

    Returns None (does not touch current_receiving_transfer_id) — approval
    happens asynchronously via the REST /transfer/approve or /transfer/reject
    endpoints, which push the ACCEPT/REJECT frame back over this same socket.
    """
    import time

    _, payload_json = message.split(":", 1)
    try:
        payload = json.loads(payload_json)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[P2P SERVER] Malformed TRANSFER_REQUEST payload. Ignoring.")
        return None  # noqa: RET501

    transfer_id = payload.get("transfer_id")
    filename = safe_filename(payload.get("filename", ""))
    size = int(payload.get("size", 0))

    if not transfer_id:
        return None  # noqa: RET501

    pending_incoming_transfers[transfer_id] = {
        "transfer_id": transfer_id,
        "filename": filename,
        "size": size,
        "sender_device_id": remote_device_id,
        "sender_device_name": sender_device_name,
        "status": "PENDING",
        "websocket": websocket,
        "created_at": time.time(),
    }
    logger.info(f"[P2P SERVER] Incoming transfer request {transfer_id} ({filename}, {size} bytes) from {sender_device_name}")
    return None  # noqa: RET501


def _open_incoming_file(transfer_id: str):
    record = pending_incoming_transfers.get(transfer_id)
    if not record:
        logger.warning(f"[P2P SERVER] TRANSFER_START for unknown transfer {transfer_id}")
        return

    dest_path = os.path.join(DOWNLOADS_DIR, record["filename"])
    handle = open(dest_path, "wb")  # noqa: SIM115
    active_incoming_files[transfer_id] = {
        "handle": handle,
        "path": dest_path,
        "received": 0,
        "size": record["size"],
    }
    record["status"] = "RECEIVING"
    logger.info(f"[P2P SERVER] Started receiving {record['filename']} -> {dest_path}")


def _write_incoming_chunk(transfer_id: str | None, chunk: bytes | bytearray):
    if not transfer_id:
        logger.warning("[P2P SERVER] Received binary chunk with no active transfer context. Dropping.")
        return

    entry = active_incoming_files.get(transfer_id)
    if not entry:
        logger.warning(f"[P2P SERVER] Received binary chunk for unopened transfer {transfer_id}. Dropping.")
        return

    entry["handle"].write(chunk)
    entry["received"] += len(chunk)


def _close_incoming_file(transfer_id: str):
    entry = active_incoming_files.pop(transfer_id, None)
    if entry:
        entry["handle"].close()

    record = pending_incoming_transfers.get(transfer_id)
    if record:
        record["status"] = "COMPLETED"
        logger.info(f"[P2P SERVER] ✅ Transfer {transfer_id} complete: {record['filename']}")


# ==========================================
# CLIENT-SIDE (Device A connecting to B)
# ==========================================
async def connect_to_peer(target_ip: str, target_p2p_port: int, target_device_id: str, transfer_payload: dict | None = None):
    """
    Connects to a peer via WSS, executes certificate pinning validation, 
    answers the challenge, and establishes a SECURE tunnel.

    PHASE 7: if `transfer_payload` is provided, the connection performs a
    file-transfer request/approval/streaming sequence instead of the original
    PING test. When it is None (the default) behavior is completely
    unchanged from Phase 6.
    """
    db = localsession()
    try:
        # Check if the target is in our local trusted devices database
        trusted_record = db.query(TrustedDevice).filter(
            TrustedDevice.remote_device_id == target_device_id,
            TrustedDevice.status == "TRUSTED"
        ).first()
        
        if not trusted_record:
            logger.error(f"[P2P CLIENT] Cannot connect: Device {target_device_id} is not trusted.")
            return False
            
        local_device = db.query(Device).filter(Device.is_local == True).first()
        if not local_device:
            logger.error("[P2P CLIENT] Local device identity not initialized.")
            return False

        # Configure client SSL context (CERT_NONE required for self-signed, manual pinning overrides it)
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        uri = f"wss://{target_ip}:{target_p2p_port}"
        logger.info(f"[P2P CLIENT] Connecting to secure peer at {uri}...")

        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            # --- STEP A: CERTIFICATE PINNING VALIDATION ---
            ssl_obj = websocket.transport.get_extra_info('ssl_object')
            der_cert = ssl_obj.getpeercert(binary_form=True)
            
            if not der_cert:
                logger.error("[P2P CLIENT] ❌ MITM Alert: Peer presented no certificate.")
                return False

            parsed_cert = x509.load_der_x509_certificate(der_cert)
            extracted_pub_key = parsed_cert.public_key()
            
            extracted_pub_key_bytes = extracted_pub_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            # Load expected raw bytes from the trusted record's stored PEM public key
            expected_public_key = serialization.load_pem_public_key(
                trusted_record.remote_public_key.encode('utf-8')
            )
            expected_pub_key_bytes = expected_public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            if extracted_pub_key_bytes != expected_pub_key_bytes:
                logger.error("[P2P CLIENT] 🚨 CRITICAL: Identity mismatch! Pinned public key does not match TLS certificate.")
                return False

            logger.info("[P2P CLIENT] ✅ TLS Identity mathematically verified via certificate pinning.")

            # --- STEP B: APPLICATION-LAYER CHALLENGE RESPONSE ---
            # Wait for server challenge
            raw_msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            msg = raw_msg.decode('utf-8') if isinstance(raw_msg, bytes) else raw_msg
            
            if not msg.startswith("CHALLENGE:"):
                logger.error("[P2P CLIENT] Expected server challenge, received invalid frame.")
                return False

            _, challenge_payload = msg.split(":", 1)
            
            # Sign the challenge nonce using our local persistent private key
            signature_hex = sign_message(challenge_payload)
            
            auth_frame = f"AUTH:{str(local_device.id)}|{signature_hex}"  # noqa: RUF010
            await websocket.send(auth_frame)

            # Await status response
            raw_status = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            status_msg = raw_status.decode('utf-8') if isinstance(raw_status, bytes) else raw_status
            
            if status_msg == "STATUS:SECURE":
                logger.info(f"[P2P CLIENT] 🔒 Secure session fully established with {trusted_record.device_name}!")
                active_secure_connections[target_device_id] = websocket

                # PHASE 7: hand off to the file-transfer flow if requested.
                if transfer_payload is not None:
                    return await _perform_file_transfer(websocket, transfer_payload)

                # Original Phase 6 behavior: send a test PING to prove the channel works
                await websocket.send("PING")
                pong_reply = await websocket.recv()
                logger.info(f"[P2P CLIENT] Ping test response: {pong_reply}")
                return True
            else:
                logger.error(f"[P2P CLIENT] Handshake rejected by server: {status_msg}")
                return False

    except Exception as e:  # noqa: BLE001
        logger.error(f"[P2P CLIENT] Connection error to {target_ip}: {e}")
        if transfer_payload is not None:
            status_entry = outbound_transfer_status.get(transfer_payload["transfer_id"])
            if status_entry:
                status_entry["status"] = "FAILED"
                status_entry["error"] = str(e)
        return False
    finally:
        db.close()


# ==========================================
# PHASE 7 — SENDER-SIDE TRANSFER FLOW
# ==========================================
async def _perform_file_transfer(websocket, transfer_payload: dict) -> bool:
    """Runs the TRANSFER_REQUEST -> approval -> streaming -> TRANSFER_END
    sequence over an already-authenticated secure websocket connection.
    """
    transfer_id = transfer_payload["transfer_id"]
    file_path = transfer_payload["file_path"]
    filename = transfer_payload["filename"]
    size = transfer_payload["size"]

    status_entry = outbound_transfer_status.setdefault(transfer_id, {})
    status_entry["status"] = "PENDING_APPROVAL"

    request_frame = "TRANSFER_REQUEST:" + json.dumps({
        "transfer_id": transfer_id,
        "filename": filename,
        "size": size,
    })
    await websocket.send(request_frame)

    try:
        # Give the human on the other end time to notice and click Accept/Reject.
        raw_reply = await asyncio.wait_for(websocket.recv(), timeout=120.0)
    except asyncio.TimeoutError:
        logger.warning(f"[P2P CLIENT] Transfer {transfer_id} timed out awaiting receiver approval.")
        status_entry["status"] = "FAILED"
        status_entry["error"] = "Receiver did not respond in time."
        return False

    reply = raw_reply.decode("utf-8") if isinstance(raw_reply, bytes) else raw_reply

    if reply.startswith("TRANSFER_REJECT:"):
        logger.info(f"[P2P CLIENT] Transfer {transfer_id} was rejected by the receiver.")
        status_entry["status"] = "REJECTED"
        return False

    if not reply.startswith("TRANSFER_ACCEPT:"):
        logger.warning(f"[P2P CLIENT] Unexpected reply to transfer request: {reply}")
        status_entry["status"] = "FAILED"
        status_entry["error"] = "Unexpected response from receiver."
        return False

    logger.info(f"[P2P CLIENT] ✅ Transfer {transfer_id} accepted. Streaming {filename} ({size} bytes)...")
    status_entry["status"] = "SENDING"

    try:
        await websocket.send(f"TRANSFER_START:{transfer_id}")
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                await websocket.send(chunk)
        await websocket.send(f"TRANSFER_END:{transfer_id}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[P2P CLIENT] Error while streaming transfer {transfer_id}: {e}")
        status_entry["status"] = "FAILED"
        status_entry["error"] = str(e)
        return False

    status_entry["status"] = "COMPLETED"
    logger.info(f"[P2P CLIENT] ✅ Transfer {transfer_id} completed successfully.")
    return True


async def send_file_over_p2p(target_ip: str, target_p2p_port: int, target_device_id: str, transfer_payload: dict) -> bool:
    """Public entry point used by the /transfer REST endpoints to kick off
    a full connect + request + stream cycle for a single file."""
    return await connect_to_peer(target_ip, target_p2p_port, target_device_id, transfer_payload=transfer_payload)