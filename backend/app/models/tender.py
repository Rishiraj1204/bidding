import enum
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenderStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    UNDER_EVALUATION = "UNDER_EVALUATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DocumentStatusEnum(str, enum.Enum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RequirementCategoryEnum(str, enum.Enum):
    FINANCIAL = "FINANCIAL"
    TECHNICAL = "TECHNICAL"
    EXPERIENCE = "EXPERIENCE"
    CERTIFICATION = "CERTIFICATION"
    MANDATORY_DOCUMENT = "MANDATORY_DOCUMENT"
    ELIGIBILITY = "ELIGIBILITY"
    OTHER = "OTHER"


class Tender(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenders"

    tender_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    submission_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TenderStatusEnum] = mapped_column(
        Enum(TenderStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=TenderStatusEnum.DRAFT,
        index=True,
        nullable=False,
    )
    created_by_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Relationships
    created_by: Mapped["User"] = relationship("User", back_populates="created_tenders")
    documents: Mapped[List["TenderDocument"]] = relationship(
        "TenderDocument", back_populates="tender", cascade="all, delete-orphan"
    )
    requirements: Mapped[List["TenderRequirement"]] = relationship(
        "TenderRequirement", back_populates="tender", cascade="all, delete-orphan"
    )
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="tender", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="tender", cascade="all, delete-orphan")


class TenderDocument(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "tender_documents"

    tender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256
    status: Mapped[DocumentStatusEnum] = mapped_column(
        Enum(DocumentStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatusEnum.UPLOADED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender", back_populates="documents")
    derived_requirements: Mapped[List["TenderRequirement"]] = relationship(
        "TenderRequirement", back_populates="source_document"
    )


class TenderRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tender_requirements"

    tender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[RequirementCategoryEnum] = mapped_column(
        Enum(RequirementCategoryEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=RequirementCategoryEnum.OTHER,
        index=True,
        nullable=False,
    )
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    parameter: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., turnover, experience_years
    operator: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # >=, <=, ==, contains, exists
    threshold_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g., 5000000
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # INR, years, count
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    source_document_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tender_documents.id", ondelete="SET NULL"), nullable=True
    )
    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender", back_populates="requirements")
    source_document: Mapped[Optional["TenderDocument"]] = relationship(
        "TenderDocument", back_populates="derived_requirements"
    )
    compliance_results: Mapped[List["ComplianceResult"]] = relationship(
        "ComplianceResult", back_populates="requirement", cascade="all, delete-orphan"
    )
