from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from app.core.config import settings


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_password.decode("utf-8")

def verify_password(password: str, password_hashed: str) -> bool:
    return (
        bcrypt.checkpw(password.encode("utf-8"),
                       password_hashed.encode("utf-8"))
    )

def create_accessToken(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {"exp": expire, "sub": str(user_id)}
    return jwt.encode(to_encode, settings.SECRET_KEY, settings.ALGORITHM)