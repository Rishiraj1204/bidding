from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.models.bid import Bid, BidStatusEnum
from backend.app.models.tender import Tender, TenderStatusEnum
from backend.app.services.user_service import create_user
from backend.app.schemas.user import UserCreate


def setup_bid_test_environment(client: TestClient, db: Session):
    """Setup officer, bidders, and published tender for testing."""
    # Create Officer
    officer = create_user(
        db,
        UserCreate(
            email="officer_bid_test@gem.gov.in",
            password="OfficerPassword123",
            full_name="Procurement Officer",
            organization_name="Ministry of Defense",
            role_names=["PROCUREMENT_OFFICER"],
        ),
    )

    # Create Bidder 1 & 2
    bidder1 = create_user(
        db,
        UserCreate(
            email="bidder1_test@vendor.in",
            password="BidderPassword123",
            full_name="Alpha Tech Pvt Ltd",
            organization_name="Alpha Tech",
            role_names=["BIDDER"],
        ),
    )

    bidder2 = create_user(
        db,
        UserCreate(
            email="bidder2_test@vendor.in",
            password="BidderPassword123",
            full_name="Beta Systems Ltd",
            organization_name="Beta Systems",
            role_names=["BIDDER"],
        ),
    )

    officer_token = client.post(
        "/api/v1/auth/login",
        json={"email": "officer_bid_test@gem.gov.in", "password": "OfficerPassword123"},
    ).json()["access_token"]

    bidder1_token = client.post(
        "/api/v1/auth/login",
        json={"email": "bidder1_test@vendor.in", "password": "BidderPassword123"},
    ).json()["access_token"]

    bidder2_token = client.post(
        "/api/v1/auth/login",
        json={"email": "bidder2_test@vendor.in", "password": "BidderPassword123"},
    ).json()["access_token"]

    # Create a published tender with future deadline
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    t_pub = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/BID_READY",
            "title": "Defense Communication Systems",
            "organization": "Ministry of Defense",
            "category": "Defense Electronics",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {officer_token}"},
    ).json()

    client.patch(
        f"/api/v1/tenders/{t_pub['id']}/status",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )

    return {
        "officer": {"id": officer.id, "token": officer_token},
        "bidder1": {"id": bidder1.id, "token": bidder1_token},
        "bidder2": {"id": bidder2.id, "token": bidder2_token},
        "tender_id": t_pub["id"],
    }


def test_create_bid_success(client: TestClient, db: Session):
    """Bidder creates a draft bid against a published tender."""
    env = setup_bid_test_environment(client, db)

    response = client.post(
        "/api/v1/bids",
        json={
            "tender_id": env["tender_id"],
            "notes": "Alpha Tech initial compliance draft submission",
        },
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tender_id"] == env["tender_id"]
    assert data["bidder_id"] == env["bidder1"]["id"]
    assert data["status"] == "DRAFT"
    assert "BID/" in data["bid_number"]


def test_create_bid_on_draft_tender_rejected(client: TestClient, db: Session):
    """Bidding on a non-published draft tender returns 400 Bad Request."""
    env = setup_bid_test_environment(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()

    draft_tender = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/DRAFT_ONLY",
            "title": "Secret Draft Project",
            "organization": "Defense",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {env['officer']['token']}"},
    ).json()

    response = client.post(
        "/api/v1/bids",
        json={"tender_id": draft_tender["id"]},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert response.status_code == 400
    assert "not permitted" in response.json()["detail"]


def test_create_duplicate_bid_rejected(client: TestClient, db: Session):
    """Bidder cannot create multiple active bids for the same tender."""
    env = setup_bid_test_environment(client, db)

    res1 = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"]},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"]},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert res2.status_code == 400
    assert "already have an active bid" in res2.json()["detail"]


def test_get_bids_rbac_isolation(client: TestClient, db: Session):
    """Bidder sees only own bids; Officer can see all submissions."""
    env = setup_bid_test_environment(client, db)

    # Bidder 1 creates bid
    b1 = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"], "notes": "Bidder 1 Notes"},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    ).json()

    # Bidder 2 creates bid
    b2 = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"], "notes": "Bidder 2 Notes"},
        headers={"Authorization": f"Bearer {env['bidder2']['token']}"},
    ).json()

    # 1. Bidder 1 list -> Only Bidder 1's bid
    res_b1 = client.get(
        "/api/v1/bids",
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert res_b1.status_code == 200
    b1_items = res_b1.json()["items"]
    assert len(b1_items) == 1
    assert b1_items[0]["id"] == b1["id"]

    # 2. Officer list -> Both bids
    res_off = client.get(
        "/api/v1/bids",
        headers={"Authorization": f"Bearer {env['officer']['token']}"},
    )
    assert res_off.status_code == 200
    off_items = res_off.json()["items"]
    assert len(off_items) == 2


def test_bidder_idor_protection(client: TestClient, db: Session):
    """Bidder A cannot view or submit Bidder B's bid (403 Forbidden)."""
    env = setup_bid_test_environment(client, db)

    # Bidder 1 creates bid
    b1 = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"]},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    ).json()

    # Bidder 2 attempts to get Bidder 1's bid -> 403 Forbidden
    res_view = client.get(
        f"/api/v1/bids/{b1['id']}",
        headers={"Authorization": f"Bearer {env['bidder2']['token']}"},
    )
    assert res_view.status_code == 403

    # Bidder 2 attempts to submit Bidder 1's bid -> 403 Forbidden
    res_sub = client.post(
        f"/api/v1/bids/{b1['id']}/submit",
        headers={"Authorization": f"Bearer {env['bidder2']['token']}"},
    )
    assert res_sub.status_code == 403


def test_submit_bid_success_and_lock(client: TestClient, db: Session):
    """Submitting bid transitions status to SUBMITTED and locks modifications."""
    env = setup_bid_test_environment(client, db)

    # Create draft
    bid = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"], "notes": "Draft quote"},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    ).json()

    # Submit
    res_submit = client.post(
        f"/api/v1/bids/{bid['id']}/submit",
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert res_submit.status_code == 200
    data = res_submit.json()
    assert data["status"] == "SUBMITTED"
    assert data["submission_date"] is not None

    # Attempt to edit submitted bid -> 400 Bad Request
    res_edit = client.put(
        f"/api/v1/bids/{bid['id']}",
        json={"notes": "Hacked post-submission note"},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert res_edit.status_code == 400
    assert "Only DRAFT bids can be modified" in res_edit.json()["detail"]


def test_withdraw_bid_success(client: TestClient, db: Session):
    """Bidder can withdraw a draft or submitted bid."""
    env = setup_bid_test_environment(client, db)

    bid = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"]},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    ).json()

    res_withdraw = client.post(
        f"/api/v1/bids/{bid['id']}/withdraw?reason=Commercial_Reevaluation",
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )
    assert res_withdraw.status_code == 200
    assert res_withdraw.json()["status"] == "WITHDRAWN"


def test_bid_audit_log_records(client: TestClient, db: Session):
    """Verify AuditLog records are generated for bid lifecycle events."""
    env = setup_bid_test_environment(client, db)

    bid = client.post(
        "/api/v1/bids",
        json={"tender_id": env["tender_id"], "notes": "Audit Bid Test"},
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    ).json()

    client.post(
        f"/api/v1/bids/{bid['id']}/submit",
        headers={"Authorization": f"Bearer {env['bidder1']['token']}"},
    )

    audit_records = (
        db.query(AuditLog)
        .filter(AuditLog.resource_id == bid["id"])
        .order_by(AuditLog.timestamp)
        .all()
    )
    actions = [a.action for a in audit_records]

    assert "BID_CREATED" in actions
    assert "BID_SUBMITTED" in actions
