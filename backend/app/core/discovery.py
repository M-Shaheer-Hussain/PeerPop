import asyncio
import logging
import socket
import time

from app.core.config import settings
from app.schemas.schemas import DiscoveryPayload
from pydantic import ValidationError

logger = logging.getLogger(__name__)

# The in-memory peer registry
nearby_devices = {}

async def udp_broadcaster(local_device, api_port: int):

    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)

    payload = DiscoveryPayload(
        device_id=str(local_device.id),
        device_name=local_device.device_name,
        public_key=local_device.public_key,
        port=api_port
    ).model_dump_json().encode('utf-8')

    while True:
        try:
            await loop.sock_sendto(sock, payload, ('255.255.255.255', settings.DISCOVERY_PORT))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Broadcast failed (expected on some isolated networks): {e}")
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
                "last_seen": time.time(),
                "status": "Available"
            }
        except (ValidationError, UnicodeDecodeError):
            pass  # Silently drop malformed or malicious packets

async def cleanup_stale_peers():
    """Removes peers that haven't sent a heartbeat in 15 seconds."""
    while True:
        current_time = time.time()
        stale_ids = [
            d_id for d_id, data in nearby_devices.items()
            if current_time - data["last_seen"] > 15
        ]
        for d_id in stale_ids:
            del nearby_devices[d_id]
            logger.info(f"Device {d_id} went offline.")
            
        await asyncio.sleep(5)