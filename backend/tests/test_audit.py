import uuid
import pytest
from fastapi import status

from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash
from backend.app.services.audit_service import log_audit_event


@pytest.fixture
def audit_test_env(db):
    """Seed test users across roles and generate audit entries."""
    admin = User(
        id=str(uuid.uuid4()),
        email="admin_aud@gem.gov.in",
        hashed_password=get_password_hash("AudPass123"),
        full_name="System Auditor Admin",
        is_active=True,
    )
    auditor = User(
        id=str(uuid.uuid4()),
        email="auditor_aud@gem.gov.in",
        hashed_password=get_password_hash("AudPass123"),
        full_name="Compliance Auditor",
        is_active=True,
    )
    bidder = User(
        id=str(uuid.uuid4()),
        email="bidder_aud@vendor.in",
        hashed_password=get_password_hash("AudPass123"),
        full_name="Standard Bidder",
        is_active=True,
    )
    db.add_all([admin, auditor, bidder])
    db.commit()

    from backend.app.models.user import Role
    admin_r = db.query(Role).filter(Role.name == UserRoleEnum.ADMIN.value).first()
    auditor_r = db.query(Role).filter(Role.name == UserRoleEnum.AUDITOR.value).first()
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()

    if admin_r:
        admin.roles.append(admin_r)
    if auditor_r:
        auditor.roles.append(auditor_r)
    if bidder_r:
        bidder.roles.append(bidder_r)
    db.commit()

    # Create audit log events with some sensitive fields to test redaction
    log_audit_event(
        db=db,
        action="USER_LOGIN_TEST",
        resource_type="auth",
        actor_id=admin.id,
        actor_email=admin.email,
        new_state={"token": "secret_jwt_token_value", "login_status": "SUCCESS"},
    )
    log_audit_event(
        db=db,
        action="TENDER_CREATED_TEST",
        resource_type="tender",
        resource_id=str(uuid.uuid4()),
        actor_id=admin.id,
        actor_email=admin.email,
        new_state={"title": "Solar Power Grid Tender"},
    )

    return {"admin": admin, "auditor": auditor, "bidder": bidder}


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_audit_log_access_and_rbac(client, audit_test_env):
    """Admin and Auditor can view audit logs; Bidder is forbidden."""
    admin_token = get_token(client, "admin_aud@gem.gov.in", "AudPass123")
    auditor_token = get_token(client, "auditor_aud@gem.gov.in", "AudPass123")
    bidder_token = get_token(client, "bidder_aud@vendor.in", "AudPass123")

    # 1. Admin can access
    admin_resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_resp.status_code == status.HTTP_200_OK
    assert admin_resp.json()["total"] >= 2

    # 2. Auditor can access
    auditor_resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {auditor_token}"})
    assert auditor_resp.status_code == status.HTTP_200_OK
    assert auditor_resp.json()["total"] >= 2

    # 3. Bidder is blocked -> 403 Forbidden
    bidder_resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {bidder_token}"})
    assert bidder_resp.status_code == status.HTTP_403_FORBIDDEN


def test_audit_log_filters_and_credential_sanitization(client, audit_test_env):
    """Audit query filters by action and ensures credentials/secrets are redacted."""
    admin_token = get_token(client, "admin_aud@gem.gov.in", "AudPass123")

    # Filter by action
    resp = client.get(
        "/api/v1/audit-logs?action=USER_LOGIN_TEST",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1

    item = data["items"][0]
    assert item["action"] == "USER_LOGIN_TEST"
    # Check that sensitive keys were redacted
    assert item["new_state"]["token"] == "[REDACTED]"
    assert item["new_state"]["login_status"] == "SUCCESS"
