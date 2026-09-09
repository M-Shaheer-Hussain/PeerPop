import uuid
from datetime import datetime, timezone

from app.database.database import base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class User(base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hashed: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    is_active: Mapped[bool] = mapped_column(default=True)

class Device(base):
    __tablename__="devices"

    # Added UUID default to prevent IntegrityError on missing primary key[cite: 5]
    id: Mapped[str] = mapped_column(primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    owner_id:Mapped[int | None]=mapped_column(ForeignKey("users.id"))
    device_name: Mapped[str] = mapped_column(nullable=False)
    public_key: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    lastseen: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    is_local: Mapped[bool] = mapped_column(default=False)


class TrustedDevice(base):
    __tablename__ = "trusted_devices"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    remote_device_id: Mapped[str] = mapped_column(index=True)
    remote_public_key: Mapped[str] = mapped_column(nullable=False)
    device_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="TRUSTED")  # TRUSTED or REVOKED
    paired_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))