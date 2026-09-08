import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash, verify_password
from backend.app.services.user_service import create_user
from backend.app.schemas.user import UserCreate


def test_password_hashing():
    """Verify password hashing and verification functionality."""
    password = "SuperSecretPassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_register_bidder_success(client: TestClient):
    """Test public registration as a BIDDER."""
    payload = {
        "email": "vendor@abcsupplies.com",
        "password": "SecureVendorPass123",
        "full_name": "ABC Supplies Pvt Ltd",
        "organization_name": "ABC Supplies",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "vendor@abcsupplies.com"
    assert "BIDDER" in data["user"]["roles"]
    assert "hashed_password" not in str(data)  # Passwords must not be exposed


def test_register_duplicate_email(client: TestClient):
    """Test duplicate registration error handling."""
    payload = {
        "email": "duplicate@vendor.com",
        "password": "Password123",
        "full_name": "Duplicate User",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_login_success(client: TestClient, db: Session):
    """Test successful user login and token generation."""
    create_user(
        db,
        UserCreate(
            email="login_user@gem.gov.in",
            password="CorrectPassword123",
            full_name="Login Test User",
            role_names=["PROCUREMENT_OFFICER"],
        ),
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login_user@gem.gov.in", "password": "CorrectPassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login_user@gem.gov.in"
    assert "PROCUREMENT_OFFICER" in data["user"]["roles"]


def test_login_invalid_credentials(client: TestClient, db: Session):
    """Test login failure on incorrect password and nonexistent user."""
    create_user(
        db,
        UserCreate(
            email="existing@gem.gov.in",
            password="ValidPassword123",
            full_name="Existing User",
            role_names=["BIDDER"],
        ),
    )

    res_wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"email": "existing@gem.gov.in", "password": "WrongPassword!"},
    )
    assert res_wrong_pw.status_code == 401
    assert "Incorrect email or password" in res_wrong_pw.json()["detail"]

    # Nonexistent user
    res_nonexistent = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@gem.gov.in", "password": "AnyPassword123"},
    )
    assert res_nonexistent.status_code == 401
    assert "Incorrect email or password" in res_nonexistent.json()["detail"]


def test_login_inactive_user(client: TestClient, db: Session):
    """Test login rejection for inactive user accounts."""
    create_user(
        db,
        UserCreate(
            email="inactive@gem.gov.in",
            password="Password123",
            full_name="Inactive User",
            is_active=False,
            role_names=["BIDDER"],
        ),
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@gem.gov.in", "password": "Password123"},
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_get_current_user_me(client: TestClient):
    """Test /auth/me profile retrieval with valid token."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "me_user@vendor.in",
            "password": "Password123",
            "full_name": "Me User",
        },
    )
    token = reg.json()["access_token"]

    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "me_user@vendor.in"
    assert "BIDDER" in me_data["roles"]
    assert "bids.create" in me_data["permissions"]


def test_get_me_unauthorized(client: TestClient):
    """Test /auth/me rejection without token or with malformed token."""
    res_no_token = client.get("/api/v1/auth/me")
    assert res_no_token.status_code == 401

    res_invalid_token = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert res_invalid_token.status_code == 401


def test_rbac_admin_only_user_creation(client: TestClient, db: Session):
    """Test that creating users via /api/v1/users is allowed for ADMIN and rejected for BIDDER."""
    create_user(
        db,
        UserCreate(
            email="admin@gem.gov.in",
            password="AdminPassword123",
            full_name="System Administrator",
            role_names=["ADMIN"],
        ),
    )
    create_user(
        db,
        UserCreate(
            email="regular_bidder@vendor.in",
            password="BidderPassword123",
            full_name="Regular Bidder",
            role_names=["BIDDER"],
        ),
    )

    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@gem.gov.in", "password": "AdminPassword123"},
    ).json()["access_token"]

    bidder_token = client.post(
        "/api/v1/auth/login",
        json={"email": "regular_bidder@vendor.in", "password": "BidderPassword123"},
    ).json()["access_token"]

    new_user_payload = {
        "email": "reviewer1@gem.gov.in",
        "password": "ReviewerPass123",
        "full_name": "Reviewer One",
        "role_names": ["REVIEWER"],
    }

    # Bidder attempts to create user -> 403 Forbidden
    res_bidder = client.post(
        "/api/v1/users",
        json=new_user_payload,
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert res_bidder.status_code == 403

    # Admin creates user -> 201 Created
    res_admin = client.post(
        "/api/v1/users",
        json=new_user_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 201
    assert res_admin.json()["email"] == "reviewer1@gem.gov.in"
    assert any(r["name"] == "REVIEWER" for r in res_admin.json()["roles"])


def test_resource_level_ownership_protection(client: TestClient, db: Session):
    """Test that users can only view/modify their own profile unless they are ADMIN."""
    user_a = create_user(
        db,
        UserCreate(
            email="user_a@vendor.in",
            password="Password123",
            full_name="User A",
            role_names=["BIDDER"],
        ),
    )
    user_b = create_user(
        db,
        UserCreate(
            email="user_b@vendor.in",
            password="Password123",
            full_name="User B",
            role_names=["BIDDER"],
        ),
    )
    user_a_id = user_a.id
    user_b_id = user_b.id

    token_a = client.post(
        "/api/v1/auth/login",
        json={"email": "user_a@vendor.in", "password": "Password123"},
    ).json()["access_token"]

    # User A accesses User A profile -> 200 OK
    res_self = client.get(
        f"/api/v1/users/{user_a_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_self.status_code == 200
    assert res_self.json()["id"] == user_a_id

    # User A attempts to access User B profile -> 403 Forbidden
    res_other = client.get(
        f"/api/v1/users/{user_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_other.status_code == 403


def test_privilege_escalation_prevented_on_profile_update(client: TestClient, db: Session):
    """Test that non-admin users cannot promote themselves to ADMIN or superuser."""
    user = create_user(
        db,
        UserCreate(
            email="attacker@vendor.in",
            password="Password123",
            full_name="Attacker",
            role_names=["BIDDER"],
        ),
    )
    user_id = user.id

    token = client.post(
        "/api/v1/auth/login",
        json={"email": "attacker@vendor.in", "password": "Password123"},
    ).json()["access_token"]

    update_res = client.put(
        f"/api/v1/users/{user_id}",
        json={"role_names": ["ADMIN"], "is_superuser": True, "full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["full_name"] == "Updated Name"
    assert updated_data["is_superuser"] is False
    assert any(r["name"] == "BIDDER" for r in updated_data["roles"])
    assert not any(r["name"] == "ADMIN" for r in updated_data["roles"])


def test_logout_endpoint(client: TestClient):
    """Test user logout endpoint."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout_test@vendor.in",
            "password": "Password123",
            "full_name": "Logout Test",
        },
    )
    token = reg.json()["access_token"]

    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "success"
