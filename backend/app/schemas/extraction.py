from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractedEntityResponse(BaseModel):
    id: str
    extraction_id: str
    entity_type: str
    raw_value: str
    normalized_value: Optional[str] = None
    page_number: Optional[int] = 1
    confidence: Optional[float] = None
    source_snippet: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceResponse(BaseModel):
    id: str
    bid_document_id: str
    entity_id: Optional[str] = None
    page_number: Optional[int] = 1
    field_name: str
    extracted_value: str
    normalized_value: Optional[str] = None
    confidence: float
    snippet_text: Optional[str] = None
    source_type: str = "DOCUMENT_OCR"
    created_at: datetime
    document_filename: Optional[str] = None
    document_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentExtractionDetailResponse(BaseModel):
    id: str
    document_id: str
    raw_text: Optional[str] = None
    total_pages: int = 1
    ocr_confidence: Optional[float] = None
    status: str = "COMPLETED"
    error_message: Optional[str] = None
    entities: List[ExtractedEntityResponse] = Field(default_factory=list)
    evidence_records: List[EvidenceResponse] = Field(default_factory=list)
    extracted_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BidExtractionSummaryResponse(BaseModel):
    bid_id: str
    total_documents: int = 0
    total_entities_extracted: int = 0
    total_evidence_records: int = 0
    entities: List[ExtractedEntityResponse] = Field(default_factory=list)
    evidence: List[EvidenceResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BidEvidenceListResponse(BaseModel):
    items: List[EvidenceResponse]
    total: int
