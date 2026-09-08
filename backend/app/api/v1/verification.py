from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.verification import (
    BidVerificationListResponse,
    TriggerVerificationRequest,
    VerificationRecordResponse,
)
from backend.app.services.verification_service import (
    get_bid_verification_records,
    get_verification_record_detail,
    trigger_bid_verification,
)

router = APIRouter()


@router.post(
    "/bid/{bid_id}",
    response_model=VerificationRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger External Registry Verification",
)
def trigger_verification_endpoint(
    bid_id: str,
    payload: TriggerVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Trigger external registry verification (GST, PAN, MSME, Registry) for an identifier.
    Clearly tags the outcome with is_mock=True in local/test environments.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return trigger_bid_verification(
        db=db,
        bid_id=bid_id,
        verification_type=payload.verification_type,
        identifier=payload.identifier,
        compliance_result_id=payload.compliance_result_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/bid/{bid_id}",
    response_model=BidVerificationListResponse,
    summary="List Verification Records for Bid",
)
def list_bid_verifications_endpoint(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve all verification records associated with a bid.
    """
    return get_bid_verification_records(
        db=db,
        bid_id=bid_id,
        user=current_user,
    )


@router.get(
    "/{record_id}",
    response_model=VerificationRecordResponse,
    summary="Get Verification Record Detail",
)
def get_verification_detail_endpoint(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve details of a specific external verification record.
    """
    return get_verification_record_detail(
        db=db,
        record_id=record_id,
        user=current_user,
    )
