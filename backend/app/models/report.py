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


class Report(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "reports"

    bid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bids.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    generated_by_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    bid: Mapped["Bid"] = relationship("Bid", back_populates="reports")
    tender: Mapped["Tender"] = relationship("Tender", back_populates="reports")
    generated_by: Mapped["User"] = relationship("User", back_populates="reports_generated")
