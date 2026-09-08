from app.database.database import get_db
from app.models.models import Device
from app.schemas.schemas import DeviceCreate, DeviceNameUpdate, DeviceResponse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/device", tags=["Device"])



@router.put("/me/name", response_model=DeviceResponse)
def update_local_device_name(name_data: DeviceNameUpdate, db: Session = Depends(get_db)):  # noqa: B008
    # Fetch the local device (assuming the local node is the first/primary record)
    device = db.query(Device).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local device identity not found."
        )
    
    # Update the name and save to the database
    device.device_name = name_data.device_name
    db.commit()
    db.refresh(device)
    
    return device

@router.post("/peer", response_model=DeviceResponse)
def register_peer_device(device_data: DeviceCreate, db: Session = Depends(get_db)):  # noqa: B008
    # Search for an existing peer by its unique cryptographic footprint
    existing_peer = db.query(Device).filter(Device.public_key == device_data.public_key).first()
    
    if existing_peer:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Peer device identity is already registered on this node."
        )

    # Register the new peer device
    new_peer = Device(
        device_name=device_data.device_name,
        public_key=device_data.public_key
    )
    db.add(new_peer)
    db.commit()
    db.refresh(new_peer)
    
    return new_peer

@router.get("/me", response_model=DeviceResponse)
def get_local_device(db: Session = Depends(get_db)):  # noqa: B008
    device = db.query(Device).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device identity not initialized"
        )
    return device