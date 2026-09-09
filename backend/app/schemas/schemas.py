from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime
    is_active: bool
    
    # By default Pydantic model returns dictionaries but when this will be used
    # in CRUDS we returns BaseModel causing an error[cite: 6]
    model_config = ConfigDict(from_attributes=True)

class DeviceResponse(BaseModel):
    device_name: str
    public_key: str
    model_config = ConfigDict(from_attributes=True)

class DeviceCreate(BaseModel):
    device_name: str
    public_key: str  # Added this field so the endpoint can satisfy the database requirement[cite: 5, 6]

class DeviceNameUpdate(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=50)

class DiscoveryPayload(BaseModel):
    device_id: str
    device_name: str
    public_key: str
    port: int = 8000
    version: str = "1.0"
    p2p_port: int = 8765  # NEW: We set a default of 8765 just in case

class DiscoveredDevice(BaseModel):
    device_id: str
    device_name: str
    public_key: str
    ip_address: str
    port: int              # Added so Phase 5 knows where to send HTTP requests
    last_seen: float
    status: str = "Available"

class PairingRequest(BaseModel):
    device_id: str
    device_name: str
    public_key: str

class PairingResponse(BaseModel):
    session_id: str
    nonce: str
    code: str

class PairingVerify(BaseModel):
    session_id: str
    signature: str

class InitiatePairing(BaseModel):
    target_ip: str
    target_port: int
    target_device_id: str
    target_device_name: str
    target_public_key: str