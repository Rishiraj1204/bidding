from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.bid import DocumentTypeEnum
from backend.app.models.tender import DocumentStatusEnum


class TenderDocumentResponse(BaseModel):
    id: str
    tender_id: str
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    status: DocumentStatusEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenderDocumentListResponse(BaseModel):
    items: List[TenderDocumentResponse]
    total: int


class BidDocumentResponse(BaseModel):
    id: str
    bid_id: str
    document_type: DocumentTypeEnum
    filename: str
    file_size: int
    mime_type: str
    file_hash: str
    status: DocumentStatusEnum
    created_at: datetime
    updated_at: Optional[datetime] = None
    has_ocr: bool = False
    ocr_confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class BidDocumentListResponse(BaseModel):
    items: List[BidDocumentResponse]
    total: int


class OCRExtractionResponse(BaseModel):
    id: str
    document_id: str
    raw_text: Optional[str] = None
    total_pages: int = 1
    ocr_confidence: Optional[float] = None
    extracted_data: Optional[Dict[str, Any]] = None
    status: str = "COMPLETED"
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusUpdate(BaseModel):
    status: DocumentStatusEnum
    error_message: Optional[str] = None
