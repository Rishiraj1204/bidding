import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from backend.app.models.base import Base
from backend.app.models.user import User, Role, Permission, UserRoleEnum
from backend.app.models.tender import (
    Tender,
    TenderDocument,
    TenderRequirement,
    TenderStatusEnum,
    DocumentStatusEnum,
    RequirementCategoryEnum,
)
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.document_extraction import DocumentExtraction, ExtractedEntity, Evidence
from backend.app.models.compliance import (
    ComplianceRule,
    ComplianceResult,
    VerificationRecord,
    ComplianceStatusEnum,
    VerificationStatusEnum,
)
from backend.app.models.review import ReviewTask, ReviewDecision, ReviewStatusEnum
from backend.app.models.report import Report
from backend.app.models.notification import Notification
from backend.app.models.audit import AuditLog


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for unit testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_user_and_roles(db_session):
    """Test User, Role, and Permission creation and associations."""
    perm1 = Permission(id=str(uuid.uuid4()), name="tenders.read", description="View tenders")
    perm2 = Permission(id=str(uuid.uuid4()), name="tenders.write", description="Create/Edit tenders")
    db_session.add_all([perm1, perm2])
    db_session.commit()

    role = Role(id=str(uuid.uuid4()), name=UserRoleEnum.PROCUREMENT_OFFICER.value, description="Procurement Officer")
    role.permissions.extend([perm1, perm2])
    db_session.add(role)
    db_session.commit()

    user = User(
        id=str(uuid.uuid4()),
        email="officer@gem.gov.in",
        hashed_password="hashed_secure_password_string",
        full_name="Rajesh Kumar",
        organization_name="Ministry of Commerce",
    )
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert len(user.id) == 36
    assert user.created_at is not None
    assert len(user.roles) == 1
    assert user.roles[0].name == "PROCUREMENT_OFFICER"
    assert len(user.roles[0].permissions) == 2


def test_user_unique_email_constraint(db_session):
    """Test unique constraint on user email."""
    user1 = User(
        id=str(uuid.uuid4()),
        email="duplicate@example.com",
        hashed_password="pass1",
        full_name="User 1",
    )
    db_session.add(user1)
    db_session.commit()

    user2 = User(
        id=str(uuid.uuid4()),
        email="duplicate@example.com",
        hashed_password="pass2",
        full_name="User 2",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tender_and_requirements(db_session):
    """Test Tender, TenderDocument, and TenderRequirement creation."""
    officer = User(
        id=str(uuid.uuid4()),
        email="officer_tender@gem.gov.in",
        hashed_password="hash",
        full_name="Officer Sharma",
    )
    db_session.add(officer)
    db_session.commit()

    deadline = datetime.now(timezone.utc) + timedelta(days=30)
    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number="GEM/2026/B/1001",
        title="Procurement of IT Infrastructure Hardware",
        description="Supply, installation and maintenance of high-performance compute nodes",
        organization="GeM SPV",
        category="Hardware",
        submission_deadline=deadline,
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db_session.add(tender)
    db_session.commit()

    doc = TenderDocument(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        filename="tender_spec_2026.pdf",
        file_path="/storage/tenders/tender_spec_2026.pdf",
        file_size=1048576,
        mime_type="application/pdf",
        file_hash="a" * 64,
        status=DocumentStatusEnum.PROCESSED,
    )
    db_session.add(doc)
    db_session.commit()

    req = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.FINANCIAL,
        requirement_text="Bidder must have minimum annual turnover of 50 Lakh in last 3 FY",
        parameter="annual_turnover",
        operator=">=",
        threshold_value="5000000",
        unit="INR",
        mandatory=True,
        source_document_id=doc.id,
        source_page=4,
        extraction_confidence=0.98,
    )
    db_session.add(req)
    db_session.commit()

    assert tender.id is not None
    assert len(tender.documents) == 1
    assert len(tender.requirements) == 1
    assert tender.requirements[0].threshold_value == "5000000"


def test_bid_document_extraction_evidence_pipeline(db_session):
    """Test Bid, BidDocument, Extraction, ExtractedEntity, and Evidence creation."""
    officer = User(id=str(uuid.uuid4()), email="off1@gem.in", hashed_password="pw", full_name="Officer 1")
    bidder = User(id=str(uuid.uuid4()), email="bidder1@techcorp.in", hashed_password="pw", full_name="TechCorp India")
    db_session.add_all([officer, bidder])
    db_session.commit()

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number="GEM/2026/B/2001",
        title="Cloud Software Services",
        organization="NIC",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=15),
        status=TenderStatusEnum.PUBLISHED,
        created_by_id=officer.id,
    )
    db_session.add(tender)
    db_session.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=bidder.id,
        bid_number="BID-2026-0001",
        status=BidStatusEnum.SUBMITTED,
        submission_date=datetime.now(timezone.utc),
    )
    db_session.add(bid)
    db_session.commit()

    bid_doc = BidDocument(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        document_type=DocumentTypeEnum.FINANCIAL,
        filename="Audited_Balance_Sheet.pdf",
        file_path="/storage/bids/Audited_Balance_Sheet.pdf",
        file_size=2048000,
        mime_type="application/pdf",
        file_hash="b" * 64,
        status=DocumentStatusEnum.PROCESSED,
    )
    db_session.add(bid_doc)
    db_session.commit()

    extraction = DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=bid_doc.id,
        raw_text="Total Annual Turnover for FY 2024-25 is Rs 72,00,000",
        total_pages=5,
        ocr_confidence=0.96,
        extracted_data={"turnover": 7200000, "currency": "INR"},
        status="COMPLETED",
    )
    db_session.add(extraction)
    db_session.commit()

    entity = ExtractedEntity(
        id=str(uuid.uuid4()),
        extraction_id=extraction.id,
        entity_type="financial_amount",
        raw_value="Rs 72,00,000",
        normalized_value="7200000",
        page_number=3,
        confidence=0.96,
        source_snippet="Total Annual Turnover for FY 2024-25 is Rs 72,00,000",
    )
    db_session.add(entity)
    db_session.commit()

    evidence = Evidence(
        id=str(uuid.uuid4()),
        bid_document_id=bid_doc.id,
        entity_id=entity.id,
        page_number=3,
        field_name="annual_turnover",
        extracted_value="Rs 72,00,000",
        normalized_value="7200000",
        confidence=0.96,
        snippet_text="Total Annual Turnover for FY 2024-25 is Rs 72,00,000",
        source_type="DOCUMENT_OCR",
    )
    db_session.add(evidence)
    db_session.commit()

    assert evidence.id is not None
    assert evidence.bid_document.bid.bid_number == "BID-2026-0001"
    assert len(bid_doc.evidence_records) == 1


def test_compliance_verification_and_review(db_session):
    """Test ComplianceResult, VerificationRecord, ReviewTask, and ReviewDecision."""
    user = User(id=str(uuid.uuid4()), email="test_comp@gem.in", hashed_password="pw", full_name="User Test")
    reviewer = User(id=str(uuid.uuid4()), email="reviewer@gem.in", hashed_password="pw", full_name="Compliance Reviewer")
    db_session.add_all([user, reviewer])
    db_session.commit()

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number="GEM/2026/B/3001",
        title="Security Audit Services",
        organization="CERT-In",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=10),
        status=TenderStatusEnum.UNDER_EVALUATION,
        created_by_id=user.id,
    )
    db_session.add(tender)
    db_session.commit()

    req = TenderRequirement(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        category=RequirementCategoryEnum.EXPERIENCE,
        requirement_text="Minimum 5 years experience in cybersecurity audits",
        parameter="experience_years",
        operator=">=",
        threshold_value="5",
        mandatory=True,
    )
    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=user.id,
        bid_number="BID-2026-3001",
        status=BidStatusEnum.UNDER_REVIEW,
    )
    db_session.add_all([req, bid])
    db_session.commit()

    rule = ComplianceRule(
        id=str(uuid.uuid4()),
        rule_name="experience_years_gte_5",
        category="EXPERIENCE",
        rule_type="DETERMINISTIC",
        rule_definition={"field": "experience_years", "op": ">=", "val": 5},
    )
    db_session.add(rule)
    db_session.commit()

    compliance = ComplianceResult(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        requirement_id=req.id,
        rule_id=rule.id,
        status=ComplianceStatusEnum.NEEDS_REVIEW,
        reason="Experience documents indicate 4.5 to 5.2 years depending on certificate interpretation",
        confidence=0.78,
        evaluated_by="RULE_ENGINE",
    )
    db_session.add(compliance)
    db_session.commit()

    verification = VerificationRecord(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        compliance_result_id=compliance.id,
        verification_type="CERTIFICATE",
        provider_name="MOCK_CERT_VALIDATOR",
        is_mock=True,
        status=VerificationStatusEnum.VERIFIED,
        reference_id="MOCK-CERT-8899",
    )
    db_session.add(verification)
    db_session.commit()

    review_task = ReviewTask(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        compliance_result_id=compliance.id,
        assigned_to_id=reviewer.id,
        status=ReviewStatusEnum.IN_PROGRESS,
        trigger_reason="Borderline experience duration requires human inspection",
    )
    db_session.add(review_task)
    db_session.commit()

    decision = ReviewDecision(
        id=str(uuid.uuid4()),
        task_id=review_task.id,
        reviewer_id=reviewer.id,
        original_decision="NEEDS_REVIEW",
        new_decision="COMPLIANT",
        justification="Verified supporting client work orders dating back 5.5 years.",
        comments="Approved on human oversight.",
    )
    db_session.add(decision)
    db_session.commit()

    assert decision.id is not None
    assert decision.task.bid_id == bid.id
    assert len(compliance.verification_records) == 1
    assert len(compliance.review_tasks) == 1


def test_reports_notifications_audit_logs(db_session):
    """Test Report, Notification, and AuditLog records."""
    officer = User(id=str(uuid.uuid4()), email="audit_officer@gem.in", hashed_password="pw", full_name="Audit Officer")
    db_session.add(officer)
    db_session.commit()

    tender = Tender(
        id=str(uuid.uuid4()),
        tender_number="GEM/2026/B/4001",
        title="Consultancy",
        organization="NITI Aayog",
        submission_deadline=datetime.now(timezone.utc) + timedelta(days=5),
        created_by_id=officer.id,
    )
    db_session.add(tender)
    db_session.commit()

    bid = Bid(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        bidder_id=officer.id,
        bid_number="BID-2026-4001",
    )
    db_session.add(bid)
    db_session.commit()

    report = Report(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        tender_id=tender.id,
        report_number="REP-2026-0001",
        file_path="/storage/reports/REP-2026-0001.pdf",
        summary={"total_requirements": 10, "compliant": 9, "non_compliant": 1},
        generated_by_id=officer.id,
    )
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=officer.id,
        title="Compliance Report Ready",
        message="Compliance evaluation report REP-2026-0001 is now generated.",
        notification_type="SUCCESS",
        related_resource_type="report",
        related_resource_id=report.id,
    )
    audit = AuditLog(
        id=str(uuid.uuid4()),
        actor_id=officer.id,
        actor_email=officer.email,
        action="REPORT_GENERATED",
        resource_type="report",
        resource_id=report.id,
        previous_state=None,
        new_state={"status": "FINALIZED"},
        ip_address="127.0.0.1",
        user_agent="Pytest Client",
    )
    db_session.add_all([report, notification, audit])
    db_session.commit()

    assert report.id is not None
    assert notification.id is not None
    assert audit.id is not None
    assert audit.actor.email == "audit_officer@gem.in"
