import io
import os
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import status

from backend.app.models.bid import Bid, BidStatusEnum
from backend.app.models.compliance import ComplianceResult, ComplianceStatusEnum
from backend.app.models.tender import RequirementCategoryEnum, Tender, TenderRequirement, TenderStatusEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.core.security import get_password_hash


@pytest.fixture
def report_test_env(db):
    """Seed test users, tender, bid, and compliance evaluations."""
    bidder1 = User(
        id=str(uuid.uuid4()),
        email="bidder1_rpt@vendor.in",
        hashed_password=get_password_hash("RptPass123"),
        full_name="Report Vendor One Ltd",
        organization_name="Report Vendor One Ltd",
        is_active=True,
    )
    bidder2 = User(
        id=str(uuid.uuid4()),
        email="bidder2_rpt@vendor.in",
        hashed_password=get_password_hash("RptPass123"),
        full_name="Report Vendor Two Ltd",
        is_active=True,
    )
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_rpt@gem.gov.in",
        hashed_password=get_password_hash("RptPass123"),
        full_name="Procurement Officer Patel",
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
        tender_number=f"TND-RPT-{uuid.uuid4().hex[:6]}",
        title="Smart Water Metering Network Deployment",
        organization="Municipal Water Authority",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=20),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db.add(tender)
    db.commit()

    req = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.ELIGIBILITY,
        requirement_text="Valid GST Registration Certificate.",
        parameter="gstin",
        operator="exists",
        mandatory=True,
    )
    db.add(req)
    db.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder1.id,
        bid_number=f"BID-RPT-{uuid.uuid4().hex[:6]}",
        status=BidStatusEnum.SUBMITTED,
    )
    db.add(bid)
    db.commit()

    comp_res = ComplianceResult(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        requirement_id=req.id,
        status=ComplianceStatusEnum.COMPLIANT,
        reason="Valid GSTIN found and verified in GSTN mock registry.",
        confidence=0.98,
        evaluated_by="RULE_ENGINE",
    )
    db.add(comp_res)
    db.commit()

    return {
        "bidder1": bidder1,
        "bidder2": bidder2,
        "officer": officer,
        "tender": tender,
        "bid": bid,
        "comp_res": comp_res,
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def test_generate_and_download_compliance_report(client, report_test_env):
    """Generate PDF compliance report and download it via REST API."""
    token = get_token(client, "officer_rpt@gem.gov.in", "RptPass123")
    bid_id = report_test_env["bid"].id

    # 1. Generate Report
    gen_resp = client.post(
        f"/api/v1/reports/bid/{bid_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen_resp.status_code == status.HTTP_201_CREATED
    rpt_data = gen_resp.json()
    assert rpt_data["bid_id"] == bid_id
    assert rpt_data["report_number"].startswith("RPT-BID-")
    assert rpt_data["file_path"] is not None
    assert os.path.exists(rpt_data["file_path"])
    report_id = rpt_data["id"]

    # 2. List reports for bid
    list_resp = client.get(
        f"/api/v1/reports/bid/{bid_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. Download PDF
    download_resp = client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert len(download_resp.content) > 500  # Valid PDF binary


def test_report_idor_isolation(client, report_test_env):
    """Bidder 2 cannot generate or view reports for Bidder 1's bid."""
    token1 = get_token(client, "bidder1_rpt@vendor.in", "RptPass123")
    token2 = get_token(client, "bidder2_rpt@vendor.in", "RptPass123")
    bid_id = report_test_env["bid"].id

    # Bidder 1 generates report
    gen_resp = client.post(
        f"/api/v1/reports/bid/{bid_id}/generate",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert gen_resp.status_code == 201
    rpt_id = gen_resp.json()["id"]

    # Bidder 2 attempts to generate -> 403 Forbidden
    fail_gen = client.post(
        f"/api/v1/reports/bid/{bid_id}/generate",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert fail_gen.status_code == status.HTTP_403_FORBIDDEN

    # Bidder 2 attempts to download -> 403 Forbidden
    fail_dl = client.get(
        f"/api/v1/reports/{rpt_id}/download",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert fail_dl.status_code == status.HTTP_403_FORBIDDEN
