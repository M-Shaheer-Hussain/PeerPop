import logging

from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health", tags=["Monitoring"])
def health_check():
    try:
        return {
            "message": "Backend Alive",
            "status": "Healthy"
        }
    except Exception as exc:
        logger.error(f"Health Check Failed: {exc}", exc_info=True)  # noqa: G201
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health Check Failed: Service Unavailable"
        )