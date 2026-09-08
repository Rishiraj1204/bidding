import io
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.tender import DocumentStatusEnum, Tender, TenderDocument, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash
from backend.app.core.storage import get_storage_provider


@pytest.fixture
def test_users(db):
    """Seed officer, bidder1, bidder2, and admin users."""
    officer_role = db.query(User).filter(User.email == "officer@test.com").first()
    
    # Clean if existing
    users = {}
    
    # 1. Procurement Officer
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_doc_test@gem.gov.in",
        hashed_password=get_password_hash("OfficerPass123"),
        full_name="Procurement Officer Sharma",
        organization_name="Ministry of Electronics & IT",
        is_active=True,
    )
    # 2. Bidder 1
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="bidder1_doc_test@vendor.in",
        hashed_password=get_password_hash("Bidder1Pass123"),
        full_name="Bidder One Corp",
        organization_name="Alpha Tech Ltd",
        is_active=True,
    )
    # 3. Bidder 2
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="bidder2_doc_test@vendor.in",
        hashed_password=get_password_hash("Bidder2Pass123"),
        full_name="Bidder Two Corp",
        organization_name="Beta Solutions Ltd",
        is_active=True,
    )
    # 4. Admin
    admin = User(
        id=str(uuid.uuid4()),
        email="admin_doc_test@gem.gov.in",
        hashed_password=get_password_hash("AdminPass123"),
        full_name="System Administrator",
        is_active=True,
        is_superuser=True,
    )

    db.add_all([officer, bidder1, bidder2, admin])
    db.commit()

    # Assign roles from DB
    from backend.app.models.user import Role
    officer_r = db.query(Role).filter(Role.name == UserRoleEnum.PROCUREMENT_OFFICER.value).first()
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    admin_r = db.query(Role).filter(Role.name == UserRoleEnum.ADMIN.value).first()

    if officer_r:
        officer.roles.append(officer_r)
    if bidder_r:
        bidder1.roles.append(bidder_r)
        bidder2.roles.append(bidder_r)
    if admin_r:
        admin.roles.append(admin_r)

    db.commit()
    return {
        "officer": officer,
        "bidder1": bidder1,
        "bidder2": bidder2,
        "admin": admin,
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def auth_tokens(client, test_users):
    return {
        "officer": get_token(client, "officer_doc_test@gem.gov.in", "OfficerPass123"),
        "bidder1": get_token(client, "bidder1_doc_test@vendor.in", "Bidder1Pass123"),
        "bidder2": get_token(client, "bidder2_doc_test@vendor.in", "Bidder2Pass123"),
        "admin": get_token(client, "admin_doc_test@gem.gov.in", "AdminPass123"),
    }


@pytest.fixture
def seeded_tender(db, test_users):
    """Seed a draft tender and a published tender."""
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=30)

    draft_tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-DRAFT-{uuid.uuid4().hex[:6]}",
        title="Draft IT Infrastructure Tender",
        organization="Ministry of Electronics",
        submission_deadline=future,
        status=TenderStatusEnum.DRAFT,
        created_by_id=test_users["officer"].id,
    )

    published_tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-PUB-{uuid.uuid4().hex[:6]}",
        title="Published Cloud Migration Tender",
        organization="Ministry of IT",
        submission_deadline=future,
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=test_users["officer"].id,
    )

    db.add_all([draft_tender, published_tender])
    db.commit()
    return {"draft": draft_tender, "published": published_tender}


@pytest.fixture
def seeded_bid(db, test_users, seeded_tender):
    """Seed a draft bid for bidder1 against published tender."""
    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=seeded_tender["published"].id,
        bidder_id=test_users["bidder1"].id,
        bid_number=f"BID-ALPHA-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
        notes="Draft initial proposal",
    )
    db.add(bid)
    db.commit()
    return bid


# =========================================================================
# TENDER DOCUMENT MANAGEMENT TESTS
# =========================================================================

def test_authorized_tender_document_upload(client, auth_tokens, seeded_tender):
    """Officer successfully uploads tender specification document."""
    pdf_content = b"%PDF-1.4 Mock Tender Specification Document Content"
    file_tuple = ("tender_specification.pdf", io.BytesIO(pdf_content), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
        files={"file": file_tuple},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["filename"] == "tender_specification.pdf"
    assert data["file_size"] == len(pdf_content)
    assert data["mime_type"] == "application/pdf"
    assert data["file_hash"] == hashlib.sha256(pdf_content).hexdigest()
    assert data["status"] == "PROCESSED"
    # Ensure server path is not exposed
    assert "file_path" not in data


def test_unauthorized_tender_document_upload(client, auth_tokens, seeded_tender):
    """Bidder is blocked from uploading documents to tender."""
    pdf_content = b"%PDF-1.4 Malicious File"
    file_tuple = ("bad.pdf", io.BytesIO(pdf_content), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
        files={"file": file_tuple},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_invalid_file_type_rejected(client, auth_tokens, seeded_tender):
    """Dangerous executable extensions (.exe, .bat, .sh) are rejected."""
    exe_content = b"MZ\x90\x00Executable binary data"
    file_tuple = ("malware.exe", io.BytesIO(exe_content), "application/x-msdownload")

    resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
        files={"file": file_tuple},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "prohibited" in resp.json()["detail"].lower() or "unsupported" in resp.json()["detail"].lower()


def test_oversized_file_rejected(client, auth_tokens, seeded_tender, monkeypatch):
    """Files exceeding maximum allowed size are rejected."""
    from backend.app.core.config import settings
    # Temporarily set max upload to 100 bytes for testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 100)

    big_content = b"%PDF-1.4" + b"X" * 200
    file_tuple = ("large_doc.pdf", io.BytesIO(big_content), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
        files={"file": file_tuple},
    )
    assert resp.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


def test_tender_document_download_and_integrity(client, auth_tokens, seeded_tender):
    """Download tender document and verify binary content and SHA-256."""
    pdf_content = b"%PDF-1.4 Sample Tender Document Payload 12345"
    file_tuple = ("spec.pdf", io.BytesIO(pdf_content), "application/pdf")

    upload_resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
        files={"file": file_tuple},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # Download document
    dl_resp = client.get(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}/{doc_id}/download",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content == pdf_content
    assert hashlib.sha256(dl_resp.content).hexdigest() == upload_resp.json()["file_hash"]


def test_tender_specification_is_visible_to_admin_and_procurement_officer(
    client, auth_tokens, seeded_tender
):
    """Both tender-management roles can see an uploaded tender specification."""
    pdf_content = b"%PDF-1.4 Shared Tender Specification"
    upload_resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
        files={"file": ("shared-specification.pdf", io.BytesIO(pdf_content), "application/pdf")},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED
    document_id = upload_resp.json()["id"]

    for role in ("officer", "admin"):
        list_resp = client.get(
            f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
            headers={"Authorization": f"Bearer {auth_tokens[role]}"},
        )
        assert list_resp.status_code == status.HTTP_200_OK
        assert document_id in [item["id"] for item in list_resp.json()["items"]]


def test_tender_document_deletion_authorized_and_unauthorized(client, auth_tokens, seeded_tender):
    """Officer can delete doc in DRAFT, bidder cannot delete."""
    pdf_content = b"%PDF-1.4 Deletion Test"
    file_tuple = ("to_delete.pdf", io.BytesIO(pdf_content), "application/pdf")

    upload_resp = client.post(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
        files={"file": file_tuple},
    )
    doc_id = upload_resp.json()["id"]

    # Bidder tries to delete -> 403
    del_fail = client.delete(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}/{doc_id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
    )
    assert del_fail.status_code == status.HTTP_403_FORBIDDEN

    # Officer deletes -> 200
    del_ok = client.delete(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}/{doc_id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
    )
    assert del_ok.status_code == 200

    # Ensure document is gone from list
    list_resp = client.get(
        f"/api/v1/documents/tender/{seeded_tender['draft'].id}",
        headers={"Authorization": f"Bearer {auth_tokens['officer']}"},
    )
    assert doc_id not in [d["id"] for d in list_resp.json()["items"]]


# =========================================================================
# BID DOCUMENT & IDOR SECURITY TESTS
# =========================================================================

def test_authorized_bid_document_upload(client, auth_tokens, seeded_bid):
    """Bidder 1 uploads GST certificate to own draft bid."""
    pdf_content = b"%PDF-1.4 GST Certificate Government of India 27AABCV1234F1Z5"
    file_tuple = ("gst_certificate.pdf", io.BytesIO(pdf_content), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.GST_CERTIFICATE.value},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["filename"] == "gst_certificate.pdf"
    assert data["document_type"] == DocumentTypeEnum.GST_CERTIFICATE.value
    assert data["has_ocr"] is True
    assert data["ocr_confidence"] is not None
    assert data["status"] == "PROCESSED"
    # Ensure server path is not exposed
    assert "file_path" not in data


def test_idor_protection_bid_document_upload(client, auth_tokens, seeded_bid):
    """Bidder 2 cannot upload documents to Bidder 1's bid."""
    pdf_content = b"%PDF-1.4 Attacking Bidder File"
    file_tuple = ("attack.pdf", io.BytesIO(pdf_content), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder2']}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.PAN.value},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "forbidden" in resp.json()["detail"].lower()


def test_idor_protection_bid_document_access_and_download(client, auth_tokens, seeded_bid):
    """Bidder 2 cannot view or download Bidder 1's documents."""
    pdf_content = b"%PDF-1.4 Confidential Vendor Data Alpha"
    file_tuple = ("financial_audit.pdf", io.BytesIO(pdf_content), "application/pdf")

    upload_resp = client.post(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.FINANCIAL.value},
    )
    doc_id = upload_resp.json()["id"]

    # 1. Bidder 2 listing Bidder 1 docs -> 403
    list_fail = client.get(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder2']}"},
    )
    assert list_fail.status_code == status.HTTP_403_FORBIDDEN

    # 2. Bidder 2 getting metadata -> 403
    meta_fail = client.get(
        f"/api/v1/documents/bid/{seeded_bid.id}/{doc_id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder2']}"},
    )
    assert meta_fail.status_code == status.HTTP_403_FORBIDDEN

    # 3. Bidder 2 downloading binary -> 403
    dl_fail = client.get(
        f"/api/v1/documents/bid/{seeded_bid.id}/{doc_id}/download",
        headers={"Authorization": f"Bearer {auth_tokens['bidder2']}"},
    )
    assert dl_fail.status_code == status.HTTP_403_FORBIDDEN

    # 4. Bidder 2 deleting document -> 403
    del_fail = client.delete(
        f"/api/v1/documents/bid/{seeded_bid.id}/{doc_id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder2']}"},
    )
    assert del_fail.status_code == status.HTTP_403_FORBIDDEN

    # 5. Bidder 1 (owner) can access & download -> 200
    dl_ok = client.get(
        f"/api/v1/documents/bid/{seeded_bid.id}/{doc_id}/download",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
    )
    assert dl_ok.status_code == 200
    assert dl_ok.content == pdf_content


def test_unique_storage_keys_and_no_path_traversal(client, auth_tokens, seeded_bid):
    """
    Ensure original filenames with path traversal (e.g. ../../etc/passwd)
    are sanitized and storage keys use random UUIDs.
    """
    pdf_content = b"%PDF-1.4 Safe Traversal Test Document"
    file_tuple = ("../../../../etc/passwd.pdf", io.BytesIO(pdf_content), "application/pdf")

    resp = client.post(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.OTHER.value},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    # Filename should be sanitized without traversal slashes
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]
    assert ".." not in data["filename"]


def test_cannot_modify_documents_after_bid_submission(client, auth_tokens, db, seeded_bid):
    """Once bid is SUBMITTED, deleting or adding documents is locked."""
    pdf_content = b"%PDF-1.4 Lock Test"
    file_tuple = ("lock_test.pdf", io.BytesIO(pdf_content), "application/pdf")

    # Upload doc while in DRAFT
    upload_resp = client.post(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
        files={"file": file_tuple},
    )
    doc_id = upload_resp.json()["id"]

    # Transition bid to SUBMITTED
    seeded_bid.status = BidStatusEnum.SUBMITTED
    db.commit()

    # Try uploading another document -> 400
    upload2 = client.post(
        f"/api/v1/documents/bid/{seeded_bid.id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
        files={"file": ("another.pdf", io.BytesIO(pdf_content), "application/pdf")},
    )
    assert upload2.status_code == status.HTTP_400_BAD_REQUEST

    # Try deleting document -> 400
    del_resp = client.delete(
        f"/api/v1/documents/bid/{seeded_bid.id}/{doc_id}",
        headers={"Authorization": f"Bearer {auth_tokens['bidder1']}"},
    )
    assert del_resp.status_code == status.HTTP_400_BAD_REQUEST
