import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.compliance import ComplianceStatusEnum
from backend.app.models.tender import RequirementCategoryEnum, Tender, TenderRequirement, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash


@pytest.fixture
def compliance_test_env(db):
    """Seed test users, tender with requirements, and a bid with uploaded documents."""
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="bidder1_comp@vendor.in",
        hashed_password=get_password_hash("CompPass123"),
        full_name="Prime Infrastructure Ltd",
        organization_name="Prime Infra Ltd",
        is_active=True,
    )
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="bidder2_comp@vendor.in",
        hashed_password=get_password_hash("CompPass123"),
        full_name="Secondary Bidder",
        is_active=True,
    )
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_comp@gem.gov.in",
        hashed_password=get_password_hash("CompPass123"),
        full_name="Officer Sharma",
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

    # Create Tender
    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number=f"TND-CMP-{uuid.uuid4().hex[:6]}",
        title="Highway Sensor Installation & Telematics Tender",
        organization="National Highways Authority",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=30),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    # Requirements:
    # 1. GST Registration (Mandatory, exists)
    req1 = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.ELIGIBILITY,
        requirement_text="Bidder must have a valid Active Indian GSTIN registration.",
        parameter="gstin",
        operator="exists",
        mandatory=True,
    )
    # 2. Annual Turnover >= 10 Crores (100,000,000 INR)
    req2 = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.FINANCIAL,
        requirement_text="Minimum average annual turnover of at least INR 10 Crores.",
        parameter="annual_turnover",
        operator=">=",
        threshold_value="100000000.0",
        unit="INR",
        mandatory=True,
    )
    # 3. Experience >= 3 Years
    req3 = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.EXPERIENCE,
        requirement_text="Minimum 3 years past experience in similar telemetry deployments.",
        parameter="experience_years",
        operator=">=",
        threshold_value="3.0",
        unit="years",
        mandatory=True,
    )
    # 4. Optional MSME Udyam Certificate (Optional)
    req4 = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.CERTIFICATION,
        requirement_text="MSME / Udyam registration for purchase preference.",
        parameter="msme_number",
        operator="exists",
        mandatory=False,
    )
    db.add_all([req1, req2, req3, req4])
    db.commit()

    # Create Bid for Bidder 1
    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder1.id,
        bid_number=f"BID-CMP-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.DRAFT,
    )
    db.add(bid)
    db.commit()

    return {
        "bidder1": bidder1,
        "bidder2": bidder2,
        "officer": officer,
        "tender": tender,
        "bid": bid,
        "req1": req1,
        "req2": req2,
        "req3": req3,
        "req4": req4,
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_compliance_evaluation_full_pass(client, compliance_test_env):
    """Upload documents satisfying all requirements -> Bid evaluated as COMPLIANT."""
    token = get_token(client, "bidder1_comp@vendor.in", "CompPass123")
    bid_id = compliance_test_env["bid"].id

    # 1. Upload Doc 1: GST & PAN
    doc1 = "%PDF-1.4\nGSTIN: 27AABCV1234F1Z5\nLegal Name: PRIME INFRASTRUCTURE LTD\nPAN: AAACB1234K"
    client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("gst.pdf", io.BytesIO(doc1.encode("utf-8")), "application/pdf")},
        data={"document_type": DocumentTypeEnum.GST_CERTIFICATE.value},
    )

    # 2. Upload Doc 2: Financials (Turnover 15.4 Crores > 10 Crores threshold)
    doc2 = "%PDF-1.4\nAnnual Turnover: INR 15.4 Crores\nNet Worth: INR 5 Crores"
    client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("fin.pdf", io.BytesIO(doc2.encode("utf-8")), "application/pdf")},
        data={"document_type": DocumentTypeEnum.FINANCIAL.value},
    )

    # 3. Upload Doc 3: Experience (4 Years > 3 Years threshold)
    doc3 = "%PDF-1.4\nPeriod of Execution: 4.0 Years\nClient: Indian Highway Authority"
    client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("exp.pdf", io.BytesIO(doc3.encode("utf-8")), "application/pdf")},
        data={"document_type": DocumentTypeEnum.EXPERIENCE.value},
    )

    # Run AI Extraction on all docs
    client.post(f"/api/v1/extraction/bid/{bid_id}", headers={"Authorization": f"Bearer {token}"})

    # Evaluate Compliance
    eval_resp = client.post(
        f"/api/v1/compliance/bid/{bid_id}/evaluate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert eval_resp.status_code == status.HTTP_200_OK
    summary = eval_resp.json()

    assert summary["bid_id"] == bid_id
    assert summary["total_requirements"] == 4
    assert summary["compliant_count"] >= 3
    assert summary["mandatory_passed"] is True
    assert summary["overall_status"] == ComplianceStatusEnum.COMPLIANT.value

    # Check requirement results
    results_map = {r["parameter"]: r for r in summary["results"] if r.get("parameter")}
    assert results_map["gstin"]["status"] == ComplianceStatusEnum.COMPLIANT.value
    assert results_map["gstin"]["verification_status"] == "VERIFIED"
    assert results_map["gstin"]["is_mock_verification"] is True
    assert results_map["annual_turnover"]["status"] == ComplianceStatusEnum.COMPLIANT.value
    assert results_map["experience_years"]["status"] == ComplianceStatusEnum.COMPLIANT.value


def test_compliance_evaluation_mandatory_failed(client, compliance_test_env, db):
    """Turnover of 5 Crores fails the mandatory 10 Crores threshold -> NON_COMPLIANT."""
    token = get_token(client, "bidder1_comp@vendor.in", "CompPass123")
    bid_id = compliance_test_env["bid"].id

    # Upload Doc: Low turnover (5 Crores < 10 Crores)
    doc_fin = "%PDF-1.4\nAnnual Turnover: INR 5 Crores"
    client.post(
        f"/api/v1/documents/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("low_fin.pdf", io.BytesIO(doc_fin.encode("utf-8")), "application/pdf")},
        data={"document_type": DocumentTypeEnum.FINANCIAL.value},
    )

    # Run extraction and evaluate
    client.post(f"/api/v1/extraction/bid/{bid_id}", headers={"Authorization": f"Bearer {token}"})
    eval_resp = client.post(
        f"/api/v1/compliance/bid/{bid_id}/evaluate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert eval_resp.status_code == 200
    summary = eval_resp.json()

    assert summary["mandatory_passed"] is False
    assert summary["overall_status"] == ComplianceStatusEnum.NON_COMPLIANT.value
    assert summary["non_compliant_count"] >= 1


def test_compliance_no_evidence_never_compliant(client, compliance_test_env):
    """A fresh bid with 0 uploaded documents must NEVER be marked COMPLIANT."""
    token = get_token(client, "bidder1_comp@vendor.in", "CompPass123")
    bid_id = compliance_test_env["bid"].id

    eval_resp = client.post(
        f"/api/v1/compliance/bid/{bid_id}/evaluate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert eval_resp.status_code == 200
    summary = eval_resp.json()

    assert summary["overall_status"] == ComplianceStatusEnum.NON_COMPLIANT.value
    assert summary["compliant_count"] == 0
    assert summary["mandatory_passed"] is False


def test_compliance_idor_isolation(client, compliance_test_env):
    """Bidder 2 cannot evaluate or view compliance summary for Bidder 1's bid."""
    token1 = get_token(client, "bidder1_comp@vendor.in", "CompPass123")
    token2 = get_token(client, "bidder2_comp@vendor.in", "CompPass123")
    bid_id = compliance_test_env["bid"].id

    # Bidder 2 attempts evaluate -> 403
    eval_fail = client.post(
        f"/api/v1/compliance/bid/{bid_id}/evaluate",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert eval_fail.status_code == status.HTTP_403_FORBIDDEN

    # Bidder 2 attempts get -> 403
    get_fail = client.get(
        f"/api/v1/compliance/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert get_fail.status_code == status.HTTP_403_FORBIDDEN
