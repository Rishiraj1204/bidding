from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    role: str
    user_name: str
    user_email: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    recent_bids: List[Dict[str, Any]] = Field(default_factory=list)
    recent_tenders: List[Dict[str, Any]] = Field(default_factory=list)
    pending_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list)
