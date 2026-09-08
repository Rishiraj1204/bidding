import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.tender import DocumentStatusEnum, Tender, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash
from backend.app.ai.provider import LocalDeterministicAIExtractionProvider, get_ai_provider


@pytest.fixture
def extraction_test_env(db):
    """Seed test users, tender, and bids."""
    # 1. Bidder 1
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="bidder1_ext@vendor.in",
        hashed_password=get_password_hash("Bidder1Pass123"),
        full_name="Alpha Infotech Corp",
        organization_name="Alpha Infotech Ltd",
        is_active=True,
    )
    # 2. Bidder 2
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="bidder2_ext@vendor.in",
        hashed_password=get_password_hash("Bidder2Pass123"),
        full_name="Beta Systems Corp",
        organization_name="Beta Systems Ltd",
        is_active=True,
    )
    # 3. Officer
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_ext@gem.gov.in",
        hashed_password=get_password_hash("OfficerPass123"),
        full_name="Procurement Officer Verma",
        organization_name="Ministry of Electronics",
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
        tender_number=f"TND-EXT-{uuid.uuid4().hex[:6]}",
        title="AI Cloud Modernization Tender",
        organization="Govt Dept of Technology",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=30),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    bid1 = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder1.id,
        bid_number=f"BID-ALPHA-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid1)
    db.commit()

    return {
        "bidder1": bidder1,
        "bidder2": bidder2,
        "officer": officer,
        "tender": tender,
        "bid1": bid1,
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_ai_provider_normalization_and_hallucination_defense():
    """Verify local AI provider extracts only grounded entities and standardizes formats."""
    provider = get_ai_provider()

    sample_ocr_text = (
        "GOVERNMENT OF INDIA - GST CERTIFICATE\n"
        "GSTIN: 27AABCV1234F1Z5\n"
        "Legal Name: ACME TECHNOLOGIES PVT LTD\n"
        "PAN Number: AAACB1234K\n"
        "Annual Turnover: INR 15,40,00,000\n"
        "Net Worth: INR 6,20,00,000\n"
        "Period of Execution: 3.5 Years\n"
        "UDYAM Registration: UDYAM-MH-01-0012345\n"
        "Date of Issue: 12/04/2019"
    )

    result = provider.extract_entities(sample_ocr_text, "GST_CERTIFICATE", "gst.pdf")
    assert result.status == "COMPLETED"
    assert len(result.entities) >= 7

    entity_map = {e.entity_type: e for e in result.entities}

    # GSTIN check
    assert "gstin" in entity_map
    assert entity_map["gstin"].normalized_value == "27AABCV1234F1Z5"
    assert entity_map["gstin"].confidence >= 0.9

    # PAN check
    assert "pan_number" in entity_map
    assert entity_map["pan_number"].normalized_value == "AAACB1234K"

    # Company name check
    assert "company_name" in entity_map
    assert "PRIVATE LIMITED" in entity_map["company_name"].normalized_value

    # Turnover check
    assert "annual_turnover" in entity_map
    assert entity_map["annual_turnover"].normalized_value == "154000000.0"

    # Experience check
    assert "experience_years" in entity_map
    assert entity_map["experience_years"].normalized_value == "3.5"

    # MSME check
    assert "msme_number" in entity_map
    assert entity_map["msme_number"].normalized_value == "UDYAM-MH-01-0012345"

    # Date check
    assert "issue_date" in entity_map
    assert entity_map["issue_date"].normalized_value == "2019-04-12"

    # Hallucination check: absent fields are not invented
    unrelated_text = "This is a simple terms and conditions document with no financial or tax identifiers."
    unrelated_res = provider.extract_entities(unrelated_text, "OTHER", "terms.txt")
    assert len(unrelated_res.entities) == 0


def test_document_ai_extraction_endpoint(client, extraction_test_env):
    """Upload document, run extraction endpoint, verify entities and evidence created."""
    token = get_token(client, "bidder1_ext@vendor.in", "Bidder1Pass123")
    bid_id = extraction_test_env["bid1"].id

    doc_text = (
        "%PDF-1.4\n"
        "FORM GST REG-06\n"
        "GSTIN: 27AABCV1234F1Z5\n"
        "Legal Name: ALPHA INFOTECH PRIVATE LIMITED\n"
        "Permanent Account Number: AAACB1234K\n"
        "Date of Issue: 15/08/2020\n"
    )
    file_tuple = ("gst_cert.pdf", io.BytesIO(doc_text.encode("utf-8")), "application/pdf")

    # 1. Upload document
    upload_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.GST_CERTIFICATE.value},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED
    doc_id = upload_resp.json()["id"]

    # 2. Trigger Extraction
    ext_resp = client.post(
        f"/api/v1/extraction/bid/{bid_id}/document/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ext_resp.status_code == status.HTTP_200_OK
    ext_data = ext_resp.json()
    assert ext_data["status"] == "COMPLETED"
    assert len(ext_data["entities"]) >= 3
    assert len(ext_data["evidence_records"]) >= 3

    # Check evidence record linking
    ev_fields = {ev["field_name"]: ev for ev in ext_data["evidence_records"]}
    assert "gstin" in ev_fields
    assert ev_fields["gstin"]["normalized_value"] == "27AABCV1234F1Z5"
    assert ev_fields["gstin"]["source_type"] == "AI_EXTRACTION"
    assert ev_fields["gstin"]["snippet_text"] is not None


def test_idor_protection_ai_extraction(client, extraction_test_env):
    """Bidder 2 cannot trigger or view AI extraction on Bidder 1's bid."""
    token1 = get_token(client, "bidder1_ext@vendor.in", "Bidder1Pass123")
    token2 = get_token(client, "bidder2_ext@vendor.in", "Bidder2Pass123")
    bid_id = extraction_test_env["bid1"].id

    doc_text = "%PDF-1.4 GSTIN: 27AABCV1234F1Z5 Legal Name: ALPHA"
    file_tuple = ("doc.pdf", io.BytesIO(doc_text.encode("utf-8")), "application/pdf")

    upload_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token1}"},
        files={"file": file_tuple},
        data={"document_type": DocumentTypeEnum.GST_CERTIFICATE.value},
    )
    doc_id = upload_resp.json()["id"]

    # Bidder 2 attempts extraction on Bidder 1's document -> 403
    ext_fail = client.post(
        f"/api/v1/extraction/bid/{bid_id}/document/{doc_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert ext_fail.status_code == status.HTTP_403_FORBIDDEN

    # Bidder 2 attempts viewing extraction -> 403
    get_fail = client.get(
        f"/api/v1/extraction/bid/{bid_id}/document/{doc_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert get_fail.status_code == status.HTTP_403_FORBIDDEN

    # Bidder 2 attempts viewing all entities -> 403
    all_fail = client.get(
        f"/api/v1/extraction/bid/{bid_id}/entities",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert all_fail.status_code == status.HTTP_403_FORBIDDEN


def test_batch_bid_extraction_endpoint(client, extraction_test_env):
    """Test extracting all documents of a bid in a single call."""
    token = get_token(client, "bidder1_ext@vendor.in", "Bidder1Pass123")
    bid_id = extraction_test_env["bid1"].id

    # Upload Doc 1: Financials
    doc1 = "%PDF-1.4 Annual Turnover: INR 25 Crores Net Worth: INR 10 Crores"
    client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("fin.pdf", io.BytesIO(doc1.encode("utf-8")), "application/pdf")},
        data={"document_type": DocumentTypeEnum.FINANCIAL.value},
    )

    # Upload Doc 2: Experience
    doc2 = "%PDF-1.4 Period of Execution: 4 Years Client: Indian Railways"
    client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("exp.pdf", io.BytesIO(doc2.encode("utf-8")), "application/pdf")},
        data={"document_type": DocumentTypeEnum.EXPERIENCE.value},
    )

    # Batch extraction call
    batch_resp = client.post(
        f"/api/v1/extraction/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert batch_resp.status_code == status.HTTP_200_OK
    summary = batch_resp.json()
    assert summary["bid_id"] == bid_id
    assert summary["total_documents"] >= 2
    assert summary["total_entities_extracted"] >= 3
    assert summary["total_evidence_records"] >= 3
