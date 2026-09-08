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