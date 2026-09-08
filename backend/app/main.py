import logging
from contextlib import asynccontextmanager

from app.api.device import router as device_router
from app.api.health import router as health_router
from app.Auth.auth import router as auth_router
from app.core.config import settings
from app.core.identity import initialize_device_identity
from app.database.database import base, engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate tables and identity before taking requests
@asynccontextmanager
async def lifespan(app: FastAPI):
    base.metadata.create_all(bind=engine)
    
    # Executes the flow: Check -> Load/Generate -> Ready
    local_device = initialize_device_identity()
    
    # Safety check to satisfy Pylance and handle potential DB inconsistency
    if local_device:
        logger.info(f"Device Ready. Identity ID: {local_device.id}")
    else:
        logger.warning("Device identity file exists, but database record is missing.")
        
    yield
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
