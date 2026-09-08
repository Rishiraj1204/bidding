from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.compliance import (
    BidComplianceSummaryResponse,
    ComplianceResultResponse,
    EvaluateComplianceRequest,
)
from backend.app.services.compliance_service import (
    evaluate_bid_compliance,
    get_bid_compliance_summary,
    get_requirement_compliance_detail,
)

router = APIRouter()


@router.post(
    "/bid/{bid_id}/evaluate",
    response_model=BidComplianceSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Bid Compliance",
)
def evaluate_compliance_endpoint(
    bid_id: str,
    request: Request,
    payload: Optional[EvaluateComplianceRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Run deterministic rule evaluation of all tender requirements against bidder evidence.
    Automatically triggers mock registry verification for tax/registration fields.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    auto_verify = payload.auto_verify if payload else True

    return evaluate_bid_compliance(
        db=db,
        bid_id=bid_id,
        user=current_user,
        auto_verify=auto_verify,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/bid/{bid_id}",
    response_model=BidComplianceSummaryResponse,
    summary="Get Bid Compliance Summary",
)
def get_compliance_summary_endpoint(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve requirement-level compliance breakdown and overall verdict for a bid.
    """
    return get_bid_compliance_summary(
        db=db,
        bid_id=bid_id,
        user=current_user,
    )


@router.get(
    "/bid/{bid_id}/requirement/{requirement_id}",
    response_model=ComplianceResultResponse,
    summary="Get Requirement Compliance Detail",
)
def get_requirement_compliance_endpoint(
    bid_id: str,
    requirement_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve detailed compliance verdict and supporting evidence citation for a single requirement.
    """
    return get_requirement_compliance_detail(
        db=db,
        bid_id=bid_id,
        requirement_id=requirement_id,
        user=current_user,
    )
