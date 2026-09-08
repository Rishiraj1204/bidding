import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.tender import DocumentStatusEnum, Tender, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash
from backend.app.ocr.provider import LocalMockOCRProvider, get_ocr_provider


@pytest.fixture
def ocr_test_env(db):
    """Seed test user and bid for OCR testing."""
    user = User(
        id=str(uuid.uuid4()),
        email="ocr_tester@vendor.in",
        hashed_password=get_password_hash("OcrTestPass123"),
        full_name="OCR Verification Vendor",
        is_active=True,
    )
    db.add(user)
    db.commit()

    from backend.app.models.user import Role
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    if bidder_r:
        user.roles.append(bidder_r)

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-OCR-{uuid.uuid4().hex[:6]}",
        title="OCR Evaluation Tender",
        organization="Dept of IT",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=20),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=user.id,
    )
    db.add(tender)
    db.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=user.id,
        bid_number=f"BID-OCR-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid)
    db.commit()

    return {"user": user, "tender": tender, "bid": bid}


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_ocr_provider_direct_extraction():
    """Test LocalMockOCRProvider directly across document types."""
    provider = get_ocr_provider()

    # 1. Plain text extraction
    txt_bytes = b"Company Name: Tech Innovators Inc.\nAnnual Turnover: 50,00,000 INR"
    res_txt = provider.extract_text(txt_bytes, "financials.txt", "text/plain")
    assert res_txt.status == "COMPLETED"
    assert "Tech Innovators Inc." in res_txt.raw_text
    assert res_txt.ocr_confidence > 0.9
    assert res_txt.total_pages == 1

    # 2. PDF document context
    pdf_bytes = b"%PDF-1.4 (GOVERNMENT OF INDIA GSTIN 27AABCV1234F1Z5) Tj"
    res_pdf = provider.extract_text(pdf_bytes, "gst_cert.pdf", "application/pdf")
    assert res_pdf.status == "COMPLETED"
    assert res_pdf.ocr_confidence is not None
    assert res_pdf.ocr_confidence > 0.5
    assert len(res_pdf.raw_text) > 0

    # 3. Deliberately corrupted data -> must FAIL and NOT invent text
    corrupt_bytes = b"CORRUPT_DOCUMENT_PAYLOAD"
    res_corrupt = provider.extract_text(corrupt_bytes, "bad.pdf", "application/pdf")
    assert res_corrupt.status == "FAILED"
    assert res_corrupt.raw_text is None
    assert res_corrupt.error_message is not None


def test_ocr_pipeline_on_upload(client, ocr_test_env):
    """Test end-to-end OCR processing when document is uploaded."""
    token = get_token(client, "ocr_tester@vendor.in", "OcrTestPass123")
    bid_id = ocr_test_env["bid"].id

    pdf_content = b"%PDF-1.4 PAN Card Extraction AAACB1234K ACME TECH"
    file_tuple = ("pan_card.pdf", io.BytesIO(pdf_content), "application/pdf")

    # Upload with auto_ocr=True
    resp = client.post(
        f"/api/v1/documents/bid/{bid_id}?auto_ocr=true",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.PAN.value},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    doc_id = data["id"]
    assert data["status"] == "PROCESSED"
    assert data["has_ocr"] is True
    assert data["ocr_confidence"] is not None

    # Fetch OCR endpoint
    ocr_resp = client.get(
        f"/api/v1/documents/bid/{bid_id}/{doc_id}/ocr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ocr_resp.status_code == 200
    ocr_data = ocr_resp.json()
    assert ocr_data["document_id"] == doc_id
    assert ocr_data["status"] == "COMPLETED"
    assert ocr_data["raw_text"] is not None
    assert ocr_data["ocr_confidence"] is not None


def test_ocr_failure_preserves_original_document(client, ocr_test_env):
    """
    When OCR fails on a corrupted document, status becomes FAILED,
    raw_text is None, error message is recorded, and original document
    remains downloadable on disk.
    """
    token = get_token(client, "ocr_tester@vendor.in", "OcrTestPass123")
    bid_id = ocr_test_env["bid"].id

    # Corrupt document bytes with PDF magic header
    corrupt_content = b"%PDF-1.4 CORRUPT_DOCUMENT_PAYLOAD"
    file_tuple = ("corrupt_scan.pdf", io.BytesIO(corrupt_content), "application/pdf")

    upload_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}?auto_ocr=true",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.OTHER.value},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]
    assert upload_resp.json()["status"] == "FAILED"

    # Verify OCR endpoint reflects failure
    ocr_resp = client.get(
        f"/api/v1/documents/bid/{bid_id}/{doc_id}/ocr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ocr_resp.status_code == 200
    ocr_data = ocr_resp.json()
    assert ocr_data["status"] == "FAILED"
    assert ocr_data["raw_text"] is None
    assert ocr_data["error_message"] is not None

    # Verify original document is preserved and downloadable
    dl_resp = client.get(
        f"/api/v1/documents/bid/{bid_id}/{doc_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content == corrupt_content


def test_manual_trigger_ocr(client, ocr_test_env):
    """Test manual / re-run OCR trigger endpoint."""
    token = get_token(client, "ocr_tester@vendor.in", "OcrTestPass123")
    bid_id = ocr_test_env["bid"].id

    pdf_content = b"%PDF-1.4 GSTIN 27AABCV1234F1Z5 ACME TECHNOLOGIES"
    file_tuple = ("gst_doc.pdf", io.BytesIO(pdf_content), "application/pdf")

    # Upload with auto_ocr=False
    upload_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}?auto_ocr=false",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.GST_CERTIFICATE.value},
    )
    doc_id = upload_resp.json()["id"]
    assert upload_resp.json()["status"] == "UPLOADED"
    assert upload_resp.json()["has_ocr"] is False

    # Trigger OCR manually
    trigger_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}/{doc_id}/process-ocr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert trigger_resp.status_code == 200
    data = trigger_resp.json()
    assert data["status"] == "COMPLETED"
    assert data["raw_text"] is not None
    assert data["ocr_confidence"] is not None
