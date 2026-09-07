import jwt
from app.core.config import settings
from app.database.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse
from app.security.security import (
    create_accessToken,
    get_password_hash,
    verify_password,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):  # noqa: B008
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    hashed_pw = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, password_hashed=hashed_pw)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

# --- 2. LOGIN ---
@router.post("/login")
def login(user_data: UserCreate, response: Response, db: Session = Depends(get_db)):  # noqa: B008
    user = db.query(User).filter(User.username == user_data.username).first()
    
    if not user or not verify_password(user_data.password, user.password_hashed):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_accessToken(user_id=user.id)
    
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True, 
        samesite="lax", 
        secure=False,      
        max_age=86400  #24hours in seconds
    )
    
    return {"message": "Successfully logged in"}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", httponly=True, samesite="lax")
    return {"message": "Successfully logged out"}

def get_current_user(request: Request, db: Session = Depends(get_db)):  # noqa: B008
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token structure")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
        
    return user

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):  # noqa: B008
    return current_user