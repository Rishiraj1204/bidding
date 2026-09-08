import uuid
import pytest
from fastapi import status

from backend.app.models.notification import Notification
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash
from backend.app.services.notification_service import create_notification


@pytest.fixture
def notification_test_env(db):
    """Seed test users and sample notifications."""
    user1 = User(
        id=str(uuid.uuid4()),
        email="user1_notif@gem.gov.in",
        hashed_password=get_password_hash("NotifPass123"),
        full_name="Notification User One",
        is_active=True,
    )
    user2 = User(
        id=str(uuid.uuid4()),
        email="user2_notif@gem.gov.in",
        hashed_password=get_password_hash("NotifPass123"),
        full_name="Notification User Two",
        is_active=True,
    )
    db.add_all([user1, user2])
    db.commit()

    from backend.app.models.user import Role
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    if bidder_r:
        user1.roles.append(bidder_r)
        user2.roles.append(bidder_r)
        db.commit()

    # Create 3 notifications for user 1
    n1 = create_notification(
        db=db,
        user_id=user1.id,
        title="Tender Published",
        message="A new telemetry tender has been published.",
        notification_type="INFO",
    )
    n2 = create_notification(
        db=db,
        user_id=user1.id,
        title="Extraction Complete",
        message="AI entity extraction finished for your bid document.",
        notification_type="SUCCESS",
    )
    n3 = create_notification(
        db=db,
        user_id=user1.id,
        title="Review Required",
        message="A requirement needs additional clarification.",
        notification_type="ACTION_REQUIRED",
    )

    # Create 1 notification for user 2
    n_other = create_notification(
        db=db,
        user_id=user2.id,
        title="Private Notice",
        message="Confidential alert for user 2.",
        notification_type="INFO",
    )

    return {"user1": user1, "user2": user2, "n1": n1, "n2": n2, "n3": n3, "n_other": n_other}


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_list_notifications_and_unread_count(client, notification_test_env):
    """User can list own notifications and fetch unread count."""
    token = get_token(client, "user1_notif@gem.gov.in", "NotifPass123")

    # 1. Unread count
    count_resp = client.get("/api/v1/notifications/unread-count", headers={"Authorization": f"Bearer {token}"})
    assert count_resp.status_code == status.HTTP_200_OK
    assert count_resp.json()["unread_count"] == 3

    # 2. List notifications
    list_resp = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == status.HTTP_200_OK
    data = list_resp.json()
    assert data["total"] == 3
    assert data["unread_count"] == 3
    assert len(data["items"]) == 3
    # Check that User 2's notification is NOT visible
    assert all(item["title"] != "Private Notice" for item in data["items"])


def test_mark_notification_as_read_and_read_all(client, notification_test_env):
    """User can mark single notification as read and mark all as read."""
    token = get_token(client, "user1_notif@gem.gov.in", "NotifPass123")
    n1_id = notification_test_env["n1"].id

    # 1. Mark single notification read
    mark_resp = client.post(f"/api/v1/notifications/{n1_id}/read", headers={"Authorization": f"Bearer {token}"})
    assert mark_resp.status_code == status.HTTP_200_OK
    assert mark_resp.json()["is_read"] is True

    # Check unread count is now 2
    count_resp = client.get("/api/v1/notifications/unread-count", headers={"Authorization": f"Bearer {token}"})
    assert count_resp.json()["unread_count"] == 2

    # 2. Mark all as read
    read_all_resp = client.post("/api/v1/notifications/read-all", headers={"Authorization": f"Bearer {token}"})
    assert read_all_resp.status_code == status.HTTP_200_OK
    assert read_all_resp.json()["unread_count"] == 0

    # Verify count
    count_after = client.get("/api/v1/notifications/unread-count", headers={"Authorization": f"Bearer {token}"})
    assert count_after.json()["unread_count"] == 0


def test_notification_idor_isolation(client, notification_test_env):
    """User 1 cannot mark as read a notification owned by User 2."""
    token1 = get_token(client, "user1_notif@gem.gov.in", "NotifPass123")
    user2_notif_id = notification_test_env["n_other"].id

    # User 1 attempts to mark User 2's notification as read -> 403 Forbidden
    fail_resp = client.post(
        f"/api/v1/notifications/{user2_notif_id}/read",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert fail_resp.status_code == status.HTTP_403_FORBIDDEN
