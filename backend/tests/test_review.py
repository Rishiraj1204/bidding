import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.compliance import ComplianceResult, ComplianceStatusEnum
from backend.app.models.review import ReviewStatusEnum, ReviewTask
from backend.app.models.tender import RequirementCategoryEnum, Tender, TenderRequirement, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash


@pytest.fixture
def review_test_env(db):
    """Seed test users, tender, bid, and review task."""
    bidder = User(
        id=str(uuid.uuid4()),
        email="bidder_rev@vendor.in",
        hashed_password=get_password_hash("RevPass123"),
        full_name="Rev Vendor Ltd",
        is_active=True,
    )
    reviewer = User(
        id=str(uuid.uuid4()),
        email="reviewer_rev@gem.gov.in",
        hashed_password=get_password_hash("RevPass123"),
        full_name="Senior Reviewer Roy",
        is_active=True,
    )
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_rev@gem.gov.in",
        hashed_password=get_password_hash("RevPass123"),
        full_name="Officer Verma",
        is_active=True,
    )
    db.add_all([bidder, reviewer, officer])
    db.commit()

    from backend.app.models.user import Role
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    reviewer_r = db.query(Role).filter(Role.name == UserRoleEnum.REVIEWER.value).first()
    officer_r = db.query(Role).filter(Role.name == UserRoleEnum.PROCUREMENT_OFFICER.value).first()

    if bidder_r:
        bidder.roles.append(bidder_r)
    if reviewer_r:
        reviewer.roles.append(reviewer_r)
    if officer_r:
        officer.roles.append(officer_r)
    db.commit()

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-REV-{uuid.uuid4().hex[:6]}",
        title="Telemetry Infrastructure Procurement",
        organization="RailTel Corporation",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=25),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    req = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.EXPERIENCE,
        requirement_text="Minimum 5 years specialized telemetry experience.",
        parameter="experience_years",
        operator=">=",
        threshold_value="5.0",
        unit="years",
        mandatory=True,
    )
    db.add(req)
    db.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder.id,
        bid_number=f"BID-REV-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid)
    db.commit()

    comp_res = ComplianceResult(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        requirement_id=req.id,
        status=ComplianceStatusEnum.NEEDS_REVIEW,
        reason="Low OCR confidence (55%) extracted value 4.8 years against 5.0 requirement.",
        confidence=0.55,
        evaluated_by="RULE_ENGINE",
    )
    db.add(comp_res)
    db.commit()

    task = ReviewTask(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        compliance_result_id=comp_res.id,
        status=ReviewStatusEnum.PENDING,
        trigger_reason=comp_res.reason,
    )
    db.add(task)
    db.commit()

    return {
        "bidder": bidder,
        "reviewer": reviewer,
        "officer": officer,
        "tender": tender,
        "bid": bid,
        "req": req,
        "comp_res": comp_res,
        "task": task,
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_review_task_listing_and_detail(client, review_test_env):
    """Reviewer can list queue tasks and view task detail."""
    token = get_token(client, "reviewer_rev@gem.gov.in", "RevPass123")
    task_id = review_test_env["task"].id

    # List tasks
    list_resp = client.get("/api/v1/review/tasks", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == status.HTTP_200_OK
    data = list_resp.json()
    assert data["total"] >= 1
    assert any(t["id"] == task_id for t in data["items"])

    # Detail
    detail_resp = client.get(f"/api/v1/review/tasks/{task_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_resp.status_code == status.HTTP_200_OK
    task_data = detail_resp.json()
    assert task_data["id"] == task_id
    assert task_data["status"] == ReviewStatusEnum.PENDING.value
    assert task_data["original_decision"] == "NEEDS_REVIEW"


def test_self_review_prevention(client, review_test_env):
    """Bidder is strictly forbidden from reviewing or assigning tasks for their own bid."""
    bidder_token = get_token(client, "bidder_rev@vendor.in", "RevPass123")
    task_id = review_test_env["task"].id

    # Bidder attempts to submit review decision -> 403 Forbidden
    resp = client.post(
        f"/api/v1/review/tasks/{task_id}/decision",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={
            "new_decision": "COMPLIANT",
            "justification": "Approving my own bid submission.",
        },
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_review_decision_override_with_mandatory_justification(client, review_test_env, db):
    """Reviewer overrides decision with mandatory justification; original decision is preserved."""
    token = get_token(client, "reviewer_rev@gem.gov.in", "RevPass123")
    task_id = review_test_env["task"].id

    # 1. Attempt decision without justification -> 422/400 validation error
    bad_resp = client.post(
        f"/api/v1/review/tasks/{task_id}/decision",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_decision": "COMPLIANT", "justification": " "},
    )
    assert bad_resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]

    # 2. Valid override with full justification
    good_resp = client.post(
        f"/api/v1/review/tasks/{task_id}/decision",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "new_decision": "COMPLIANT",
            "justification": "Verified physical certificate Section 4B indicates 5.2 cumulative years of telemetry deployment.",
            "comments": "Audited during pre-qualification committee review.",
        },
    )
    assert good_resp.status_code == status.HTTP_200_OK
    res_data = good_resp.json()

    assert res_data["status"] == ReviewStatusEnum.APPROVED.value
    assert res_data["current_status"] == "COMPLIANT"
    assert len(res_data["decisions"]) == 1

    dec = res_data["decisions"][0]
    assert dec["original_decision"] == "NEEDS_REVIEW"
    assert dec["new_decision"] == "COMPLIANT"
    assert "5.2 cumulative years" in dec["justification"]

    # Verify DB compliance result state
    comp_res = db.query(ComplianceResult).filter(ComplianceResult.id == review_test_env["comp_res"].id).first()
    assert comp_res.status == ComplianceStatusEnum.COMPLIANT
    assert comp_res.evaluated_by == "HUMAN_REVIEW"
    assert "5.2 cumulative years" in comp_res.reason
