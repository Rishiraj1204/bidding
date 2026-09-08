import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import or_, desc, func
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_user_roles
from backend.app.models.tender import Tender, TenderStatusEnum, TenderDocument, TenderRequirement
from backend.app.models.bid import Bid
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.tender import TenderCreate, TenderListResponse, TenderResponse, TenderUpdate
from backend.app.services.audit_service import log_audit_event

# Valid state transition mapping
VALID_TENDER_TRANSITIONS: Dict[TenderStatusEnum, Set[TenderStatusEnum]] = {
    TenderStatusEnum.DRAFT: {TenderStatusEnum.PUBLISHED, TenderStatusEnum.CANCELLED},
    TenderStatusEnum.PUBLISHED: {TenderStatusEnum.CLOSED, TenderStatusEnum.UNDER_EVALUATION, TenderStatusEnum.CANCELLED},
    TenderStatusEnum.CLOSED: {TenderStatusEnum.UNDER_EVALUATION, TenderStatusEnum.CANCELLED},
    TenderStatusEnum.UNDER_EVALUATION: {TenderStatusEnum.COMPLETED, TenderStatusEnum.CANCELLED},
    TenderStatusEnum.COMPLETED: set(),
    TenderStatusEnum.CANCELLED: set(),
}


def _tender_to_response(tender: Tender) -> TenderResponse:
    """Format Tender model into TenderResponse with counts."""
    return TenderResponse(
        id=tender.id,
        tender_number=tender.tender_number,
        title=tender.title,
        description=tender.description,
        organization=tender.organization,
        category=tender.category,
        submission_deadline=tender.submission_deadline,
        status=tender.status,
        created_by_id=tender.created_by_id,
        created_by_name=tender.created_by.full_name if tender.created_by else None,
        created_at=tender.created_at,
        updated_at=tender.updated_at,
        documents_count=len(tender.documents) if tender.documents else 0,
        requirements_count=len(tender.requirements) if tender.requirements else 0,
        bids_count=len(tender.bids) if tender.bids else 0,
    )


def create_tender(
    db: Session,
    tender_in: TenderCreate,
    creator: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> TenderResponse:
    """Create a new tender."""
    # Check duplicate tender_number
    existing = db.query(Tender).filter(Tender.tender_number == tender_in.tender_number.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tender with number '{tender_in.tender_number}' already exists.",
        )

    # Validate deadline is in the future
    now_utc = datetime.now(timezone.utc)
    deadline = tender_in.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission deadline must be set to a future date and time.",
        )

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=tender_in.tender_number.strip(),
        title=tender_in.title.strip(),
        description=tender_in.description.strip() if tender_in.description else None,
        organization=tender_in.organization.strip(),
        category=tender_in.category.strip() if tender_in.category else None,
        submission_deadline=deadline,
        status=tender_in.status,
        created_by_id=creator.id,
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)

    # Log audit event
    log_audit_event(
        db=db,
        action="TENDER_CREATED",
        resource_type="tender",
        resource_id=tender.id,
        actor_id=creator.id,
        actor_email=creator.email,
        new_state={"tender_number": tender.tender_number, "status": tender.status.value},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _tender_to_response(tender)


def get_tenders(
    db: Session,
    user: User,
    search: Optional[str] = None,
    category: Optional[str] = None,
    tender_status: Optional[TenderStatusEnum] = None,
    page: int = 1,
    size: int = 20,
) -> TenderListResponse:
    """List tenders with search, filters, RBAC visibility, and pagination."""
    query = db.query(Tender).options(
        selectinload(Tender.created_by),
        selectinload(Tender.documents),
        selectinload(Tender.requirements),
        selectinload(Tender.bids),
    )

    user_roles = get_user_roles(user)
    is_admin_or_officer = user.is_superuser or bool(user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER"}))

    # Bidders & Reviewers cannot see DRAFT tenders by default
    if not is_admin_or_officer:
        query = query.filter(Tender.status != TenderStatusEnum.DRAFT)

    # Apply filters
    if tender_status:
        query = query.filter(Tender.status == tender_status)

    if category:
        query = query.filter(Tender.category.ilike(f"%{category.strip()}%"))

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Tender.title.ilike(search_term),
                Tender.tender_number.ilike(search_term),
                Tender.organization.ilike(search_term),
                Tender.description.ilike(search_term),
            )
        )

    total = query.count()
    offset = (page - 1) * size
    tenders = query.order_by(desc(Tender.created_at)).offset(offset).limit(size).all()
    pages = math.ceil(total / size) if size > 0 else 1

    items = [_tender_to_response(t) for t in tenders]
    return TenderListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


def get_tender_by_id(db: Session, tender_id: str, user: User) -> TenderResponse:
    """Fetch tender details by ID with visibility checks."""
    tender = (
        db.query(Tender)
        .options(
            selectinload(Tender.created_by),
            selectinload(Tender.documents),
            selectinload(Tender.requirements),
            selectinload(Tender.bids),
        )
        .filter(Tender.id == tender_id)
        .first()
    )

    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found",
        )

    # Check draft visibility
    user_roles = get_user_roles(user)
    is_admin_or_officer = user.is_superuser or bool(user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER"}))
    if tender.status == TenderStatusEnum.DRAFT and not is_admin_or_officer and tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tender is currently in draft and not accessible to public bidders.",
        )

    return _tender_to_response(tender)


def update_tender(
    db: Session,
    tender_id: str,
    tender_in: TenderUpdate,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> TenderResponse:
    """Update tender fields with ownership and lifecycle rules."""
    tender = (
        db.query(Tender)
        .options(
            selectinload(Tender.created_by),
            selectinload(Tender.documents),
            selectinload(Tender.requirements),
            selectinload(Tender.bids),
        )
        .filter(Tender.id == tender_id)
        .first()
    )

    if not tender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    # Authorization check
    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles
    if not is_admin and tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to modify this tender.",
        )

    # Terminal state check
    if tender.status in {TenderStatusEnum.COMPLETED, TenderStatusEnum.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify a tender in {tender.status.value} status.",
        )

    prev_state = {
        "title": tender.title,
        "organization": tender.organization,
        "deadline": str(tender.submission_deadline),
        "status": tender.status.value,
    }

    if tender_in.title is not None:
        tender.title = tender_in.title.strip()
    if tender_in.description is not None:
        tender.description = tender_in.description.strip()
    if tender_in.organization is not None:
        tender.organization = tender_in.organization.strip()
    if tender_in.category is not None:
        tender.category = tender_in.category.strip()

    if tender_in.submission_deadline is not None:
        deadline = tender_in.submission_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Submission deadline must be a future date.",
            )
        tender.submission_deadline = deadline

    if tender_in.status is not None and tender_in.status != tender.status:
        # Validate transition
        allowed_transitions = VALID_TENDER_TRANSITIONS.get(tender.status, set())
        if tender_in.status not in allowed_transitions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {tender.status.value} to {tender_in.status.value}.",
            )
        tender.status = tender_in.status

    db.commit()
    db.refresh(tender)

    log_audit_event(
        db=db,
        action="TENDER_UPDATED",
        resource_type="tender",
        resource_id=tender.id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state=prev_state,
        new_state={"status": tender.status.value, "title": tender.title},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _tender_to_response(tender)


def update_tender_status(
    db: Session,
    tender_id: str,
    new_status: TenderStatusEnum,
    user: User,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> TenderResponse:
    """Transition tender status adhering to lifecycle rules."""
    tender = (
        db.query(Tender)
        .options(
            selectinload(Tender.created_by),
            selectinload(Tender.documents),
            selectinload(Tender.requirements),
            selectinload(Tender.bids),
        )
        .filter(Tender.id == tender_id)
        .first()
    )

    if not tender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles
    if not is_admin and tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this tender's status.",
        )

    if new_status == tender.status:
        return _tender_to_response(tender)

    allowed_transitions = VALID_TENDER_TRANSITIONS.get(tender.status, set())
    if new_status not in allowed_transitions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition tender from {tender.status.value} to {new_status.value}. Valid transitions: {[s.value for s in allowed_transitions]}",
        )

    prev_status = tender.status.value
    tender.status = new_status
    db.commit()
    db.refresh(tender)

    log_audit_event(
        db=db,
        action="TENDER_STATUS_CHANGED",
        resource_type="tender",
        resource_id=tender.id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"status": prev_status},
        new_state={"status": new_status.value, "reason": reason},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _tender_to_response(tender)


def delete_tender(
    db: Session,
    tender_id: str,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """Delete a tender (Only allowed in DRAFT status or by Admin)."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles

    if not is_admin and tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this tender.",
        )

    if not is_admin and tender.status != TenderStatusEnum.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only DRAFT tenders can be deleted. Current status is {tender.status.value}.",
        )

    # Check if any bids have been submitted
    bid_count = db.query(Bid).filter(Bid.tender_id == tender.id).count()
    if bid_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete tender with associated bidder submissions.",
        )

    tender_num = tender.tender_number
    db.delete(tender)
    db.commit()

    log_audit_event(
        db=db,
        action="TENDER_DELETED",
        resource_type="tender",
        resource_id=tender_id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"tender_number": tender_num},
        new_state=None,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": f"Tender {tender_num} deleted successfully", "status": "success"}
