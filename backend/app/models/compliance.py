import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ComplianceStatusEnum(str, enum.Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class VerificationStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    MISMATCH = "MISMATCH"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class ComplianceRule(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "compliance_rules"

    rule_name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DETERMINISTIC"
    )  # DETERMINISTIC, SEMANTIC_AI, CROSS_DOC_MATCH
    rule_definition: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    compliance_results: Mapped[List["ComplianceResult"]] = relationship("ComplianceResult", back_populates="rule")


class ComplianceResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "compliance_results"

    bid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bids.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tender_requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rule_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("compliance_rules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[ComplianceStatusEnum] = mapped_column(
        Enum(ComplianceStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=ComplianceStatusEnum.NEEDS_REVIEW,
        index=True,
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluated_by: Mapped[str] = mapped_column(
        String(50), default="RULE_ENGINE", nullable=False
    )  # RULE_ENGINE, AI_SEMANTIC, HUMAN_REVIEW

    # Relationships
    bid: Mapped["Bid"] = relationship("Bid", back_populates="compliance_results")
    requirement: Mapped["TenderRequirement"] = relationship("TenderRequirement", back_populates="compliance_results")
    evidence: Mapped[Optional["Evidence"]] = relationship("Evidence", back_populates="compliance_results")
    rule: Mapped[Optional["ComplianceRule"]] = relationship("ComplianceRule", back_populates="compliance_results")
    verification_records: Mapped[List["VerificationRecord"]] = relationship(
        "VerificationRecord", back_populates="compliance_result", cascade="all, delete-orphan"
    )
    review_tasks: Mapped[List["ReviewTask"]] = relationship(
        "ReviewTask", back_populates="compliance_result", cascade="all, delete-orphan"
    )


class VerificationRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "verification_records"

    bid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bids.id", ondelete="CASCADE"), nullable=False, index=True
    )
    compliance_result_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("compliance_results.id", ondelete="SET NULL"), nullable=True, index=True
    )
    verification_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # GST, PAN, CERTIFICATE, MSME, BLACKLIST
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, default="MOCK")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[VerificationStatusEnum] = mapped_column(
        Enum(VerificationStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=VerificationStatusEnum.PENDING,
        index=True,
        nullable=False,
    )
    reference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    response_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    bid: Mapped["Bid"] = relationship("Bid", back_populates="verification_records")
    compliance_result: Mapped[Optional["ComplianceResult"]] = relationship(
        "ComplianceResult", back_populates="verification_records"
    )
