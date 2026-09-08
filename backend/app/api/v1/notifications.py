from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from backend.app.services.notification_service import (
    get_unread_count,
    list_user_notifications,
    mark_all_as_read,
    mark_as_read,
)

router = APIRouter()


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List User Notifications",
)
def list_notifications_endpoint(
    is_read: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List notifications for the currently logged-in user.
    """
    return list_user_notifications(
        db=db,
        user_id=current_user.id,
        is_read=is_read,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get Unread Notification Count",
)
def get_unread_count_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve unread notification count for the badge icon.
    """
    return get_unread_count(db=db, user_id=current_user.id)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark Notification as Read",
)
def mark_notification_read_endpoint(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Mark a single notification as read.
    """
    return mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )


@router.post(
    "/read-all",
    response_model=UnreadCountResponse,
    summary="Mark All Notifications as Read",
)
def mark_all_read_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Mark all unread notifications for the user as read.
    """
    return mark_all_as_read(db=db, user_id=current_user.id)
