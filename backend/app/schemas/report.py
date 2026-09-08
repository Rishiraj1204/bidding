from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GenerateReportRequest(BaseModel):
    include_evidence_snippets: bool = True


class ReportResponse(BaseModel):
    id: str
    bid_id: str
    tender_id: str
    report_number: str
    file_path: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    generated_by_id: str
    generated_by_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int
