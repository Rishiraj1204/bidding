import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_user_roles
from backend.app.models.bid import Bid
from backend.app.models.compliance import ComplianceResult, ComplianceStatusEnum
from backend.app.models.document_extraction import Evidence
from backend.app.models.review import ReviewDecision, ReviewStatusEnum, ReviewTask
from backend.app.models.tender import Tender, TenderRequirement
from backend.app.models.user import User
from backend.app.schemas.review import (
    ReviewDecisionCreate,
    ReviewDecisionResponse,
    ReviewTaskListResponse,
    ReviewTaskResponse,
)
from backend.app.services.audit_service import log_audit_event


def _check_reviewer_access(user: User, action_name: str = "review tasks") -> None:
    """Ensure user has a staff role permitted to inspect or act on review tasks."""
    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )
    if not is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: You do not have permission to access {action_name}.",
        )


def _check_decision_permission(user: User, bid: Bid) -> None:
    """Ensure user can make decisions and prevent self-review/approval conflicts."""
    user_roles = get_user_roles(user)
    can_decide = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER"})
    )
    if not can_decide:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permissions to submit human review decisions.",
        )

    # STRICT SECURITY: Prevent bidder from approving or reviewing own bid
    if bid.bidder_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-Review Conflict: Bidders are strictly prohibited from reviewing or approving their own bid submissions.",
        )


def _task_to_response(task: ReviewTask) -> ReviewTaskResponse:
    bid = task.bid
    tender = bid.tender if bid else None
    comp_res = task.compliance_result
    req = comp_res.requirement if comp_res else None
    ev = comp_res.evidence if comp_res else None
    doc = ev.bid_document if ev else None

    decision_items = [
        ReviewDecisionResponse(
            id=d.id,
            task_id=d.task_id,
            reviewer_id=d.reviewer_id,
            reviewer_name=d.reviewer.full_name if d.reviewer else None,
            original_decision=d.original_decision,
            new_decision=d.new_decision,
            justification=d.justification,
            comments=d.comments,
            created_at=d.created_at,
        )
        for d in (task.decisions or [])
    ]

    original_decision = "NEEDS_REVIEW"
    if comp_res:
        original_decision = comp_res.status.value if hasattr(comp_res.status, "value") else str(comp_res.status)

    return ReviewTaskResponse(
        id=task.id,
        bid_id=task.bid_id,
        bid_number=bid.bid_number if bid else None,
        tender_id=tender.id if tender else None,
        tender_title=tender.title if tender else None,
        compliance_result_id=task.compliance_result_id,
        requirement_id=req.id if req else None,
        requirement_text=req.requirement_text if req else None,
        requirement_category=req.category.value if req and hasattr(req.category, "value") else "OTHER",
        mandatory=req.mandatory if req else True,
        status=task.status,
        trigger_reason=task.trigger_reason,
        assigned_to_id=task.assigned_to_id,
        assigned_to_name=task.assigned_to.full_name if task.assigned_to else None,
        original_decision=original_decision,
        current_status=comp_res.status.value if comp_res and hasattr(comp_res.status, "value") else "NEEDS_REVIEW",
        extracted_value=ev.extracted_value if ev else None,
        normalized_value=ev.normalized_value if ev else None,
        evidence_snippet=ev.snippet_text if ev else None,
        source_document_filename=doc.filename if doc else None,
        source_page=ev.page_number if ev else (req.source_page if req else None),
        decisions=decision_items,
        created_at=task.created_at,
    )


def list_review_tasks(
    db: Session,
    user: User,
    status_filter: Optional[str] = None,
    bid_id: Optional[str] = None,
) -> ReviewTaskListResponse:
    """Retrieve list of human review tasks in the review queue."""
    _check_reviewer_access(user, "review tasks queue")

    query = (
        db.query(ReviewTask)
        .options(
            selectinload(ReviewTask.bid).selectinload(Bid.tender),
            selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.requirement),
            selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.evidence).selectinload(Evidence.bid_document),
            selectinload(ReviewTask.assigned_to),
            selectinload(ReviewTask.decisions).selectinload(ReviewDecision.reviewer),
        )
    )

    if status_filter:
        query = query.filter(ReviewTask.status == status_filter)
    if bid_id:
        query = query.filter(ReviewTask.bid_id == bid_id)

    tasks = query.order_by(ReviewTask.created_at.desc()).all()
    items = [_task_to_response(t) for t in tasks]

    return ReviewTaskListResponse(
        items=items,
        total=len(items),
    )


def get_review_task_detail(
    db: Session,
    task_id: str,
    user: User,
) -> ReviewTaskResponse:
    """Retrieve detailed inspection view of a single review task."""
    _check_reviewer_access(user, "review task details")

    task = (
        db.query(ReviewTask)
        .options(
            selectinload(ReviewTask.bid).selectinload(Bid.tender),
            selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.requirement),
            selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.evidence).selectinload(Evidence.bid_document),
            selectinload(ReviewTask.assigned_to),
            selectinload(ReviewTask.decisions).selectinload(ReviewDecision.reviewer),
        )
        .filter(ReviewTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review task not found")

    return _task_to_response(task)


def assign_review_task(
    db: Session,
    task_id: str,
    assigned_to_id: Optional[str],
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> ReviewTaskResponse:
    """Assign a review task to a specific reviewer or self-assign."""
    task = (
        db.query(ReviewTask)
        .options(
            selectinload(ReviewTask.bid),
            selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.requirement),
        )
        .filter(ReviewTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review task not found")

    _check_decision_permission(user, task.bid)

    target_user_id = assigned_to_id or user.id
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned user not found")

    if task.bid.bidder_id == target_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conflict of interest: Task cannot be assigned to the bid owner.",
        )

    task.assigned_to_id = target_user.id
    task.status = ReviewStatusEnum.IN_PROGRESS
    db.commit()
    db.refresh(task)

    log_audit_event(
        db=db,
        action="REVIEW_ASSIGNED",
        resource_type="review_task",
        resource_id=task.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "task_id": task.id,
            "assigned_to_id": target_user.id,
            "assigned_to_email": target_user.email,
            "status": task.status.value,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    from backend.app.services.notification_service import create_notification
    create_notification(
        db=db,
        user_id=target_user.id,
        title="Review Task Assigned",
        message=f"You have been assigned a compliance review task for bid {task.bid.bid_number}.",
        notification_type="ACTION_REQUIRED",
        related_resource_type="review_task",
        related_resource_id=task.id,
    )

    return get_review_task_detail(db=db, task_id=task.id, user=user)


def submit_review_decision(
    db: Session,
    task_id: str,
    decision_data: ReviewDecisionCreate,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> ReviewTaskResponse:
    """
    Submit a human review decision (Approve, Reject, Override) with mandatory justification.
    Preserves historical AI/rule evaluation without overwriting historical records.
    """
    task = (
        db.query(ReviewTask)
        .options(
            selectinload(ReviewTask.bid),
            selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.requirement),
        )
        .filter(ReviewTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review task not found")

    _check_decision_permission(user, task.bid)

    comp_res = task.compliance_result
    if not comp_res:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Associated compliance result not found")

    justification_clean = decision_data.justification.strip()
    if len(justification_clean) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mandatory justification explanation required (minimum 5 characters).",
        )

    original_decision = comp_res.status.value if hasattr(comp_res.status, "value") else str(comp_res.status)
    new_decision_upper = decision_data.new_decision.strip().upper()

    # Map decision string to ComplianceStatusEnum
    if new_decision_upper in ["COMPLIANT", "APPROVED", "PASS"]:
        new_status = ComplianceStatusEnum.COMPLIANT
        task_status = ReviewStatusEnum.APPROVED
    elif new_decision_upper in ["NON_COMPLIANT", "REJECTED", "FAIL"]:
        new_status = ComplianceStatusEnum.NON_COMPLIANT
        task_status = ReviewStatusEnum.REJECTED
    elif new_decision_upper in ["CLARIFICATION_REQUIRED", "NEEDS_CLARIFICATION"]:
        new_status = ComplianceStatusEnum.NEEDS_REVIEW
        task_status = ReviewStatusEnum.CLARIFICATION_REQUIRED
    else:
        new_status = ComplianceStatusEnum.NEEDS_REVIEW
        task_status = ReviewStatusEnum.COMPLETED

    # 1. Create immutable ReviewDecision record
    decision_record = ReviewDecision(
        id=str(uuid.uuid4()),
        task_id=task.id,
        reviewer_id=user.id,
        original_decision=original_decision,
        new_decision=new_status.value,
        justification=justification_clean,
        comments=decision_data.comments,
    )
    db.add(decision_record)

    # 2. Update Compliance Result with human verdict and citation
    is_override = (original_decision != new_status.value)
    comp_res.status = new_status
    comp_res.evaluated_by = "HUMAN_REVIEW"
    comp_res.reason = f"Human Review Decision by {user.full_name or user.email}: {justification_clean} (Original rule decision: {original_decision})"

    # 3. Update Review Task lifecycle status
    task.status = task_status
    task.assigned_to_id = user.id

    db.commit()

    # 4. Audit Logging
    log_audit_event(
        db=db,
        action="REVIEW_DECISION",
        resource_type="review_task",
        resource_id=task.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "task_id": task.id,
            "original_decision": original_decision,
            "new_decision": new_status.value,
            "justification": justification_clean,
            "status": task.status.value,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if is_override:
        log_audit_event(
            db=db,
            action="REVIEW_OVERRIDE",
            resource_type="compliance_result",
            resource_id=comp_res.id,
            actor_id=user.id,
            actor_email=user.email,
            new_state={
                "compliance_result_id": comp_res.id,
                "original_status": original_decision,
                "overridden_status": new_status.value,
                "justification": justification_clean,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    from backend.app.services.notification_service import create_notification
    create_notification(
        db=db,
        user_id=task.bid.bidder_id,
        title="Review Decision Submitted",
        message=f"A human reviewer has updated requirement evaluation for bid {task.bid.bid_number} to {new_status.value}.",
        notification_type="INFO",
        related_resource_type="bid",
        related_resource_id=task.bid_id,
    )

    return get_review_task_detail(db=db, task_id=task.id, user=user)
