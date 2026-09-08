from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.services.dashboard_service import get_dashboard_summary

router = APIRouter()


@router.get(
    "",
    response_model=DashboardSummaryResponse,
    summary="Get Role-Aware Dashboard Summary",
)
def get_dashboard_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve personalized, role-specific metrics, charts, and operational queues.
    """
    return get_dashboard_summary(db=db, user=current_user)
