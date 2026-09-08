from app.core.discovery import nearby_devices
from app.schemas.schemas import DiscoveredDevice
from fastapi import APIRouter

# Initialize the router with a prefix and tag for the Swagger UI
router = APIRouter(prefix="/network", tags=["Network"])

@router.get("/nearby", response_model=list[DiscoveredDevice])
def get_nearby_devices():
    # Convert the dictionary values to a list for the frontend
    return list(nearby_devices.values())