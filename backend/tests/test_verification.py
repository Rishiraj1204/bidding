import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.models.bid import Bid, BidStatusEnum
from backend.app.models.compliance import VerificationStatusEnum
from backend.app.models.tender import Tender, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash
from backend.app.verification.provider import get_verification_provider


@pytest.fixture
def verification_test_env(db):
    """Seed test users, tender, and bid."""
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="bidder1_vrf@vendor.in",
        hashed_password=get_password_hash("VrfPass123"),
        full_name="Verifiable Vendor 1",
        is_active=True,
    )
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="bidder2_vrf@vendor.in",
        hashed_password=get_password_hash("VrfPass123"),
        full_name="Verifiable Vendor 2",
        is_active=True,
    )
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_vrf@gem.gov.in",
        hashed_password=get_password_hash("VrfPass123"),
        full_name="Verification Officer",
        is_active=True,
    )
    db.add_all([bidder1, bidder2, officer])
    db.commit()

    from backend.app.models.user import Role
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    officer_r = db.query(Role).filter(Role.name == UserRoleEnum.PROCUREMENT_OFFICER.value).first()

    if bidder_r:
        bidder1.roles.append(bidder_r)
        bidder2.roles.append(bidder_r)
    if officer_r:
        officer.roles.append(officer_r)
    db.commit()

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-VRF-{uuid.uuid4().hex[:6]}",
        title="Verification Platform Tender",
        organization="Ministry of Electronics",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=20),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder1.id,
        bid_number=f"BID-VRF-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid)
    db.commit()

    return {"bidder1": bidder1, "bidder2": bidder2, "officer": officer, "bid": bid}


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_mock_verification_provider_logic():
    """Test registry verification logic for GST, PAN, and MSME."""
    provider = get_verification_provider()

    # 1. Valid GST
    gst_res = provider.verify("GST", "27AABCV1234F1Z5")
    assert gst_res.status == VerificationStatusEnum.VERIFIED
    assert gst_res.is_mock is True
    assert gst_res.provider_name == "MOCK_GOVERNMENT_GATEWAY"
    assert gst_res.summary["taxpayer_status"] == "ACTIVE"

    # 2. Invalid GST
    gst_bad = provider.verify("GST", "INVALID_GST_123")
    assert gst_bad.status == VerificationStatusEnum.FAILED
    assert gst_bad.is_mock is True

    # 3. Valid PAN
    pan_res = provider.verify("PAN", "AAACB1234K")
    assert pan_res.status == VerificationStatusEnum.VERIFIED
    assert pan_res.is_mock is True

    # 4. Invalid PAN
    pan_bad = provider.verify("PAN", "123INVALID")
    assert pan_bad.status == VerificationStatusEnum.FAILED

    # 5. Valid MSME Udyam
    msme_res = provider.verify("MSME", "UDYAM-MH-01-0012345")
    assert msme_res.status == VerificationStatusEnum.VERIFIED
    assert msme_res.is_mock is True


def test_verification_api_endpoints_and_idor(client, verification_test_env):
    """Test trigger verification endpoint, listing, and IDOR protection."""
    token1 = get_token(client, "bidder1_vrf@vendor.in", "VrfPass123")
    token2 = get_token(client, "bidder2_vrf@vendor.in", "VrfPass123")
    bid_id = verification_test_env["bid"].id

    # 1. Bidder 1 triggers GST verification
    post_res = client.post(
        f"/api/v1/verification/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token1}"},
        json={"verification_type": "GST", "identifier": "27AABCV1234F1Z5"},
    )
    assert post_res.status_code == status.HTTP_200_OK
    vrf_data = post_res.json()
    assert vrf_data["status"] == "VERIFIED"
    assert vrf_data["is_mock"] is True
    rec_id = vrf_data["id"]

    # 2. List verifications for bid
    list_res = client.get(
        f"/api/v1/verification/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 3. Get single verification record
    get_res = client.get(
        f"/api/v1/verification/{rec_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == rec_id

    # 4. IDOR Check: Bidder 2 blocked from triggering or viewing verification
    fail_post = client.post(
        f"/api/v1/verification/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token2}"},
        json={"verification_type": "GST", "identifier": "27AABCV1234F1Z5"},
    )
    assert fail_post.status_code == status.HTTP_403_FORBIDDEN

    fail_list = client.get(
        f"/api/v1/verification/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert fail_list.status_code == status.HTTP_403_FORBIDDEN
