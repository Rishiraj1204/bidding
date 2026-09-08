from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.compliance import VerificationStatusEnum


class TriggerVerificationRequest(BaseModel):
    verification_type: str = Field(..., description="GST, PAN, MSME, REGISTRATION")
    identifier: str = Field(..., description="Document identification number to verify")
    compliance_result_id: Optional[str] = None


class VerificationRecordResponse(BaseModel):
    id: str
    bid_id: str
    compliance_result_id: Optional[str] = None
    verification_type: str
    provider_name: str
    is_mock: bool
    status: VerificationStatusEnum
    reference_id: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BidVerificationListResponse(BaseModel):
    items: list[VerificationRecordResponse]
    total: int
