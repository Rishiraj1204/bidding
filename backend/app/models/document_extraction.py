from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, UUIDPrimaryKeyMixin


class DocumentExtraction(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_extractions"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    document: Mapped["BidDocument"] = relationship("BidDocument", back_populates="extractions")
    entities: Mapped[List["ExtractedEntity"]] = relationship(
        "ExtractedEntity", back_populates="extraction", cascade="all, delete-orphan"
    )


class ExtractedEntity(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "extracted_entities"

    extraction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_extractions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # organization_name, gst_number, pan_number, etc.
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    extraction: Mapped["DocumentExtraction"] = relationship("DocumentExtraction", back_populates="entities")
    evidence_records: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="entity")


class Evidence(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evidence"

    bid_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bid_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("extracted_entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    extracted_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    snippet_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="DOCUMENT_OCR", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    # Relationships
    bid_document: Mapped["BidDocument"] = relationship("BidDocument", back_populates="evidence_records")
    entity: Mapped[Optional["ExtractedEntity"]] = relationship("ExtractedEntity", back_populates="evidence_records")
    compliance_results: Mapped[List["ComplianceResult"]] = relationship("ComplianceResult", back_populates="evidence")
