import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.compliance.engine import evaluate_requirement_against_evidence
from backend.app.core.deps import get_user_roles
from backend.app.models.bid import Bid, BidDocument
from backend.app.models.compliance import (
    ComplianceResult,
    ComplianceStatusEnum,
    VerificationRecord,
    VerificationStatusEnum,
)
from backend.app.models.review import ReviewStatusEnum, ReviewTask

from backend.app.models.document_extraction import Evidence
from backend.app.models.tender import Tender, TenderRequirement
from backend.app.models.user import User
from backend.app.schemas.compliance import (
    BidComplianceSummaryResponse,
    ComplianceResultResponse,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.verification.provider import get_verification_provider


def _check_bid_access(bid: Bid, user: User) -> None:
    """Validate user has permission to access compliance records for this bid."""
    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )
    if not is_staff and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view or evaluate compliance for this bid.",
        )


def _result_to_response(res: ComplianceResult) -> ComplianceResultResponse:
    req = res.requirement
    ev = res.evidence
    doc = ev.bid_document if ev else None
    
    # Get latest verification record if present
    v_rec = res.verification_records[-1] if res.verification_records else None

    return ComplianceResultResponse(
        id=res.id,
        bid_id=res.bid_id,
        requirement_id=res.requirement_id,
        requirement_text=req.requirement_text if req else "Requirement",
        requirement_category=req.category.value if req and hasattr(req.category, "value") else "OTHER",
        mandatory=req.mandatory if req else True,
        parameter=req.parameter if req else None,
        operator=req.operator if req else None,
        threshold_value=req.threshold_value if req else None,
        unit=req.unit if req else None,
        status=res.status,
        reason=res.reason,
        confidence=res.confidence,
        evaluated_by=res.evaluated_by,
        evidence_id=res.evidence_id,
        extracted_value=ev.extracted_value if ev else None,
        normalized_value=ev.normalized_value if ev else None,
        source_document_filename=doc.filename if doc else None,
        source_page=ev.page_number if ev else (req.source_page if req else None),
        source_snippet=ev.snippet_text if ev else None,
        verification_status=v_rec.status if v_rec else None,
        is_mock_verification=v_rec.is_mock if v_rec else None,
        created_at=res.created_at,
    )


def evaluate_bid_compliance(
    db: Session,
    bid_id: str,
    user: User,
    auto_verify: bool = True,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidComplianceSummaryResponse:
    """
    Evaluate deterministic compliance for all tender requirements against bidder evidence.
    Safety: Never marks compliant without grounded supporting evidence.
    """
    # 1. Fetch bid and tender
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender).selectinload(Tender.requirements),
            selectinload(Bid.documents).selectinload(BidDocument.evidence_records),
        )
        .filter(Bid.id == bid_id)
        .first()
    )
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    requirements: List[TenderRequirement] = bid.tender.requirements if bid.tender else []
    
    # 2. Collect all evidence records for this bid
    all_evidence: List[Evidence] = []
    for doc in bid.documents:
        for ev in doc.evidence_records:
            all_evidence.append(ev)

    # 3. Clean existing compliance results for idempotent evaluation
    existing_results = db.query(ComplianceResult).filter(ComplianceResult.bid_id == bid.id).all()
    for er in existing_results:
        db.delete(er)
    db.flush()

    persisted_results: List[ComplianceResult] = []
    v_provider = get_verification_provider()

    # 4. Evaluate each requirement
    for req in requirements:
        eval_outcome = evaluate_requirement_against_evidence(req, all_evidence)

        res_record = ComplianceResult(
            id=str(uuid.uuid4()),
            bid_id=bid.id,
            requirement_id=req.id,
            evidence_id=eval_outcome.matched_evidence_id,
            status=eval_outcome.status,
            reason=eval_outcome.reason,
            confidence=eval_outcome.confidence,
            evaluated_by="RULE_ENGINE",
        )
        db.add(res_record)
        db.flush()

        # 5. Auto-trigger registry verification if identifier is present
        if auto_verify and eval_outcome.matched_evidence_id and eval_outcome.normalized_value:
            param_lower = (req.parameter or "").lower()
            val_clean = eval_outcome.normalized_value.strip()

            v_type = None
            if "gst" in param_lower or (req.category and "TAX" in str(req.category)):
                v_type = "GST"
            elif "pan" in param_lower:
                v_type = "PAN"
            elif "msme" in param_lower or "udyam" in param_lower:
                v_type = "MSME"

            if v_type:
                v_res = v_provider.verify(verification_type=v_type, identifier=val_clean)
                v_rec = VerificationRecord(
                    id=str(uuid.uuid4()),
                    bid_id=bid.id,
                    compliance_result_id=res_record.id,
                    verification_type=v_type,
                    provider_name=v_res.provider_name,
                    is_mock=v_res.is_mock,
                    status=v_res.status,
                    reference_id=v_res.reference_id,
                    response_payload=v_res.summary,
                    error_message=v_res.error_message,
                )
                db.add(v_rec)

                # If verification failed on mandatory tax/registry identifier, update compliance status
                if v_res.status in [VerificationStatusEnum.FAILED, VerificationStatusEnum.MISMATCH]:
                    res_record.status = ComplianceStatusEnum.NON_COMPLIANT if req.mandatory else ComplianceStatusEnum.NEEDS_REVIEW
                    res_record.reason = f"Verification failed ({v_res.provider_name}): {v_res.error_message or 'Invalid identifier in registry records.'}"

        # If result requires human review, create a ReviewTask in the review queue
        if res_record.status == ComplianceStatusEnum.NEEDS_REVIEW:
            review_task = ReviewTask(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                compliance_result_id=res_record.id,
                trigger_reason=res_record.reason or "Evaluation requires human reviewer verification.",
                status=ReviewStatusEnum.PENDING,
            )
            db.add(review_task)

        persisted_results.append(res_record)


    db.commit()

    # 6. Audit Logging & Notification
    log_audit_event(
        db=db,
        action="BID_COMPLIANCE_EVALUATED",
        resource_type="bid_compliance",
        resource_id=bid.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "bid_id": bid.id,
            "tender_id": bid.tender_id,
            "total_requirements": len(requirements),
            "results_count": len(persisted_results),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    from backend.app.services.notification_service import create_notification
    create_notification(
        db=db,
        user_id=bid.bidder_id,
        title="Compliance Evaluation Completed",
        message=f"Compliance evaluation for bid {bid.bid_number} has completed with {len(persisted_results)} requirement checks.",
        notification_type="INFO",
        related_resource_type="bid",
        related_resource_id=bid.id,
    )

    return get_bid_compliance_summary(db=db, bid_id=bid.id, user=user)


def get_bid_compliance_summary(
    db: Session,
    bid_id: str,
    user: User,
) -> BidComplianceSummaryResponse:
    """Retrieve full requirement-level compliance breakdown and overall verdict for a bid."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    results = (
        db.query(ComplianceResult)
        .options(
            selectinload(ComplianceResult.requirement),
            selectinload(ComplianceResult.evidence).selectinload(Evidence.bid_document),
            selectinload(ComplianceResult.verification_records),
        )
        .filter(ComplianceResult.bid_id == bid.id)
        .all()
    )

    total = len(results)
    compliant_count = sum(1 for r in results if r.status == ComplianceStatusEnum.COMPLIANT)
    non_compliant_count = sum(1 for r in results if r.status == ComplianceStatusEnum.NON_COMPLIANT)
    needs_review_count = sum(1 for r in results if r.status == ComplianceStatusEnum.NEEDS_REVIEW)
    not_applicable_count = sum(1 for r in results if r.status == ComplianceStatusEnum.NOT_APPLICABLE)

    # Check mandatory requirements
    mandatory_results = [r for r in results if r.requirement and r.requirement.mandatory]
    mandatory_passed = all(r.status == ComplianceStatusEnum.COMPLIANT for r in mandatory_results) if mandatory_results else (total > 0)

    # Overall verdict
    if total == 0:
        overall_status = ComplianceStatusEnum.NEEDS_REVIEW
    elif any(r.status == ComplianceStatusEnum.NON_COMPLIANT for r in mandatory_results):
        overall_status = ComplianceStatusEnum.NON_COMPLIANT
    elif any(r.status == ComplianceStatusEnum.NEEDS_REVIEW for r in results):
        overall_status = ComplianceStatusEnum.NEEDS_REVIEW
    elif compliant_count + not_applicable_count == total:
        overall_status = ComplianceStatusEnum.COMPLIANT
    else:
        overall_status = ComplianceStatusEnum.NEEDS_REVIEW

    response_items = [_result_to_response(r) for r in results]

    return BidComplianceSummaryResponse(
        bid_id=bid.id,
        overall_status=overall_status,
        total_requirements=total,
        compliant_count=compliant_count,
        non_compliant_count=non_compliant_count,
        needs_review_count=needs_review_count,
        not_applicable_count=not_applicable_count,
        mandatory_passed=mandatory_passed,
        results=response_items,
    )


def get_requirement_compliance_detail(
    db: Session,
    bid_id: str,
    requirement_id: str,
    user: User,
) -> ComplianceResultResponse:
    """Retrieve compliance verdict for a specific tender requirement."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    res = (
        db.query(ComplianceResult)
        .options(
            selectinload(ComplianceResult.requirement),
            selectinload(ComplianceResult.evidence).selectinload(Evidence.bid_document),
            selectinload(ComplianceResult.verification_records),
        )
        .filter(ComplianceResult.bid_id == bid.id, ComplianceResult.requirement_id == requirement_id)
        .first()
    )
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compliance evaluation found for this requirement. Run evaluation first.",
        )

    return _result_to_response(res)
