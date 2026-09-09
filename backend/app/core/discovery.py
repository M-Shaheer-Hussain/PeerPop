import asyncio
import logging
import socket
import time

from app.core.config import settings
from app.database.database import localsession
from app.models.models import Device
from app.schemas.schemas import DiscoveryPayload
from pydantic import ValidationError

logger = logging.getLogger(__name__)

# The in-memory peer registry
nearby_devices = {}

# --- New Global State ---
nearby_devices = {}
is_discoverable = False  # Devices start hidden until user logs in

def get_current_device_name(device_id: str) -> str:
    """Synchronously fetches the freshest device name from the database."""
    db = localsession()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        return device.device_name if device else "Unknown Node"
    finally:
        db.close()

async def udp_broadcaster(local_device, api_port: int):
    """Broadcasts this device's presence to the local network."""
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)

    while True:
        # Only broadcast if a user is actively authenticated
        if is_discoverable:
            # Fetch the latest name without blocking the async loop
            fresh_name = await asyncio.to_thread(get_current_device_name, str(local_device.id))
            
            # Rebuild the payload dynamically inside the loop
            payload = DiscoveryPayload(
                device_id=str(local_device.id),
                device_name=fresh_name,
                public_key=local_device.public_key,
                port=api_port
            ).model_dump_json().encode('utf-8')

            try:
                await loop.sock_sendto(sock, payload, ('255.255.255.255', settings.DISCOVERY_PORT))
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Broadcast failed: {e}")
                
        await asyncio.sleep(settings.DISCOVERY_INTERVAL)


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """Listens for other Local Drop devices broadcasting on the LAN."""
    def __init__(self, local_device_id: str):
        self.local_device_id = local_device_id

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            # Strictly validate incoming data
            payload = DiscoveryPayload.model_validate_json(data.decode('utf-8'))
            
            # Ignore our own broadcast loopback
            if payload.device_id == self.local_device_id:
                return

            # Register or update the peer's heartbeat
            nearby_devices[payload.device_id] = {
                "device_id": payload.device_id,
                "device_name": payload.device_name,
                "public_key": payload.public_key,
                "ip_address": addr[0],
                "port": payload.port,  # Added this line
                "last_seen": time.time(),
                "status": "Available"
            }
        except (ValidationError, UnicodeDecodeError):
            pass  # Silently drop malformed or malicious packets

async def cleanup_stale_peers():
    """Marks peers as Unavailable after 15 seconds, and removes them after 60 seconds."""
    while True:
        current_time = time.time()
        
        # Iterate over a list of items so we can safely modify the dictionary
        for d_id, data in list(nearby_devices.items()):
            time_since_last_seen = current_time - data["last_seen"]
            
            if time_since_last_seen > 60:
                # Stage 2: Completely remove from memory after 1 minute
                del nearby_devices[d_id]
            elif time_since_last_seen > 15 and data["status"] != "Unavailable":
                # Stage 1: Mark as offline on the UI after 15 seconds
                nearby_devices[d_id]["status"] = "Unavailable"
                logger.info(f"Device {d_id} went offline.")
                
        await asyncio.sleep(5)