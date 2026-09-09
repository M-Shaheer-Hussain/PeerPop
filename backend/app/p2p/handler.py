import asyncio
import logging
import ssl

import websockets
from app.core.pairing import generate_nonce, sign_message, verify_signature
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
        
        # Keep connection alive and process incoming secure messages (e.g. PING/PONG)
        async for message in websocket:
            if message == "PING":
                await websocket.send("PONG")
            else:
                logger.info(f"[P2P SECURE MSG from {remote_device_id}]: {message}")
                
    except asyncio.TimeoutError:
        logger.warning("[P2P SERVER] Authentication handshake timed out.")
        await websocket.close(code=4005, reason="Handshake timeout")
    except websockets.exceptions.ConnectionClosed:
        logger.info("[P2P SERVER] Peer disconnected cleanly.")
    except Exception as e:
        logger.error(f"[P2P SERVER] Error handling connection: {e}")
    finally:
        db.close()
        # Cleanup registry on disconnect
        for d_id, ws in list(active_secure_connections.items()):
            if ws == websocket:
                del active_secure_connections[d_id]
                logger.info(f"[P2P SERVER] Removed {d_id} from active secure connections.")


# ==========================================
# CLIENT-SIDE (Device A connecting to B)
# ==========================================
async def connect_to_peer(target_ip: str, target_p2p_port: int, target_device_id: str):
    """
    Connects to a peer via WSS, executes certificate pinning validation, 
    answers the challenge, and establishes a SECURE tunnel.
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
                
                # Send a test PING to prove the channel works
                await websocket.send("PING")
                pong_reply = await websocket.recv()
                logger.info(f"[P2P CLIENT] Ping test response: {pong_reply}")
                return True
            else:
                logger.error(f"[P2P CLIENT] Handshake rejected by server: {status_msg}")
                return False

    except Exception as e:  # noqa: BLE001
        logger.error(f"[P2P CLIENT] Connection error to {target_ip}: {e}")
        return False
    finally:
        db.close()