from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Basic Health Check")
def health_check():
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
    }
