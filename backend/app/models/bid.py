import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from backend.app.models.tender import DocumentStatusEnum

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.tender import Tender
    from backend.app.models.document_extraction import DocumentExtraction, Evidence
    from backend.app.models.compliance import ComplianceResult, VerificationRecord
    from backend.app.models.review import ReviewTask
    from backend.app.models.report import Report


class BidStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    FINALIZED = "FINALIZED"
    WITHDRAWN = "WITHDRAWN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class DocumentTypeEnum(str, enum.Enum):
    GST_CERTIFICATE = "GST_CERTIFICATE"
    PAN = "PAN"
    FINANCIAL = "FINANCIAL"
    EXPERIENCE = "EXPERIENCE"
    TECHNICAL_PROPOSAL = "TECHNICAL_PROPOSAL"
    COMPLIANCE_DECLARATION = "COMPLIANCE_DECLARATION"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    MSME_CERTIFICATE = "MSME_CERTIFICATE"
    ISO_CERTIFICATE = "ISO_CERTIFICATE"
    SECURITY_CLEARANCE = "SECURITY_CLEARANCE"
    OTHER = "OTHER"


class Bid(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bids"

    tender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bidder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bid_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[BidStatusEnum] = mapped_column(
        Enum(BidStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=BidStatusEnum.DRAFT,
        index=True,
        nullable=False,
    )
    submission_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender", back_populates="bids")
    bidder: Mapped["User"] = relationship("User", back_populates="bids")
    documents: Mapped[List["BidDocument"]] = relationship(
        "BidDocument", back_populates="bid", cascade="all, delete-orphan"
    )
    compliance_results: Mapped[List["ComplianceResult"]] = relationship(
        "ComplianceResult", back_populates="bid", cascade="all, delete-orphan"
    )
    review_tasks: Mapped[List["ReviewTask"]] = relationship(
        "ReviewTask", back_populates="bid", cascade="all, delete-orphan"
    )
    verification_records: Mapped[List["VerificationRecord"]] = relationship(
        "VerificationRecord", back_populates="bid", cascade="all, delete-orphan"
    )
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="bid", cascade="all, delete-orphan")


class BidDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bid_documents"

    bid_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bids.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[DocumentTypeEnum] = mapped_column(
        Enum(DocumentTypeEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=DocumentTypeEnum.OTHER,
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[DocumentStatusEnum] = mapped_column(
        Enum(DocumentStatusEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatusEnum.UPLOADED,
        index=True,
        nullable=False,
    )

    # Relationships
    bid: Mapped["Bid"] = relationship("Bid", back_populates="documents")
    extractions: Mapped[List["DocumentExtraction"]] = relationship(
        "DocumentExtraction", back_populates="document", cascade="all, delete-orphan"
    )
    evidence_records: Mapped[List["Evidence"]] = relationship(
        "Evidence", back_populates="bid_document", cascade="all, delete-orphan"
    )