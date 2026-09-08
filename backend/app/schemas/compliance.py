from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.compliance import ComplianceStatusEnum, VerificationStatusEnum


class ComplianceResultResponse(BaseModel):
    id: str
    bid_id: str
    requirement_id: str
    requirement_text: str
    requirement_category: str
    mandatory: bool
    parameter: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[str] = None
    unit: Optional[str] = None
    status: ComplianceStatusEnum
    reason: Optional[str] = None
    confidence: Optional[float] = None
    evaluated_by: str = "RULE_ENGINE"
    evidence_id: Optional[str] = None
    extracted_value: Optional[str] = None
    normalized_value: Optional[str] = None
    source_document_filename: Optional[str] = None
    source_page: Optional[int] = None
    source_snippet: Optional[str] = None
    verification_status: Optional[VerificationStatusEnum] = None
    is_mock_verification: Optional[bool] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BidComplianceSummaryResponse(BaseModel):
    bid_id: str
    overall_status: ComplianceStatusEnum
    total_requirements: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    needs_review_count: int = 0
    not_applicable_count: int = 0
    mandatory_passed: bool = False
    results: List[ComplianceResultResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvaluateComplianceRequest(BaseModel):
    auto_verify: bool = True
