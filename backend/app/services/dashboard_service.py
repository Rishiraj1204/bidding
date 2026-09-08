from typing import Any, Dict, List
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_user_roles
from backend.app.models.audit import AuditLog
from backend.app.models.bid import Bid, BidStatusEnum
from backend.app.models.compliance import ComplianceResult, ComplianceStatusEnum, VerificationRecord
from backend.app.models.report import Report
from backend.app.models.review import ReviewDecision, ReviewStatusEnum, ReviewTask
from backend.app.models.tender import Tender, TenderStatusEnum
from backend.app.models.user import Role, User
from backend.app.schemas.dashboard import DashboardSummaryResponse


def get_dashboard_summary(db: Session, user: User) -> DashboardSummaryResponse:
    """Compile role-tailored operational metrics, statistics, and recent activity items."""
    user_roles = get_user_roles(user)
    
    primary_role = "BIDDER"
    if user.is_superuser or "ADMIN" in user_roles:
        primary_role = "ADMIN"
    elif "PROCUREMENT_OFFICER" in user_roles:
        primary_role = "PROCUREMENT_OFFICER"
    elif "REVIEWER" in user_roles:
        primary_role = "REVIEWER"
    elif "AUDITOR" in user_roles:
        primary_role = "AUDITOR"

    metrics: Dict[str, Any] = {}
    status_breakdown: Dict[str, int] = {}
    recent_bids: List[Dict[str, Any]] = []
    recent_tenders: List[Dict[str, Any]] = []
    pending_tasks: List[Dict[str, Any]] = []
    recent_activity: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # 1. ADMIN Dashboard
    # -------------------------------------------------------------
    if primary_role == "ADMIN":
        total_users = db.query(User).count()
        total_tenders = db.query(Tender).count()
        total_bids = db.query(Bid).count()
        pending_rev = db.query(ReviewTask).filter(ReviewTask.status == ReviewStatusEnum.PENDING).count()
        total_reports = db.query(Report).count()
        total_verifications = db.query(VerificationRecord).count()

        # Tender status breakdown
        t_counts = db.query(Tender.status, func.count(Tender.id)).group_by(Tender.status).all()
        status_breakdown = {s.value if hasattr(s, "value") else str(s): c for s, c in t_counts}

        metrics = {
            "total_users": total_users,
            "total_tenders": total_tenders,
            "total_bids": total_bids,
            "pending_review_tasks": pending_rev,
            "total_reports": total_reports,
            "total_verifications": total_verifications,
        }

        # Recent Tenders
        tenders = db.query(Tender).order_by(Tender.created_at.desc()).limit(5).all()
        recent_tenders = [
            {
                "id": t.id,
                "title": t.title,
                "tender_number": t.tender_number,
                "status": t.status.value,
                "created_at": t.created_at.isoformat(),
            }
            for t in tenders
        ]

        # Recent Bids
        bids = (
            db.query(Bid)
            .options(selectinload(Bid.tender), selectinload(Bid.bidder))
            .order_by(Bid.created_at.desc())
            .limit(5)
            .all()
        )
        recent_bids = [
            {
                "id": b.id,
                "bid_number": b.bid_number,
                "tender_title": b.tender.title if b.tender else None,
                "bidder_name": b.bidder.full_name or b.bidder.organization_name if b.bidder else None,
                "status": b.status.value,
                "created_at": b.created_at.isoformat(),
            }
            for b in bids
        ]

        # Recent Audit logs
        audits = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(8).all()
        recent_activity = [
            {
                "id": a.id,
                "action": a.action,
                "actor_email": a.actor_email,
                "resource_type": a.resource_type,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in audits
        ]

    # -------------------------------------------------------------
    # 2. PROCUREMENT OFFICER Dashboard
    # -------------------------------------------------------------
    elif primary_role == "PROCUREMENT_OFFICER":
        my_tenders = db.query(Tender).filter(Tender.created_by_id == user.id).all()
        my_tender_ids = [t.id for t in my_tenders]

        published_t = sum(1 for t in my_tenders if t.status == TenderStatusEnum.PUBLISHED)
        closed_t = sum(1 for t in my_tenders if t.status == TenderStatusEnum.CLOSED)
        total_bids_received = db.query(Bid).filter(Bid.tender_id.in_(my_tender_ids)).count() if my_tender_ids else 0
        pending_reviews = (
            db.query(ReviewTask)
            .join(Bid, ReviewTask.bid_id == Bid.id)
            .filter(Bid.tender_id.in_(my_tender_ids), ReviewTask.status == ReviewStatusEnum.PENDING)
            .count()
            if my_tender_ids
            else 0
        )

        metrics = {
            "my_tenders_total": len(my_tenders),
            "published_tenders": published_t,
            "closed_tenders": closed_t,
            "bids_received": total_bids_received,
            "pending_reviews": pending_reviews,
        }

        # Recent Tenders
        recent_tenders = [
            {
                "id": t.id,
                "title": t.title,
                "tender_number": t.tender_number,
                "status": t.status.value,
                "created_at": t.created_at.isoformat(),
            }
            for t in my_tenders[:5]
        ]

        # Recent Bids for officer tenders
        if my_tender_ids:
            bids = (
                db.query(Bid)
                .options(selectinload(Bid.tender), selectinload(Bid.bidder))
                .filter(Bid.tender_id.in_(my_tender_ids))
                .order_by(Bid.created_at.desc())
                .limit(5)
                .all()
            )
            recent_bids = [
                {
                    "id": b.id,
                    "bid_number": b.bid_number,
                    "tender_title": b.tender.title if b.tender else None,
                    "bidder_name": b.bidder.full_name or b.bidder.organization_name if b.bidder else None,
                    "status": b.status.value,
                    "created_at": b.created_at.isoformat(),
                }
                for b in bids
            ]

    # -------------------------------------------------------------
    # 3. BIDDER Dashboard
    # -------------------------------------------------------------
    elif primary_role == "BIDDER":
        my_bids = (
            db.query(Bid)
            .options(selectinload(Bid.tender), selectinload(Bid.compliance_results))
            .filter(Bid.bidder_id == user.id)
            .order_by(Bid.created_at.desc())
            .all()
        )

        draft_c = sum(1 for b in my_bids if b.status == BidStatusEnum.DRAFT)
        submitted_c = sum(1 for b in my_bids if b.status == BidStatusEnum.SUBMITTED)
        under_review_c = sum(1 for b in my_bids if b.status == BidStatusEnum.UNDER_REVIEW)
        finalized_c = sum(1 for b in my_bids if b.status in (BidStatusEnum.FINALIZED, BidStatusEnum.COMPLIANT, BidStatusEnum.NON_COMPLIANT))

        # Compliance counts across bidder's bids
        comp_count = 0
        non_comp_count = 0
        needs_rev_count = 0
        for b in my_bids:
            res_list = b.compliance_results or []
            if any(r.status == ComplianceStatusEnum.NON_COMPLIANT for r in res_list if r.requirement and r.requirement.mandatory):
                non_comp_count += 1
            elif any(r.status == ComplianceStatusEnum.NEEDS_REVIEW for r in res_list):
                needs_rev_count += 1
            elif res_list and all(r.status == ComplianceStatusEnum.COMPLIANT for r in res_list if r.requirement and r.requirement.mandatory):
                comp_count += 1

        metrics = {
            "my_total_bids": len(my_bids),
            "draft_bids": draft_c,
            "submitted_bids": submitted_c,
            "under_review_bids": under_review_c,
            "finalized_bids": finalized_c,
            "compliant_bids": comp_count,
            "non_compliant_bids": non_comp_count,
            "pending_review_bids": needs_rev_count,
        }

        recent_bids = [
            {
                "id": b.id,
                "bid_number": b.bid_number,
                "tender_title": b.tender.title if b.tender else "Tender",
                "status": b.status.value,
                "created_at": b.created_at.isoformat(),
            }
            for b in my_bids[:5]
        ]

        # Available open published tenders for bidding
        open_tenders = (
            db.query(Tender)
            .filter(Tender.status == TenderStatusEnum.PUBLISHED)
            .order_by(Tender.created_at.desc())
            .limit(5)
            .all()
        )
        recent_tenders = [
            {
                "id": t.id,
                "title": t.title,
                "tender_number": t.tender_number,
                "deadline": t.submission_deadline.isoformat(),
                "organization": t.organization,
            }
            for t in open_tenders
        ]

    # -------------------------------------------------------------
    # 4. REVIEWER Dashboard
    # -------------------------------------------------------------
    elif primary_role == "REVIEWER":
        pending_queue = (
            db.query(ReviewTask)
            .options(selectinload(ReviewTask.compliance_result).selectinload(ComplianceResult.requirement), selectinload(ReviewTask.bid))
            .filter(ReviewTask.status == ReviewStatusEnum.PENDING)
            .all()
        )
        my_tasks = (
            db.query(ReviewTask)
            .filter(ReviewTask.assigned_to_id == user.id)
            .all()
        )
        my_decisions_c = db.query(ReviewDecision).filter(ReviewDecision.reviewer_id == user.id).count()

        metrics = {
            "queue_pending_tasks": len(pending_queue),
            "my_assigned_tasks": len(my_tasks),
            "my_decisions_completed": my_decisions_c,
        }

        pending_tasks = [
            {
                "id": t.id,
                "bid_id": t.bid_id,
                "bid_number": t.bid.bid_number if t.bid else None,
                "requirement_text": t.compliance_result.requirement.requirement_text if t.compliance_result and t.compliance_result.requirement else None,
                "status": t.status.value,
                "trigger_reason": t.trigger_reason,
                "created_at": t.created_at.isoformat(),
            }
            for t in pending_queue[:5]
        ]

    # -------------------------------------------------------------
    # 5. AUDITOR Dashboard
    # -------------------------------------------------------------
    elif primary_role == "AUDITOR":
        total_evaluations = db.query(ComplianceResult).count()
        total_reports = db.query(Report).count()
        total_audits = db.query(AuditLog).count()
        total_overrides = db.query(ReviewDecision).count()

        metrics = {
            "total_compliance_evaluations": total_evaluations,
            "total_reports_generated": total_reports,
            "total_review_decisions": total_overrides,
            "total_audit_events_recorded": total_audits,
        }

        audits = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
        recent_activity = [
            {
                "id": a.id,
                "action": a.action,
                "actor_email": a.actor_email,
                "resource_type": a.resource_type,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in audits
        ]

    return DashboardSummaryResponse(
        role=primary_role,
        user_name=user.full_name or user.email,
        user_email=user.email,
        metrics=metrics,
        status_breakdown=status_breakdown,
        recent_bids=recent_bids,
        recent_tenders=recent_tenders,
        pending_tasks=pending_tasks,
        recent_activity=recent_activity,
    )
