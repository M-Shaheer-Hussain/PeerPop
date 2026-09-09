
from app.core.discovery import nearby_devices
from app.p2p.handler import connect_to_peer
from app.schemas.schemas import DiscoveredDevice
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/network", tags=["Network"])

@router.get("/nearby", response_model=list[DiscoveredDevice])
def get_nearby_devices():
    return list(nearby_devices.values())

@router.post("/connect/{device_id}")
async def trigger_p2p_connection(device_id: str):
    """Test endpoint for Phase 6: Manually trigger a secure WSS connection to a peer."""
    peer = nearby_devices.get(device_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found on local network radar.")
        
    success = await connect_to_peer(
        target_ip=peer["ip_address"],
        target_p2p_port=peer.get("p2p_port", 8765),
        target_device_id=device_id
    )
    
    if success:
        return {"message": f"Successfully established secure P2P connection with {peer['device_name']}!"}
    else:
        raise HTTPException(status_code=400, detail="Secure connection or mutual authentication failed.")