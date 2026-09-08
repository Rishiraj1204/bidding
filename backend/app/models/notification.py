from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, UUIDPrimaryKeyMixin


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), default="INFO", nullable=False)  # INFO, WARNING, SUCCESS, ACTION_REQUIRED
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    related_resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # tender, bid, review_task
    related_resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
