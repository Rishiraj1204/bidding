from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.audit import AuditLogListResponse
from backend.app.services.audit_service import list_audit_logs

router = APIRouter()


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List System Audit Logs",
)
def get_audit_logs_endpoint(
    actor_email: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Query immutable security audit trails.
    Strictly authorized to ADMIN and AUDITOR roles.
    """
    return list_audit_logs(
        db=db,
        user=current_user,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
