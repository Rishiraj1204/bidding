import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_user_roles
from backend.app.models.bid import Bid, BidStatusEnum, BidDocument
from backend.app.models.tender import Tender, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.bid import BidCreate, BidListResponse, BidResponse, BidUpdate
from backend.app.services.audit_service import log_audit_event


def _bid_to_response(bid: Bid) -> BidResponse:
    """Format Bid model into BidResponse with tender and bidder metadata."""
    return BidResponse(
        id=bid.id,
        tender_id=bid.tender_id,
        bidder_id=bid.bidder_id,
        bid_number=bid.bid_number,
        status=bid.status,
        submission_date=bid.submission_date,
        notes=bid.notes,
        created_at=bid.created_at,
        updated_at=bid.updated_at,
        tender_number=bid.tender.tender_number if bid.tender else None,
        tender_title=bid.tender.title if bid.tender else None,
        tender_organization=bid.tender.organization if bid.tender else None,
        tender_deadline=bid.tender.submission_deadline if bid.tender else None,
        tender_status=bid.tender.status if bid.tender else None,
        bidder_name=bid.bidder.full_name if bid.bidder else None,
        bidder_email=bid.bidder.email if bid.bidder else None,
        bidder_organization=bid.bidder.organization_name if bid.bidder else None,
        documents_count=len(bid.documents) if bid.documents else 0,
        compliance_status=bid.status.value,
    )


def create_bid(
    db: Session,
    bid_in: BidCreate,
    bidder: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidResponse:
    """Create a new draft bid for a published tender."""
    # 1. Fetch and validate tender
    tender = db.query(Tender).filter(Tender.id == bid_in.tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specified tender not found",
        )

    if tender.status != TenderStatusEnum.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bidding is closed or not permitted for tender in '{tender.status.value}' status.",
        )

    # 2. Check submission deadline
    now_utc = datetime.now(timezone.utc)
    deadline = tender.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender submission deadline has already expired.",
        )

    # 3. Check for existing active bid by this bidder
    existing_active_bid = (
        db.query(Bid)
        .filter(
            Bid.tender_id == tender.id,
            Bid.bidder_id == bidder.id,
            Bid.status != BidStatusEnum.WITHDRAWN,
        )
        .first()
    )
    if existing_active_bid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have an active bid ({existing_active_bid.bid_number}) for this tender.",
        )

    # 4. Generate bid number
    bid_number = bid_in.bid_number
    if not bid_number:
        year = datetime.now().year
        rand_suffix = random.randint(10000, 99999)
        bid_number = f"BID/{year}/{rand_suffix}"

    # Check unique bid_number
    existing_num = db.query(Bid).filter(Bid.bid_number == bid_number).first()
    if existing_num:
        bid_number = f"BID/{datetime.now().year}/{random.randint(100000, 999999)}"

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder.id,
        bid_number=bid_number,
        status=BidStatusEnum.DRAFT,
        notes=bid_in.notes.strip() if bid_in.notes else None,
    )
    db.add(bid)
    db.commit()
    db.refresh(bid)

    # Eager reload for response
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender),
            selectinload(Bid.bidder),
            selectinload(Bid.documents),
        )
        .filter(Bid.id == bid.id)
        .first()
    )

    log_audit_event(
        db=db,
        action="BID_CREATED",
        resource_type="bid",
        resource_id=bid.id,
        actor_id=bidder.id,
        actor_email=bidder.email,
        new_state={"bid_number": bid.bid_number, "tender_id": tender.id, "status": bid.status.value},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _bid_to_response(bid)


def get_bids(
    db: Session,
    user: User,
    tender_id: Optional[str] = None,
    bid_status: Optional[BidStatusEnum] = None,
    page: int = 1,
    size: int = 20,
) -> BidListResponse:
    """List bids with RBAC isolation and filters."""
    query = db.query(Bid).options(
        selectinload(Bid.tender),
        selectinload(Bid.bidder),
        selectinload(Bid.documents),
    )

    user_roles = get_user_roles(user)
    is_admin_or_officer = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    # Bidder can ONLY see their own bids
    if not is_admin_or_officer:
        query = query.filter(Bid.bidder_id == user.id)

    if tender_id:
        query = query.filter(Bid.tender_id == tender_id)

    if bid_status:
        query = query.filter(Bid.status == bid_status)

    total = query.count()
    offset = (page - 1) * size
    bids = query.order_by(desc(Bid.created_at)).offset(offset).limit(size).all()
    pages = math.ceil(total / size) if size > 0 else 1

    items = [_bid_to_response(b) for b in bids]
    return BidListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


def get_bid_by_id(db: Session, bid_id: str, user: User) -> BidResponse:
    """Retrieve bid by ID with ownership verification."""
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender),
            selectinload(Bid.bidder),
            selectinload(Bid.documents),
        )
        .filter(Bid.id == bid_id)
        .first()
    )

    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bid not found",
        )

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    # Enforce IDOR protection for Bidders
    if not is_staff and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to bid forbidden: you do not own this submission.",
        )

    return _bid_to_response(bid)


def update_bid(
    db: Session,
    bid_id: str,
    bid_in: BidUpdate,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidResponse:
    """Update draft bid notes before submission."""
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender),
            selectinload(Bid.bidder),
            selectinload(Bid.documents),
        )
        .filter(Bid.id == bid_id)
        .first()
    )

    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles
    if not is_admin and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to edit this bid.",
        )

    if bid.status != BidStatusEnum.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit bid in '{bid.status.value}' status. Only DRAFT bids can be modified.",
        )

    # Check deadline
    now_utc = datetime.now(timezone.utc)
    deadline = bid.tender.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender submission deadline has passed. Modifications are locked.",
        )

    prev_notes = bid.notes
    if bid_in.notes is not None:
        bid.notes = bid_in.notes.strip()

    db.commit()
    db.refresh(bid)

    log_audit_event(
        db=db,
        action="BID_UPDATED",
        resource_type="bid",
        resource_id=bid.id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"notes": prev_notes},
        new_state={"notes": bid.notes},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _bid_to_response(bid)


def submit_bid(
    db: Session,
    bid_id: str,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidResponse:
    """Submit a draft bid against a published tender."""
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender),
            selectinload(Bid.bidder),
            selectinload(Bid.documents),
        )
        .filter(Bid.id == bid_id)
        .first()
    )

    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles
    if not is_admin and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to submit this bid.",
        )

    if bid.status != BidStatusEnum.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bid has already been {bid.status.value}.",
        )

    # Validate tender status
    if bid.tender.status != TenderStatusEnum.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit bid. Tender is in '{bid.tender.status.value}' state.",
        )

    # Check deadline
    now_utc = datetime.now(timezone.utc)
    deadline = bid.tender.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission rejected: Tender deadline has passed.",
        )

    bid.status = BidStatusEnum.SUBMITTED
    bid.submission_date = now_utc
    db.commit()
    db.refresh(bid)

    log_audit_event(
        db=db,
        action="BID_SUBMITTED",
        resource_type="bid",
        resource_id=bid.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={"status": bid.status.value, "submission_date": str(bid.submission_date)},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _bid_to_response(bid)


def withdraw_bid(
    db: Session,
    bid_id: str,
    user: User,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidResponse:
    """Withdraw a bid before evaluation."""
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender),
            selectinload(Bid.bidder),
            selectinload(Bid.documents),
        )
        .filter(Bid.id == bid_id)
        .first()
    )

    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles
    if not is_admin and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to withdraw this bid.",
        )

    if bid.status not in {BidStatusEnum.DRAFT, BidStatusEnum.SUBMITTED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot withdraw bid in '{bid.status.value}' status.",
        )

    prev_status = bid.status.value
    bid.status = BidStatusEnum.WITHDRAWN
    db.commit()
    db.refresh(bid)

    log_audit_event(
        db=db,
        action="BID_WITHDRAWN",
        resource_type="bid",
        resource_id=bid.id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"status": prev_status},
        new_state={"status": bid.status.value, "reason": reason},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _bid_to_response(bid)


def update_bid_status(
    db: Session,
    bid_id: str,
    new_status: BidStatusEnum,
    user: User,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidResponse:
    """Update bid status during evaluation/review by Officers or Admins."""
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender),
            selectinload(Bid.bidder),
            selectinload(Bid.documents),
        )
        .filter(Bid.id == bid_id)
        .first()
    )

    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    prev_status = bid.status.value
    bid.status = new_status
    db.commit()
    db.refresh(bid)

    log_audit_event(
        db=db,
        action="BID_STATUS_CHANGED",
        resource_type="bid",
        resource_id=bid.id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"status": prev_status},
        new_state={"status": new_status.value, "reason": reason},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _bid_to_response(bid)
