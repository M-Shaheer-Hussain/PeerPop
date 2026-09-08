# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Local File Sharing"
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    SECRET_KEY: str = "default-secret-key"
    ALGORITHM: str = "HS256"

    DISCOVERY_PORT: int = 54321
    DISCOVERY_INTERVAL: int = 3  # Seconds between broadcasts

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()