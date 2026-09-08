from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.services.user_service import create_user
from backend.app.schemas.user import UserCreate


def create_test_users(client: TestClient, db: Session):
    """Helper to create officer, admin, and bidder test users and get their access tokens."""
    officer = create_user(
        db,
        UserCreate(
            email="officer_tender_test@gem.gov.in",
            password="OfficerPassword123",
            full_name="Procurement Officer 1",
            organization_name="Ministry of Health",
            role_names=["PROCUREMENT_OFFICER"],
        ),
    )
    officer2 = create_user(
        db,
        UserCreate(
            email="officer2_tender_test@gem.gov.in",
            password="OfficerPassword123",
            full_name="Procurement Officer 2",
            organization_name="Ministry of Railways",
            role_names=["PROCUREMENT_OFFICER"],
        ),
    )
    admin = create_user(
        db,
        UserCreate(
            email="admin_tender_test@gem.gov.in",
            password="AdminPassword123",
            full_name="Admin User",
            role_names=["ADMIN"],
        ),
    )
    bidder = create_user(
        db,
        UserCreate(
            email="bidder_tender_test@vendor.in",
            password="BidderPassword123",
            full_name="Vendor Representative",
            role_names=["BIDDER"],
        ),
    )
    officer_id = officer.id
    officer2_id = officer2.id
    admin_id = admin.id
    bidder_id = bidder.id

    officer_token = client.post(
        "/api/v1/auth/login",
        json={"email": "officer_tender_test@gem.gov.in", "password": "OfficerPassword123"},
    ).json()["access_token"]

    officer2_token = client.post(
        "/api/v1/auth/login",
        json={"email": "officer2_tender_test@gem.gov.in", "password": "OfficerPassword123"},
    ).json()["access_token"]

    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin_tender_test@gem.gov.in", "password": "AdminPassword123"},
    ).json()["access_token"]

    bidder_token = client.post(
        "/api/v1/auth/login",
        json={"email": "bidder_tender_test@vendor.in", "password": "BidderPassword123"},
    ).json()["access_token"]

    return {
        "officer": {"id": officer_id, "token": officer_token},
        "officer2": {"id": officer2_id, "token": officer2_token},
        "admin": {"id": admin_id, "token": admin_token},
        "bidder": {"id": bidder_id, "token": bidder_token},
    }


def test_create_tender_by_officer(client: TestClient, db: Session):
    """Procurement Officer creates a new tender."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()

    payload = {
        "tender_number": "GEM/2026/B/8001",
        "title": "High Precision Diagnostic Scanners",
        "description": "Procurement of 50 MRI diagnostic scan units",
        "organization": "AIIMS New Delhi",
        "category": "Medical Equipment",
        "submission_deadline": future_deadline,
        "status": "DRAFT",
    }

    response = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tender_number"] == "GEM/2026/B/8001"
    assert data["status"] == "DRAFT"
    assert data["created_by_id"] == users["officer"]["id"]


def test_create_tender_by_bidder_forbidden(client: TestClient, db: Session):
    """Bidder cannot create a tender (403 Forbidden)."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    payload = {
        "tender_number": "GEM/2026/B/8002",
        "title": "Unauthorized Bidder Tender",
        "organization": "Vendor Entity",
        "submission_deadline": future_deadline,
    }

    response = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {users['bidder']['token']}"},
    )
    assert response.status_code == 403


def test_create_tender_duplicate_number(client: TestClient, db: Session):
    """Duplicate tender number returns 400 Bad Request."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()

    payload = {
        "tender_number": "GEM/2026/B/DUPLICATE",
        "title": "Tender One",
        "organization": "Org A",
        "submission_deadline": future_deadline,
    }

    res1 = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_create_tender_past_deadline_rejected(client: TestClient, db: Session):
    """Setting a submission deadline in the past returns 400 Bad Request."""
    users = create_test_users(client, db)
    past_deadline = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    payload = {
        "tender_number": "GEM/2026/B/PAST",
        "title": "Past Deadline Tender",
        "organization": "Org Past",
        "submission_deadline": past_deadline,
    }

    response = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert response.status_code == 400
    assert "future date" in response.json()["detail"]


def test_list_tenders_visibility_and_search(client: TestClient, db: Session):
    """Test RBAC visibility and keyword search for tenders."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    # Create 1 DRAFT tender and 1 PUBLISHED tender
    t_draft = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/DRAFT01",
            "title": "Secret Internal Draft Server Tender",
            "organization": "Ministry of Electronics",
            "category": "Servers",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()

    t_pub = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/PUB01",
            "title": "Solar Panel Array Installation",
            "organization": "Ministry of New and Renewable Energy",
            "category": "Solar Energy",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()

    # Publish second tender
    client.patch(
        f"/api/v1/tenders/{t_pub['id']}/status",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )

    # 1. Officer lists tenders -> should see both DRAFT and PUBLISHED
    res_officer = client.get(
        "/api/v1/tenders",
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_officer.status_code == 200
    officer_tenders = res_officer.json()["items"]
    assert any(t["tender_number"] == "GEM/2026/B/DRAFT01" for t in officer_tenders)
    assert any(t["tender_number"] == "GEM/2026/B/PUB01" for t in officer_tenders)

    # 2. Bidder lists tenders -> should ONLY see PUBLISHED, NOT DRAFT
    res_bidder = client.get(
        "/api/v1/tenders",
        headers={"Authorization": f"Bearer {users['bidder']['token']}"},
    )
    assert res_bidder.status_code == 200
    bidder_tenders = res_bidder.json()["items"]
    assert not any(t["tender_number"] == "GEM/2026/B/DRAFT01" for t in bidder_tenders)
    assert any(t["tender_number"] == "GEM/2026/B/PUB01" for t in bidder_tenders)

    # 3. Search keyword filter
    search_res = client.get(
        "/api/v1/tenders?search=Solar",
        headers={"Authorization": f"Bearer {users['bidder']['token']}"},
    )
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1
    assert search_res.json()["items"][0]["category"] == "Solar Energy"


def test_update_tender_and_authorization(client: TestClient, db: Session):
    """Test updating tender information and creator ownership enforcement."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=25)).isoformat()

    # Officer 1 creates a tender
    tender = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/UPDATE01",
            "title": "Initial Hardware Title",
            "organization": "Department of Telecom",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()

    # Officer 2 attempts to update Officer 1's tender -> 403 Forbidden
    res_unauth = client.put(
        f"/api/v1/tenders/{tender['id']}",
        json={"title": "Hacked Title"},
        headers={"Authorization": f"Bearer {users['officer2']['token']}"},
    )
    assert res_unauth.status_code == 403

    # Officer 1 updates own tender -> 200 OK
    res_auth = client.put(
        f"/api/v1/tenders/{tender['id']}",
        json={"title": "Updated Modern Hardware Title", "category": "Telecom"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["title"] == "Updated Modern Hardware Title"
    assert res_auth.json()["category"] == "Telecom"


def test_status_lifecycle_and_invalid_transitions(client: TestClient, db: Session):
    """Test valid and invalid tender status transitions."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()

    tender = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/STATUS01",
            "title": "Lifecycle Test Tender",
            "organization": "DRDO",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()

    # 1. Invalid: DRAFT -> COMPLETED
    res_bad = client.patch(
        f"/api/v1/tenders/{tender['id']}/status",
        json={"status": "COMPLETED"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_bad.status_code == 400

    # 2. Valid: DRAFT -> PUBLISHED
    res_pub = client.patch(
        f"/api/v1/tenders/{tender['id']}/status",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_pub.status_code == 200
    assert res_pub.json()["status"] == "PUBLISHED"

    # 3. Valid: PUBLISHED -> CLOSED
    res_close = client.patch(
        f"/api/v1/tenders/{tender['id']}/status",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_close.status_code == 200
    assert res_close.json()["status"] == "CLOSED"

    # 4. Valid: CLOSED -> UNDER_EVALUATION
    res_eval = client.patch(
        f"/api/v1/tenders/{tender['id']}/status",
        json={"status": "UNDER_EVALUATION"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_eval.status_code == 200
    assert res_eval.json()["status"] == "UNDER_EVALUATION"

    # 5. Valid: UNDER_EVALUATION -> COMPLETED
    res_comp = client.patch(
        f"/api/v1/tenders/{tender['id']}/status",
        json={"status": "COMPLETED"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"


def test_delete_tender_rules(client: TestClient, db: Session):
    """Test draft deletion vs non-draft deletion rejection."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()

    # Draft tender
    t_draft = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/DEL_DRAFT",
            "title": "Draft to delete",
            "organization": "Test Org",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()

    # Published tender
    t_pub = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/DEL_PUB",
            "title": "Published cannot delete",
            "organization": "Test Org",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()
    client.patch(
        f"/api/v1/tenders/{t_pub['id']}/status",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )

    # 1. Delete draft -> 200 OK
    res_del_draft = client.delete(
        f"/api/v1/tenders/{t_draft['id']}",
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_del_draft.status_code == 200

    # 2. Officer attempts to delete published tender -> 400 Bad Request
    res_del_pub = client.delete(
        f"/api/v1/tenders/{t_pub['id']}",
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )
    assert res_del_pub.status_code == 400


def test_tender_audit_log_events(client: TestClient, db: Session):
    """Verify AuditLog records are created for tender actions."""
    users = create_test_users(client, db)
    future_deadline = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()

    # Create tender
    t_created = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": "GEM/2026/B/AUDIT_TEST",
            "title": "Audit Event Test Tender",
            "organization": "Ministry of Home Affairs",
            "submission_deadline": future_deadline,
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    ).json()

    # Update tender
    client.put(
        f"/api/v1/tenders/{t_created['id']}",
        json={"title": "Updated Audit Title"},
        headers={"Authorization": f"Bearer {users['officer']['token']}"},
    )

    # Check AuditLog table directly
    audit_records = (
        db.query(AuditLog)
        .filter(AuditLog.resource_id == t_created["id"])
        .order_by(AuditLog.timestamp)
        .all()
    )
    actions = [a.action for a in audit_records]

    assert "TENDER_CREATED" in actions
    assert "TENDER_UPDATED" in actions
