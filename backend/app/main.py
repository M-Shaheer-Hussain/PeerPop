from app.api.health import router as health_router
from app.Auth.auth import router as auth_router
from app.core.config import settings
from app.database.database import base, engine
from app.models import models
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

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