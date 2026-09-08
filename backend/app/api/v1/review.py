from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.review import (
    AssignReviewTaskRequest,
    ReviewDecisionCreate,
    ReviewTaskListResponse,
    ReviewTaskResponse,
)
from backend.app.services.review_service import (
    assign_review_task,
    get_review_task_detail,
    list_review_tasks,
    submit_review_decision,
)

router = APIRouter()


@router.get(
    "/tasks",
    response_model=ReviewTaskListResponse,
    summary="List Review Queue Tasks",
)
def list_review_tasks_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    bid_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List all pending and active human review tasks.
    Accessible to authorized staff (Reviewers, Procurement Officers, Admins).
    """
    return list_review_tasks(
        db=db,
        user=current_user,
        status_filter=status_filter,
        bid_id=bid_id,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=ReviewTaskResponse,
    summary="Get Review Task Detail",
)
def get_review_task_endpoint(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve inspection view for a single review task including evidence citations and decision history.
    """
    return get_review_task_detail(
        db=db,
        task_id=task_id,
        user=current_user,
    )


@router.post(
    "/tasks/{task_id}/assign",
    response_model=ReviewTaskResponse,
    summary="Assign Review Task",
)
def assign_review_task_endpoint(
    task_id: str,
    payload: Optional[AssignReviewTaskRequest] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Assign a review task to a designated reviewer or self-assign.
    Prevents assignment to the bid owner.
    """
    ip_address = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    assigned_to_id = payload.assigned_to_id if payload else None

    return assign_review_task(
        db=db,
        task_id=task_id,
        assigned_to_id=assigned_to_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/tasks/{task_id}/decision",
    response_model=ReviewTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Human Review Decision",
)
def submit_decision_endpoint(
    task_id: str,
    payload: ReviewDecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Submit a human review decision (Approve, Reject, Override) with mandatory justification.
    Strictly forbids self-approval/review by the bid owner.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return submit_review_decision(
        db=db,
        task_id=task_id,
        decision_data=payload,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
