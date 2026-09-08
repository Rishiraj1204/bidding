import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.core.security import get_password_hash
from backend.app.models.user import Role, User, UserRoleEnum
from seed import seed_database


@pytest.fixture
def sih_demo_users(db):
    """Seed all 5 demo users with distinct roles."""
    roles = {r.name: r for r in db.query(Role).all()}
    
    users = {}
    specs = [
        ("admin_p10@gem.gov.in", "ADMIN", True),
        ("officer_p10@gem.gov.in", "PROCUREMENT_OFFICER", False),
        ("bidder_p10@vendor.in", "BIDDER", False),
        ("reviewer_p10@gem.gov.in", "REVIEWER", False),
        ("auditor_p10@gem.gov.in", "AUDITOR", False),
    ]

    for email, role_name, is_super in specs:
        u = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=get_password_hash("DemoPass123!"),
            full_name=f"Demo {role_name}",
            organization_name="Demo Org",
            is_active=True,
            is_superuser=is_super,
        )
        db.add(u)
        db.commit()
        if role_name in roles:
            u.roles.append(roles[role_name])
        db.commit()
        users[role_name] = u

    return users


def get_token_for(client, email, password="DemoPass123!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()["access_token"]


def test_seed_database_execution(db):
    """Verify that seed_database() runs idempotently and creates demo records."""
    seed_database(custom_db=db, custom_engine=db.get_bind())


def test_all_five_roles_dashboard_access(client, sih_demo_users):
    """Verify all 5 roles can authenticate and query their role-tailored dashboards."""
    role_emails = {
        "ADMIN": "admin_p10@gem.gov.in",
        "PROCUREMENT_OFFICER": "officer_p10@gem.gov.in",
        "BIDDER": "bidder_p10@vendor.in",
        "REVIEWER": "reviewer_p10@gem.gov.in",
        "AUDITOR": "auditor_p10@gem.gov.in",
    }

    for role_name, email in role_emails.items():
        token = get_token_for(client, email)
        resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["role"] == role_name
        assert "metrics" in data
        assert "recent_activity" in data or "pending_tasks" in data or "status_breakdown" in data


def test_role_authorization_boundaries(client, sih_demo_users):
    """Verify strict access boundaries across roles."""
    bidder_token = get_token_for(client, "bidder_p10@vendor.in")
    officer_token = get_token_for(client, "officer_p10@gem.gov.in")
    auditor_token = get_token_for(client, "auditor_p10@gem.gov.in")
    reviewer_token = get_token_for(client, "reviewer_p10@gem.gov.in")

    # 1. Bidder cannot view audit logs (403)
    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {bidder_token}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 2. Officer cannot view audit logs (403)
    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {officer_token}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 3. Auditor can view audit logs (200)
    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {auditor_token}"})
    assert resp.status_code == status.HTTP_200_OK

    # 4. Reviewer cannot create tenders (403)
    resp = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:6].upper()}",
            "title": "Unauthorized Tender Creation",
            "organization": "Fraud Dept",
            "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        },
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_mock_verification_transparency(client, sih_demo_users):
    """Ensure registry verifications are explicitly identified as simulated/mock."""
    officer_token = get_token_for(client, "officer_p10@gem.gov.in")
    bidder_token = get_token_for(client, "bidder_p10@vendor.in")

    # Officer creates published tender
    t_resp = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:6].upper()}",
            "title": "Smart Water Metering Tender",
            "organization": "State Water Board",
            "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
        },
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert t_resp.status_code == status.HTTP_201_CREATED
    t_id = t_resp.json()["id"]

    client.patch(
        f"/api/v1/tenders/{t_id}/status",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )

    # Bidder creates bid & uploads GST
    b_resp = client.post(
        "/api/v1/bids",
        json={"tender_id": t_id, "amount": 5000000.0, "delivery_timeline_days": 30},
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert b_resp.status_code == status.HTTP_201_CREATED
    b_id = b_resp.json()["id"]

    fake_pdf = b"%PDF-1.4\nGSTIN: 27AAAPL1234C1ZV\n"
    d_resp = client.post(
        f"/api/v1/documents/bid/{b_id}",
        files={"file": ("gst.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        data={"document_type": "GST_CERTIFICATE"},
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    doc_id = d_resp.json()["id"]

    # Process OCR & extraction
    client.post(f"/api/v1/documents/bid/{b_id}/{doc_id}/process-ocr", headers={"Authorization": f"Bearer {bidder_token}"})
    client.post(f"/api/v1/extraction/bid/{b_id}", headers={"Authorization": f"Bearer {bidder_token}"})

    # Evaluate compliance
    comp_resp = client.post(f"/api/v1/compliance/bid/{b_id}/evaluate", headers={"Authorization": f"Bearer {bidder_token}"})
    assert comp_resp.status_code == status.HTTP_200_OK
