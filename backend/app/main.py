import asyncio
import logging
import ssl
from contextlib import asynccontextmanager

import websockets
from app.api.device import router as device_router
from app.api.health import router as health_router
from app.api.network import router as network_router
from app.api.pairing import router as pairing_router
from app.Auth.auth import router as auth_router
from app.core.config import settings
from app.core.discovery import (
    DiscoveryProtocol,
    cleanup_stale_peers,
    nearby_devices,  # noqa: F401
    udp_broadcaster,
)
from app.core.identity import initialize_device_identity
from app.core.tls_cert import generate_tls_certificates
from app.database.database import base, engine
from app.p2p.handler import handle_incoming_p2p
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    base.metadata.create_all(bind=engine)
    local_device = initialize_device_identity()
    
    broadcast_task = None
    cleanup_task = None
    p2p_server = None
    transport = None

    if local_device:
        logger.info(f"Device Ready. Identity ID: {local_device.id}")
        loop = asyncio.get_running_loop()

        # 1. Start the UDP Listener
        transport, protocol = await loop.create_datagram_endpoint(  # noqa: RUF059
            lambda: DiscoveryProtocol(local_device_id=str(local_device.id)),
            local_addr=('0.0.0.0', settings.DISCOVERY_PORT),
            allow_broadcast=True,
        )

        # 2. Start the Broadcaster & Cleanup tasks
        broadcast_task = asyncio.create_task(udp_broadcaster(local_device, settings.API_PORT))
        cleanup_task = asyncio.create_task(cleanup_stale_peers())

        # 3. PHASE 6: Start the Secure WSS P2P Server (Port 8765)
        try:
            cert_file, key_file = generate_tls_certificates()
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER) if 'ssl' in globals() else None  # noqa: F841
            # Import ssl inside lifespan if not imported globally
            import ssl as ssl_module
            p2p_ssl_context = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_SERVER)
            p2p_ssl_context.load_cert_chain(certfile=cert_file, keyfile=key_file)

            p2p_server = await websockets.serve(
                handle_incoming_p2p, 
                "0.0.0.0", 
                8765, 
                ssl=p2p_ssl_context
            )
            logger.info("🔒 Secure P2P WSS Server successfully listening on port 8765")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to start Secure P2P server: {e}")

    else:
        logger.warning("Device identity file exists, but database record is missing.")

    yield

    # Graceful teardown on server stop
    if local_device:
        if broadcast_task: broadcast_task.cancel()
        if cleanup_task: cleanup_task.cancel()
        if transport: transport.close()
        if p2p_server:
            p2p_server.close()
            await p2p_server.wait_closed()
        logger.info("Server shut down gracefully.")

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(device_router)
app.include_router(network_router)
app.include_router(pairing_router)