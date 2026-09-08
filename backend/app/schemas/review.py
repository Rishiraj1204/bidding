from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.review import ReviewStatusEnum


class ReviewDecisionCreate(BaseModel):
    new_decision: str = Field(..., description="COMPLIANT, NON_COMPLIANT, or CLARIFICATION_REQUIRED")
    justification: str = Field(..., min_length=5, description="Mandatory justification explanation for this decision")
    comments: Optional[str] = None


class AssignReviewTaskRequest(BaseModel):
    assigned_to_id: Optional[str] = Field(None, description="User ID to assign to. If omitted, self-assigns.")


class ReviewDecisionResponse(BaseModel):
    id: str
    task_id: str
    reviewer_id: str
    reviewer_name: Optional[str] = None
    original_decision: str
    new_decision: str
    justification: str
    comments: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskResponse(BaseModel):
    id: str
    bid_id: str
    bid_number: Optional[str] = None
    tender_id: Optional[str] = None
    tender_title: Optional[str] = None
    compliance_result_id: str
    requirement_id: Optional[str] = None
    requirement_text: Optional[str] = None
    requirement_category: Optional[str] = None
    mandatory: bool = True
    status: ReviewStatusEnum
    trigger_reason: str
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    original_decision: str
    current_status: str
    extracted_value: Optional[str] = None
    normalized_value: Optional[str] = None
    evidence_snippet: Optional[str] = None
    source_document_filename: Optional[str] = None
    source_page: Optional[int] = None
    decisions: List[ReviewDecisionResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskListResponse(BaseModel):
    items: List[ReviewTaskResponse]
    total: int
