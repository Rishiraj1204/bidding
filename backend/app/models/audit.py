from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # LOGIN, TENDER_CREATED, DOCUMENT_UPLOADED, COMPLIANCE_DECISION, REVIEW_DECISION, etc.
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # user, tender, bid, document, compliance, review
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), index=True
    )

    # Relationships
    actor: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
