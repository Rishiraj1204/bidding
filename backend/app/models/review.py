import enum
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    COMPLETED = "COMPLETED"


class ReviewTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_tasks"

    bid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bids.id", ondelete="CASCADE"), nullable=False, index=True
    )
    compliance_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("compliance_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[ReviewStatusEnum] = mapped_column(
        Enum(ReviewStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=ReviewStatusEnum.PENDING,
        index=True,
        nullable=False,
    )
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    bid: Mapped["Bid"] = relationship("Bid", back_populates="review_tasks")
    compliance_result: Mapped["ComplianceResult"] = relationship("ComplianceResult", back_populates="review_tasks")
    assigned_to: Mapped[Optional["User"]] = relationship("User", back_populates="assigned_reviews")
    decisions: Mapped[List["ReviewDecision"]] = relationship(
        "ReviewDecision", back_populates="task", cascade="all, delete-orphan"
    )


class ReviewDecision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "review_decisions"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    new_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    task: Mapped["ReviewTask"] = relationship("ReviewTask", back_populates="decisions")
    reviewer: Mapped["User"] = relationship("User", back_populates="review_decisions")
