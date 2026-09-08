from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.bid import BidStatusEnum
from backend.app.models.tender import TenderStatusEnum


class BidBase(BaseModel):
    tender_id: str = Field(..., description="Target Tender UUID")
    notes: Optional[str] = Field(None, max_length=2000, description="Bidder remarks, notes, or technical overview")


class BidCreate(BidBase):
    bid_number: Optional[str] = Field(None, max_length=100, description="Optional custom bid reference number")


class BidUpdate(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


class BidStatusUpdate(BaseModel):
    status: BidStatusEnum
    reason: Optional[str] = Field(None, max_length=500)


class BidResponse(BaseModel):
    id: str
    tender_id: str
    bidder_id: str
    bid_number: str
    status: BidStatusEnum
    submission_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Tender summary metadata
    tender_number: Optional[str] = None
    tender_title: Optional[str] = None
    tender_organization: Optional[str] = None
    tender_deadline: Optional[datetime] = None
    tender_status: Optional[TenderStatusEnum] = None

    # Bidder summary metadata
    bidder_name: Optional[str] = None
    bidder_email: Optional[str] = None
    bidder_organization: Optional[str] = None

    # Counts
    documents_count: int = 0
    compliance_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BidListResponse(BaseModel):
    items: List[BidResponse]
    total: int
    page: int
    size: int
    pages: int
