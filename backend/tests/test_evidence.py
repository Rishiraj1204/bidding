import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.tender import DocumentStatusEnum, Tender, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash


@pytest.fixture
def evidence_test_env(db):
    """Seed test environment with bidders, officer, tender, and bid with extracted evidence."""
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="evidence_bidder1@vendor.in",
        hashed_password=get_password_hash("Pass123"),
        full_name="Bidder One Evidence Corp",
        is_active=True,
    )
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="evidence_bidder2@vendor.in",
        hashed_password=get_password_hash("Pass123"),
        full_name="Bidder Two Evidence Corp",
        is_active=True,
    )
    officer = User(
        id=str(uuid.uuid4()),
        email="evidence_officer@gem.gov.in",
        hashed_password=get_password_hash("Pass123"),
        full_name="Officer Evidence",
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
        tender_number=f"TND-EVI-{uuid.uuid4().hex[:6]}",
        title="Evidence Traceability Tender",
        organization="Govt Procurement Authority",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=25),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder1.id,
        bid_number=f"BID-EVI-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid)
    db.commit()

    return {"bidder1": bidder1, "bidder2": bidder2, "officer": officer, "bid": bid}


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_evidence_listing_and_filtering(client, evidence_test_env):
    """Test retrieving and filtering evidence records by field_name."""
    token1 = get_token(client, "evidence_bidder1@vendor.in", "Pass123")
    bid_id = evidence_test_env["bid"].id

    doc_text = (
        "%PDF-1.4\n"
        "GOVERNMENT OF INDIA GSTIN: 27AABCV1234F1Z5\n"
        "Permanent Account Number: AAACB1234K\n"
        "Annual Turnover: INR 18.5 Crores\n"
    )
    file_tuple = ("tax_doc.pdf", io.BytesIO(doc_text.encode("utf-8")), "application/pdf")

    # Upload document
    upload_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token1}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.FINANCIAL.value},
    )
    doc_id = upload_resp.json()["id"]

    # Run extraction
    ext_resp = client.post(
        f"/api/v1/extraction/bid/{bid_id}/document/{doc_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert ext_resp.status_code == 200

    # 1. Fetch all evidence records
    all_evi = client.get(
        f"/api/v1/evidence/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert all_evi.status_code == 200
    evi_data = all_evi.json()
    assert evi_data["total"] >= 2
    assert len(evi_data["items"]) >= 2

    first_item = evi_data["items"][0]
    assert first_item["snippet_text"] is not None
    assert first_item["confidence"] > 0.5
    assert first_item["document_filename"] == "tax_doc.pdf"

    # 2. Filter evidence by field_name=gstin
    gstin_evi = client.get(
        f"/api/v1/evidence/bid/{bid_id}?field_name=gstin",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert gstin_evi.status_code == 200
    gst_items = gstin_evi.json()["items"]
    assert len(gst_items) == 1
    assert gst_items[0]["field_name"] == "gstin"
    assert gst_items[0]["normalized_value"] == "27AABCV1234F1Z5"

    # 3. Filter evidence by document_id
    doc_evi = client.get(
        f"/api/v1/evidence/bid/{bid_id}/document/{doc_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert doc_evi.status_code == 200
    assert doc_evi.json()["total"] >= 2

    # 4. Fetch single evidence item by ID
    single_evi = client.get(
        f"/api/v1/evidence/{first_item['id']}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert single_evi.status_code == 200
    assert single_evi.json()["id"] == first_item["id"]


def test_evidence_idor_protection(client, evidence_test_env):
    """Bidder 2 is blocked from viewing Bidder 1's evidence records."""
    token1 = get_token(client, "evidence_bidder1@vendor.in", "Pass123")
    token2 = get_token(client, "evidence_bidder2@vendor.in", "Pass123")
    token_officer = get_token(client, "evidence_officer@gem.gov.in", "Pass123")
    bid_id = evidence_test_env["bid"].id

    doc_text = "%PDF-1.4 GSTIN: 27AABCV1234F1Z5 Confidential Alpha"
    file_tuple = ("doc.pdf", io.BytesIO(doc_text.encode("utf-8")), "application/pdf")

    upload_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token1}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.GST_CERTIFICATE.value},
    )
    doc_id = upload_resp.json()["id"]

    client.post(
        f"/api/v1/extraction/bid/{bid_id}/document/{doc_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Bidder 2 attempts access -> 403
    evi_fail = client.get(
        f"/api/v1/evidence/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert evi_fail.status_code == status.HTTP_403_FORBIDDEN

    # Officer can access for audit/review -> 200
    officer_ok = client.get(
        f"/api/v1/evidence/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token_officer}"},
    )
    assert officer_ok.status_code == 200
    assert officer_ok.json()["total"] >= 1
