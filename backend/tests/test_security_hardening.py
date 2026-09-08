import io
import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi import status

from backend.app.core.config import settings
from backend.app.core.rate_limit import limiter
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.models.bid import Bid, BidStatusEnum
from backend.app.models.tender import Tender, TenderStatusEnum
from backend.app.models.user import Role, User, UserRoleEnum
from backend.app.services.audit_service import log_audit_event


@pytest.fixture
def security_test_env(db):
    """Seed test users with distinct roles."""
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_sec@gem.gov.in",
        hashed_password=get_password_hash("SecPass123"),
        full_name="Procurement Officer",
        is_active=True,
    )
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="bidder1_sec@vendor.in",
        hashed_password=get_password_hash("SecPass123"),
        full_name="Vendor Alpha",
        is_active=True,
    )
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="bidder2_sec@vendor.in",
        hashed_password=get_password_hash("SecPass123"),
        full_name="Vendor Beta",
        is_active=True,
    )
    db.add_all([officer, bidder1, bidder2])
    db.commit()

    officer_r = db.query(Role).filter(Role.name == UserRoleEnum.PROCUREMENT_OFFICER.value).first()
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()

    if officer_r:
        officer.roles.append(officer_r)
    if bidder_r:
        bidder1.roles.append(bidder_r)
        bidder2.roles.append(bidder_r)
    db.commit()

    # Tender created by officer
    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-SEC-{uuid.uuid4().hex[:6]}",
        title="Secure Cloud Infrastructure",
        organization="Ministry of Electronics",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=10),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    # Bid created by Bidder 1
    bid1 = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder1.id,
        bid_number=f"BID-SEC-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid1)
    db.commit()

    return {
        "officer": officer,
        "bidder1": bidder1,
        "bidder2": bidder2,
        "tender": tender,
        "bid1": bid1,
    }


def get_token(client, email, password="SecPass123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_expired_jwt_rejected(client, security_test_env):
    """Expired tokens must be strictly rejected with 401 Unauthorized."""
    user = security_test_env["bidder1"]
    expired_token = create_access_token(
        subject=user.id,
        email=user.email,
        expires_delta=timedelta(seconds=-60),
    )

    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in resp.json()["detail"].lower()


def test_tampered_jwt_rejected(client, security_test_env):
    """Tokens with tampered signatures or headers must return 401 Unauthorized."""
    valid_token = get_token(client, "bidder1_sec@vendor.in")
    parts = valid_token.split(".")
    # Tamper with the signature portion
    tampered_token = f"{parts[0]}.{parts[1]}.invalidsignaturexyz123"

    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_algorithm_none_jwt_rejected(client, security_test_env):
    """Tokens using 'none' algorithm must be rejected."""
    user = security_test_env["bidder1"]
    payload = {"sub": user.id, "email": user.email, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}
    # Attempt unverified none-alg encoding
    none_token = jwt.encode(payload, key="", algorithm="none")

    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {none_token}"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_privilege_escalation_prevented(client, security_test_env):
    """A standard bidder cannot create tenders or inspect audit logs."""
    bidder_token = get_token(client, "bidder1_sec@vendor.in")

    # Attempt to create tender (Officers/Admins only)
    tender_payload = {
        "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:6].upper()}",
        "title": "Unauthorized Tender Creation",
        "description": "Exploit attempt",
        "organization": "Fraud Corp",
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "category": "GOODS",
    }
    resp = client.post(
        "/api/v1/tenders",
        json=tender_payload,
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Attempt to query audit logs (Auditor/Admin only)
    audit_resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {bidder_token}"})
    assert audit_resp.status_code == status.HTTP_403_FORBIDDEN


def test_cross_user_bid_idor_blocked(client, security_test_env):
    """Bidder 2 cannot inspect or modify Bidder 1's draft bid."""
    bidder2_token = get_token(client, "bidder2_sec@vendor.in")
    bid1_id = security_test_env["bid1"].id

    resp = client.get(f"/api/v1/bids/{bid1_id}", headers={"Authorization": f"Bearer {bidder2_token}"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_malicious_path_traversal_filename_sanitized(client, security_test_env):
    """Path traversal filename sequences like ../../ must be safely stripped."""
    token = get_token(client, "bidder1_sec@vendor.in")
    bid_id = security_test_env["bid1"].id

    fake_pdf = b"%PDF-1.4 test secure document content with valid header"
    file_payload = ("../../../../windows/system32/exploit.pdf", io.BytesIO(fake_pdf), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        files={"file": file_payload},
        data={"document_type": "GST_CERTIFICATE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    # Ensure directory path was stripped
    assert ".." not in data["filename"]
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]


def test_disguised_executable_magic_bytes_rejected(client, security_test_env):
    """Executable binary content disguised as a .pdf must fail magic bytes verification."""
    token = get_token(client, "bidder1_sec@vendor.in")
    bid_id = security_test_env["bid1"].id

    # Windows PE executable magic header (MZ...)
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00malicious_binary_payload"
    file_payload = ("trojan.pdf", io.BytesIO(fake_exe), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        files={"file": file_payload},
        data={"document_type": "GST_CERTIFICATE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "header does not match declared mime type" in resp.json()["detail"].lower()


def test_security_headers_present_in_response(client):
    """All HTTP responses must carry standard security hardening headers."""
    resp = client.get("/health")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_audit_log_sensitive_credential_redaction(db):
    """Audit logs must automatically redact passwords, tokens, and secret keys."""
    entry = log_audit_event(
        db=db,
        action="TEST_SECURITY_EVENT",
        resource_type="auth",
        actor_email="audit@gem.gov.in",
        new_state={
            "user_email": "officer@gem.gov.in",
            "password": "SuperSecretPassword!",
            "hashed_password": "$2b$12$eX4mpleH4shValu3",
            "access_token": "eyJhbGciOi...",
            "nested_config": {"secret_key": "my_private_key", "public_id": "12345"},
        },
    )

    assert entry.new_state["password"] == "[REDACTED]"
    assert entry.new_state["hashed_password"] == "[REDACTED]"
    assert entry.new_state["access_token"] == "[REDACTED]"
    assert entry.new_state["nested_config"]["secret_key"] == "[REDACTED]"
    assert entry.new_state["nested_config"]["public_id"] == "12345"


def test_brute_force_lockout_protection(client, security_test_env):
    """Multiple failed login attempts must trigger temporary account lockout."""
    email = "brute_target@vendor.in"
    limiter.reset_failed_logins(email)

    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 6th attempt should return 429 Too Many Requests
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword"})
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "locked" in resp.json()["detail"].lower()

    # Clean up
    limiter.reset_failed_logins(email)


def test_rate_limiter_sliding_window():
    """Verify rate limiter unit logic."""
    test_ip = "10.0.0.99"
    limiter._requests.pop(test_ip, None)

    assert not limiter.is_rate_limited(test_ip, limit=3, window_seconds=60)
    assert not limiter.is_rate_limited(test_ip, limit=3, window_seconds=60)
    assert not limiter.is_rate_limited(test_ip, limit=3, window_seconds=60)
    # 4th request exceeds limit
    assert limiter.is_rate_limited(test_ip, limit=3, window_seconds=60)

    # Clean up
    limiter._requests.pop(test_ip, None)
