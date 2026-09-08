import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.notification import Notification
from backend.app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)


def create_notification(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "INFO",
    related_resource_type: Optional[str] = None,
    related_resource_id: Optional[str] = None,
) -> Notification:
    """Create a new notification entry for a specific user."""
    notif = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
        related_resource_type=related_resource_type,
        related_resource_id=related_resource_id,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def list_user_notifications(
    db: Session,
    user_id: str,
    is_read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    """List notifications for the current authenticated user with pagination and unread counts."""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()

    items = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    response_items = [NotificationResponse.model_validate(n) for n in items]

    return NotificationListResponse(
        items=response_items,
        total=total,
        unread_count=unread_count,
    )


def get_unread_count(db: Session, user_id: str) -> UnreadCountResponse:
    """Get the unread notification count for a user."""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).count()
    return UnreadCountResponse(unread_count=count)


def mark_as_read(db: Session, notification_id: str, user_id: str) -> NotificationResponse:
    """Mark a single notification as read, ensuring object ownership."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notif.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot access or modify notifications belonging to another user.",
        )

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return NotificationResponse.model_validate(notif)


def mark_all_as_read(db: Session, user_id: str) -> UnreadCountResponse:
    """Mark all unread notifications for a user as read."""
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return UnreadCountResponse(unread_count=0)
