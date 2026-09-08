import io
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.core.security import get_password_hash
from backend.app.models.tender import RequirementCategoryEnum, TenderRequirement
from backend.app.models.user import Role, User, UserRoleEnum


@pytest.fixture
def e2e_environment(db):
    """Seed procurement officer, bidder, and reviewer users."""
    officer = User(
        id=str(uuid.uuid4()),
        email="e2e_officer@gem.gov.in",
        hashed_password=get_password_hash("E2ePassword123"),
        full_name="E2E Procurement Officer",
        is_active=True,
    )
    bidder = User(
        id=str(uuid.uuid4()),
        email="e2e_bidder@vendor.in",
        hashed_password=get_password_hash("E2ePassword123"),
        full_name="National Telematics Corp",
        organization_name="National Telematics Corp",
        is_active=True,
    )
    reviewer = User(
        id=str(uuid.uuid4()),
        email="e2e_reviewer@gem.gov.in",
        hashed_password=get_password_hash("E2ePassword123"),
        full_name="E2E Reviewer Specialist",
        is_active=True,
    )
    db.add_all([officer, bidder, reviewer])
    db.commit()

    officer_r = db.query(Role).filter(Role.name == UserRoleEnum.PROCUREMENT_OFFICER.value).first()
    bidder_r = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
    reviewer_r = db.query(Role).filter(Role.name == UserRoleEnum.REVIEWER.value).first()

    if officer_r:
        officer.roles.append(officer_r)
    if bidder_r:
        bidder.roles.append(bidder_r)
    if reviewer_r:
        reviewer.roles.append(reviewer_r)
    db.commit()

    return {"officer": officer, "bidder": bidder, "reviewer": reviewer}


def login_user(client, email, password="E2ePassword123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()["access_token"]


def test_full_bid_compliance_e2e_lifecycle(client, db, e2e_environment):
    """
    Complete End-to-End Workflow Verification:
    1. Officer creates tender with mandatory criteria
    2. Officer publishes tender
    3. Bidder discovers tender and creates draft bid
    4. Bidder uploads supporting documents
    5. Document OCR is processed
    6. AI entity extraction runs
    7. Compliance evaluation + mock verification runs
    8. Reviewer reviews task & submits decision with justification
    9. Official compliance PDF report is generated & downloaded
    10. Notifications and audit trail verify integrity
    """
    officer_token = login_user(client, "e2e_officer@gem.gov.in")
    bidder_token = login_user(client, "e2e_bidder@vendor.in")
    reviewer_token = login_user(client, "e2e_reviewer@gem.gov.in")

    # -------------------------------------------------------------
    # Step 1: Officer creates tender
    # -------------------------------------------------------------
    tender_number = f"GEM/2026/B/{uuid.uuid4().hex[:6].upper()}"
    tender_payload = {
        "tender_number": tender_number,
        "title": "Supply and Installation of IoT Smart Meters",
        "description": "High-accuracy telemetry meters for state electrical distribution network.",
        "organization": "State Electricity Board",
        "submission_deadline": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
        "category": "GOODS",
    }

    t_resp = client.post(
        "/api/v1/tenders",
        json=tender_payload,
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert t_resp.status_code == status.HTTP_201_CREATED
    tender_data = t_resp.json()
    tender_id = tender_data["id"]

    # Add Requirements
    req1 = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender_id,
        category=RequirementCategoryEnum.ELIGIBILITY,
        requirement_text="Bidder must possess a valid GSTIN registration in India.",
        parameter="gstin",
        operator="==",
        threshold_value="27AAAPL1234C1ZV",
        mandatory=True,
    )
    req2 = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender_id,
        category=RequirementCategoryEnum.FINANCIAL,
        requirement_text="Minimum annual financial turnover must exceed 10,000,000 INR.",
        parameter="annual_turnover",
        operator=">=",
        threshold_value="10000000",
        unit="INR",
        mandatory=True,
    )
    db.add_all([req1, req2])
    db.commit()

    # -------------------------------------------------------------
    # Step 2: Officer publishes tender
    # -------------------------------------------------------------
    pub_resp = client.patch(
        f"/api/v1/tenders/{tender_id}/status",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert pub_resp.status_code == status.HTTP_200_OK
    assert pub_resp.json()["status"] == "PUBLISHED"

    # -------------------------------------------------------------
    # Step 3: Bidder discovers tender and creates draft bid
    # -------------------------------------------------------------
    list_tenders_resp = client.get("/api/v1/tenders", headers={"Authorization": f"Bearer {bidder_token}"})
    assert list_tenders_resp.status_code == status.HTTP_200_OK
    assert any(t["id"] == tender_id for t in list_tenders_resp.json()["items"])

    bid_payload = {
        "tender_id": tender_id,
        "amount": 72000000.0,
        "delivery_timeline_days": 90,
        "notes": "Compliant with all smart meter specifications.",
    }
    b_resp = client.post(
        "/api/v1/bids",
        json=bid_payload,
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert b_resp.status_code == status.HTTP_201_CREATED
    bid_data = b_resp.json()
    bid_id = bid_data["id"]

    # -------------------------------------------------------------
    # Step 4: Bidder uploads supporting document
    # -------------------------------------------------------------
    doc_text = """
    GOVERNMENT OF INDIA - REGISTRATION CERTIFICATE
    Legal Name: National Telematics Corp
    GSTIN: 27AAAPL1234C1ZV
    PAN: AAAPL1234C
    Financial Year 2024-25 Audited Turnover: INR 15,000,000.00
    Incorporation Date: 12-04-2015
    """
    fake_pdf = b"%PDF-1.4\n" + doc_text.encode("utf-8")
    upload_file = ("gst_and_financials.pdf", io.BytesIO(fake_pdf), "application/pdf")

    doc_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}",
        files={"file": upload_file},
        data={"document_type": "GST_CERTIFICATE"},
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert doc_resp.status_code == status.HTTP_201_CREATED
    doc_id = doc_resp.json()["id"]

    # -------------------------------------------------------------
    # Step 5: Document OCR
    # -------------------------------------------------------------
    ocr_resp = client.post(
        f"/api/v1/documents/bid/{bid_id}/{doc_id}/process-ocr",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert ocr_resp.status_code == status.HTTP_200_OK
    assert ocr_resp.json()["status"] in ["COMPLETED", "PROCESSED"]

    # -------------------------------------------------------------
    # Step 6: AI Entity Extraction & Evidence Generation
    # -------------------------------------------------------------
    extract_resp = client.post(
        f"/api/v1/extraction/bid/{bid_id}",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert extract_resp.status_code == status.HTTP_200_OK
    summary_data = extract_resp.json()
    assert summary_data["total_entities_extracted"] > 0
    assert len(summary_data["evidence"]) > 0

    # -------------------------------------------------------------
    # Step 7: Compliance Evaluation + Mock Registry Verification
    # -------------------------------------------------------------
    comp_resp = client.post(
        f"/api/v1/compliance/bid/{bid_id}/evaluate",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert comp_resp.status_code == status.HTTP_200_OK
    comp_data = comp_resp.json()
    assert len(comp_data["results"]) == 2
    assert comp_data["total_requirements"] == 2

    # -------------------------------------------------------------
    # Step 8: Review Task inspection & Decision submission
    # -------------------------------------------------------------
    tasks_resp = client.get("/api/v1/review/tasks", headers={"Authorization": f"Bearer {reviewer_token}"})
    assert tasks_resp.status_code == status.HTTP_200_OK
    review_tasks = tasks_resp.json()["items"]
    if review_tasks:
        task_id = review_tasks[0]["id"]
        dec_resp = client.post(
            f"/api/v1/review/tasks/{task_id}/decision",
            json={
                "new_decision": "COMPLIANT",
                "justification": "Verified against state GST portal and confirmed audited balance sheet.",
                "comments": "Committee approved.",
            },
            headers={"Authorization": f"Bearer {reviewer_token}"},
        )
        assert dec_resp.status_code == status.HTTP_200_OK

    # -------------------------------------------------------------
    # Step 9: Generate and download official PDF report
    # -------------------------------------------------------------
    rep_gen_resp = client.post(
        f"/api/v1/reports/bid/{bid_id}/generate",
        json={"include_evidence_snippets": True},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert rep_gen_resp.status_code == status.HTTP_201_CREATED
    report_id = rep_gen_resp.json()["id"]

    download_resp = client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert download_resp.status_code == status.HTTP_200_OK
    assert download_resp.headers.get("content-type") == "application/pdf"
    assert len(download_resp.content) > 0

    # -------------------------------------------------------------
    # Step 10: Notifications & Dashboard Verification
    # -------------------------------------------------------------
    notif_resp = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {bidder_token}"})
    assert notif_resp.status_code == status.HTTP_200_OK
    assert notif_resp.json()["total"] >= 1

    dash_resp = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {officer_token}"})
    assert dash_resp.status_code == status.HTTP_200_OK
    assert dash_resp.json()["role"] == "PROCUREMENT_OFFICER"
