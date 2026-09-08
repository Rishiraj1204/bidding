from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models.tender import TenderStatusEnum


class TenderBase(BaseModel):
    tender_number: str = Field(..., min_length=3, max_length=100, description="Unique Tender Identifier (e.g. GEM/2026/B/1001)")
    title: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    organization: str = Field(..., min_length=2, max_length=255, description="Procuring Government Entity or Ministry")
    category: Optional[str] = Field(None, max_length=100)
    submission_deadline: datetime = Field(..., description="Tender submission deadline in UTC")

    @field_validator("submission_deadline")
    @classmethod
    def validate_future_deadline(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


class TenderCreate(TenderBase):
    status: TenderStatusEnum = TenderStatusEnum.DRAFT


class TenderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = None
    organization: Optional[str] = Field(None, min_length=2, max_length=255)
    category: Optional[str] = None
    submission_deadline: Optional[datetime] = None
    status: Optional[TenderStatusEnum] = None

    @field_validator("submission_deadline")
    @classmethod
    def validate_future_deadline(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


class TenderStatusUpdate(BaseModel):
    status: TenderStatusEnum
    reason: Optional[str] = Field(None, max_length=500)


class TenderResponse(TenderBase):
    id: str
    status: TenderStatusEnum
    created_by_id: str
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    documents_count: int = 0
    requirements_count: int = 0
    bids_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TenderListResponse(BaseModel):
    items: List[TenderResponse]
    total: int
    page: int
    size: int
    pages: int
