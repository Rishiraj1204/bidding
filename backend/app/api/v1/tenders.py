from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user, require_roles
from backend.app.models.tender import TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.tender import (
    TenderCreate,
    TenderListResponse,
    TenderResponse,
    TenderStatusUpdate,
    TenderUpdate,
)
from backend.app.services.tender_service import (
    create_tender,
    delete_tender,
    get_tender_by_id,
    get_tenders,
    update_tender,
    update_tender_status,
)

router = APIRouter()


@router.post(
    "",
    response_model=TenderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Tender",
)
def create_new_tender(
    tender_in: TenderCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.PROCUREMENT_OFFICER.value, UserRoleEnum.ADMIN.value)),
):
    """
    Create a new tender in DRAFT or initial state.
    Restricted to Procurement Officers and Admins.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return create_tender(
        db=db,
        tender_in=tender_in,
        creator=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "",
    response_model=TenderListResponse,
    summary="List Tenders with Search & Filters",
)
def list_tenders(
    search: Optional[str] = Query(None, description="Search keyword in title, number, or organization"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tender_status: Optional[TenderStatusEnum] = Query(None, alias="status", description="Filter by tender status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List tenders with keyword search, category, and status filters.
    Bidders see only published/open tenders; Officers/Admins see drafts.
    """
    return get_tenders(
        db=db,
        user=current_user,
        search=search,
        category=category,
        tender_status=tender_status,
        page=page,
        size=size,
    )


@router.get(
    "/{tender_id}",
    response_model=TenderResponse,
    summary="Get Tender Details",
)
def get_tender(
    tender_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve full details of a specific tender by UUID.
    """
    return get_tender_by_id(db=db, tender_id=tender_id, user=current_user)


@router.put(
    "/{tender_id}",
    response_model=TenderResponse,
    summary="Update Tender Information",
)
def update_tender_info(
    tender_id: str,
    tender_in: TenderUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.PROCUREMENT_OFFICER.value, UserRoleEnum.ADMIN.value)),
):
    """
    Update tender details, deadline, or metadata.
    Restricted to the creating Officer or Admins.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return update_tender(
        db=db,
        tender_id=tender_id,
        tender_in=tender_in,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.patch(
    "/{tender_id}/status",
    response_model=TenderResponse,
    summary="Update Tender Status Lifecycle",
)
def update_status(
    tender_id: str,
    status_in: TenderStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.PROCUREMENT_OFFICER.value, UserRoleEnum.ADMIN.value)),
):
    """
    Perform a lifecycle status transition on a tender (e.g. DRAFT -> PUBLISHED, PUBLISHED -> CLOSED).
    Enforces valid state transition rules.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return update_tender_status(
        db=db,
        tender_id=tender_id,
        new_status=status_in.status,
        user=current_user,
        reason=status_in.reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.delete(
    "/{tender_id}",
    summary="Delete Draft Tender",
)
def delete_tender_item(
    tender_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.PROCUREMENT_OFFICER.value, UserRoleEnum.ADMIN.value)),
):
    """
    Delete a tender in DRAFT status with no submitted bids.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return delete_tender(
        db=db,
        tender_id=tender_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
