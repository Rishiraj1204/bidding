import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.deps import get_user_roles
from backend.app.models.bid import Bid
from backend.app.models.compliance import VerificationRecord
from backend.app.models.user import User
from backend.app.schemas.verification import (
    BidVerificationListResponse,
    VerificationRecordResponse,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.verification.provider import get_verification_provider


def _check_bid_access(bid: Bid, user: User) -> None:
    """Validate user has permission to access verification records for this bid."""
    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )
    if not is_staff and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view or trigger verification for this bid.",
        )


def _record_to_response(rec: VerificationRecord) -> VerificationRecordResponse:
    return VerificationRecordResponse(
        id=rec.id,
        bid_id=rec.bid_id,
        compliance_result_id=rec.compliance_result_id,
        verification_type=rec.verification_type,
        provider_name=rec.provider_name,
        is_mock=rec.is_mock,
        status=rec.status,
        reference_id=rec.reference_id,
        summary=rec.response_payload,
        error_message=rec.error_message,
        created_at=rec.created_at,
    )


def trigger_bid_verification(
    db: Session,
    bid_id: str,
    verification_type: str,
    identifier: str,
    compliance_result_id: Optional[str] = None,
    user: User = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> VerificationRecordResponse:
    """
    Trigger external registry verification for an identifier (GSTIN, PAN, MSME, etc.).
    Returns deterministic verification status clearly tagged with is_mock flag.
    """
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    v_provider = get_verification_provider()
    v_res = v_provider.verify(verification_type=verification_type, identifier=identifier)

    record = VerificationRecord(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        compliance_result_id=compliance_result_id,
        verification_type=v_res.verification_type,
        provider_name=v_res.provider_name,
        is_mock=v_res.is_mock,
        status=v_res.status,
        reference_id=v_res.reference_id,
        response_payload=v_res.summary,
        error_message=v_res.error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    log_audit_event(
        db=db,
        action="EXTERNAL_VERIFICATION_PERFORMED",
        resource_type="verification_record",
        resource_id=record.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "bid_id": bid.id,
            "verification_type": record.verification_type,
            "provider": record.provider_name,
            "is_mock": record.is_mock,
            "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return _record_to_response(record)


def get_bid_verification_records(
    db: Session,
    bid_id: str,
    user: User,
) -> BidVerificationListResponse:
    """List all verification records for a specific bid."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    records = (
        db.query(VerificationRecord)
        .filter(VerificationRecord.bid_id == bid.id)
        .order_by(VerificationRecord.created_at.desc())
        .all()
    )
    items = [_record_to_response(r) for r in records]

    return BidVerificationListResponse(
        items=items,
        total=len(items),
    )


def get_verification_record_detail(
    db: Session,
    record_id: str,
    user: User,
) -> VerificationRecordResponse:
    """Retrieve a single verification record with IDOR verification."""
    rec = db.query(VerificationRecord).filter(VerificationRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification record not found")

    bid = db.query(Bid).filter(Bid.id == rec.bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated bid not found")

    _check_bid_access(bid, user)
    return _record_to_response(rec)
