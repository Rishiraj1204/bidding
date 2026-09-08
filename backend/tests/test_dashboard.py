import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.models.bid import Bid, BidStatusEnum
from backend.app.models.tender import Tender, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash


@pytest.fixture
def dashboard_test_env(db):
    """Seed test users for each primary role."""
    admin = User(
        id=str(uuid.uuid4()),
        email="admin_dsh@gem.gov.in",
        hashed_password=get_password_hash("DshPass123"),
        full_name="Dashboard Administrator",
        is_active=True,
    )
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_dsh@gem.gov.in",
        hashed_password=get_password_hash("DshPass123"),
        full_name="Procurement Officer Dave",
        is_active=True,
    )
    bidder = User(
        id=str(uuid.uuid4()),
        email="bidder_dsh@vendor.in",
        hashed_password=get_password_hash("DshPass123"),
        full_name="Apex Telematics Ltd",
        is_active=True,
    )
    reviewer = User(
        id=str(uuid.uuid4()),
        email="reviewer_dsh@gem.gov.in",
        hashed_password=get_password_hash("DshPass123"),
        full_name="Reviewer Singh",
        is_active=True,
    )
    auditor = User(
        id=str(uuid.uuid4()),
        email="auditor_dsh@gem.gov.in",
        hashed_password=get_password_hash("DshPass123"),
        full_name="Auditor Rao",
        is_active=True,
    )
    db.add_all([admin, officer, bidder, reviewer, auditor])
    db.commit()

    from backend.app.models.user import Role
    admin_r = db.query(Role).filter(Role.name == UserRoleEnum.ADMIN.value).first()
    officer_r = db.query(Role).filter(Role.name == UserRoleEnum.PROCUREMENT_OFFICER.value).first()
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    reviewer_r = db.query(Role).filter(Role.name == UserRoleEnum.REVIEWER.value).first()
    auditor_r = db.query(Role).filter(Role.name == UserRoleEnum.AUDITOR.value).first()

    if admin_r:
        admin.roles.append(admin_r)
    if officer_r:
        officer.roles.append(officer_r)
    if bidder_r:
        bidder.roles.append(bidder_r)
    if reviewer_r:
        reviewer.roles.append(reviewer_r)
    if auditor_r:
        auditor.roles.append(auditor_r)
    db.commit()

    # Create Tender
    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-DSH-{uuid.uuid4().hex[:6]}",
        title="Smart Grid IoT Sensors",
        organization="PowerGrid India",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=15),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    # Create Bid
    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder.id,
        bid_number=f"BID-DSH-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid)
    db.commit()

    return {
        "admin": admin,
        "officer": officer,
        "bidder": bidder,
        "reviewer": reviewer,
        "auditor": auditor,
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_role_aware_dashboard_endpoints(client, dashboard_test_env):
    """Test dashboard metrics for each role."""
    # 1. Admin Dashboard
    admin_tok = get_token(client, "admin_dsh@gem.gov.in", "DshPass123")
    adm_resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {admin_tok}"})
    assert adm_resp.status_code == status.HTTP_200_OK
    adm_data = adm_resp.json()
    assert adm_data["role"] == "ADMIN"
    assert "total_users" in adm_data["metrics"]
    assert "total_tenders" in adm_data["metrics"]

    # 2. Procurement Officer Dashboard
    off_tok = get_token(client, "officer_dsh@gem.gov.in", "DshPass123")
    off_resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {off_tok}"})
    assert off_resp.status_code == status.HTTP_200_OK
    off_data = off_resp.json()
    assert off_data["role"] == "PROCUREMENT_OFFICER"
    assert "my_tenders_total" in off_data["metrics"]

    # 3. Bidder Dashboard
    bid_tok = get_token(client, "bidder_dsh@vendor.in", "DshPass123")
    bid_resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {bid_tok}"})
    assert bid_resp.status_code == status.HTTP_200_OK
    bid_data = bid_resp.json()
    assert bid_data["role"] == "BIDDER"
    assert "my_total_bids" in bid_data["metrics"]
    assert len(bid_data["recent_bids"]) >= 1

    # 4. Reviewer Dashboard
    rev_tok = get_token(client, "reviewer_dsh@gem.gov.in", "DshPass123")
    rev_resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {rev_tok}"})
    assert rev_resp.status_code == status.HTTP_200_OK
    rev_data = rev_resp.json()
    assert rev_data["role"] == "REVIEWER"
    assert "queue_pending_tasks" in rev_data["metrics"]

    # 5. Auditor Dashboard
    aud_tok = get_token(client, "auditor_dsh@gem.gov.in", "DshPass123")
    aud_resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {aud_tok}"})
    assert aud_resp.status_code == status.HTTP_200_OK
    aud_data = aud_resp.json()
    assert aud_data["role"] == "AUDITOR"
    assert "total_compliance_evaluations" in aud_data["metrics"]
