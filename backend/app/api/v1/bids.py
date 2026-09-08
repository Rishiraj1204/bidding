from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user, require_roles
from backend.app.models.bid import BidStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.bid import (
    BidCreate,
    BidListResponse,
    BidResponse,
    BidStatusUpdate,
    BidUpdate,
)
from backend.app.services.bid_service import (
    create_bid,
    get_bid_by_id,
    get_bids,
    submit_bid,
    update_bid,
    update_bid_status,
    withdraw_bid,
)

router = APIRouter()


@router.post(
    "",
    response_model=BidResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Bid Submission Draft",
)
def create_new_bid(
    bid_in: BidCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.BIDDER.value, UserRoleEnum.ADMIN.value)),
):
    """
    Create a new draft bid against a published tender.
    Bidder identity is derived securely from the authenticated token.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return create_bid(
        db=db,
        bid_in=bid_in,
        bidder=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "",
    response_model=BidListResponse,
    summary="List Bids (RBAC Isolated)",
)
def list_bids(
    tender_id: Optional[str] = Query(None, description="Filter bids by tender ID"),
    bid_status: Optional[BidStatusEnum] = Query(None, alias="status", description="Filter by bid status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List bids. Bidders can only see their own bids; Officers/Admins/Reviewers see tender submissions.
    """
    return get_bids(
        db=db,
        user=current_user,
        tender_id=tender_id,
        bid_status=bid_status,
        page=page,
        size=size,
    )


@router.get(
    "/{bid_id}",
    response_model=BidResponse,
    summary="Get Bid Details",
)
def get_bid(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Fetch bid details with strict IDOR verification for bidders.
    """
    return get_bid_by_id(db=db, bid_id=bid_id, user=current_user)


@router.put(
    "/{bid_id}",
    response_model=BidResponse,
    summary="Update Draft Bid",
)
def update_draft_bid(
    bid_id: str,
    bid_in: BidUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update notes or metadata of a DRAFT bid before submission deadline.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return update_bid(
        db=db,
        bid_id=bid_id,
        bid_in=bid_in,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/{bid_id}/submit",
    response_model=BidResponse,
    summary="Submit Bid for Evaluation",
)
def submit_bid_endpoint(
    bid_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Formally submit a draft bid against an active tender before the deadline.
    Locks further modifications.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return submit_bid(
        db=db,
        bid_id=bid_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/{bid_id}/withdraw",
    response_model=BidResponse,
    summary="Withdraw Bid Submission",
)
def withdraw_bid_endpoint(
    bid_id: str,
    request: Request,
    reason: Optional[str] = Query(None, description="Reason for withdrawal"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Withdraw a draft or submitted bid before review evaluation.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return withdraw_bid(
        db=db,
        bid_id=bid_id,
        user=current_user,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.patch(
    "/{bid_id}/status",
    response_model=BidResponse,
    summary="Update Bid Evaluation Status",
)
def update_status_endpoint(
    bid_id: str,
    status_in: BidStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRoleEnum.PROCUREMENT_OFFICER.value,
        UserRoleEnum.ADMIN.value,
        UserRoleEnum.REVIEWER.value,
    )),
):
    """
    Transition bid status during review and evaluation stages.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return update_bid_status(
        db=db,
        bid_id=bid_id,
        new_status=status_in.status,
        user=current_user,
        reason=status_in.reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
