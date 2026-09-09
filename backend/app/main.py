import asyncio
import logging
from contextlib import asynccontextmanager

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
from app.database.database import base, engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    base.metadata.create_all(bind=engine)
    local_device = initialize_device_identity()
    
    if local_device:
        logger.info(f"Device Ready. Identity ID: {local_device.id}")
        
        loop = asyncio.get_running_loop()
        
        # 1. Start the UDP Listener
        transport, protocol = await loop.create_datagram_endpoint(  # noqa: RUF059
            lambda: DiscoveryProtocol(local_device_id=str(local_device.id)),
            local_addr=('0.0.0.0', settings.DISCOVERY_PORT),
            allow_broadcast=True,
            reuse_port=True
        )
        
        # 2. Start the Broadcaster & Cleanup tasks

        broadcast_task = asyncio.create_task(udp_broadcaster(local_device, settings.API_PORT))
        cleanup_task = asyncio.create_task(cleanup_stale_peers())
    else:
        logger.warning("Device identity file exists, but database record is missing.")
        
    yield
    
    # Graceful teardown on server stop
    if local_device:
        broadcast_task.cancel()
        cleanup_task.cancel()
        transport.close()

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