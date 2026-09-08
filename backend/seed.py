"""
BIDVERIFY AI — SIH 2026 Seed / Demo Data Generator
Creates realistic procurement tenders, bids, documents, OCR extracts, compliance results,
mock registry verifications, review tasks, reports, notifications, and audit trails for all 5 roles.
"""

import io
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app.core.database import SessionLocal, engine
from backend.app.core.security import get_password_hash
from backend.app.models.audit import AuditLog
from backend.app.models.base import Base
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.compliance import (
    ComplianceResult,
    ComplianceStatusEnum,
    VerificationRecord,
    VerificationStatusEnum,
)
from backend.app.models.document_extraction import DocumentExtraction, ExtractedEntity, Evidence
from backend.app.models.notification import Notification
from backend.app.models.report import Report
from backend.app.models.review import ReviewDecision, ReviewStatusEnum, ReviewTask
from backend.app.models.tender import (
    DocumentStatusEnum,
    RequirementCategoryEnum,
    Tender,
    TenderDocument,
    TenderRequirement,
    TenderStatusEnum,
)
from backend.app.models.user import Permission, Role, User, UserRoleEnum
from backend.app.services.audit_service import log_audit_event
from backend.app.services.user_service import init_rbac_system


def seed_database(custom_db=None, custom_engine=None):
    print("==================================================================")
    print("  BIDVERIFY AI — SIH 2026 DEMO DATA SEEDING")
    print("==================================================================")

    # 1. Create tables if needed
    active_engine = custom_engine or engine
    Base.metadata.create_all(bind=active_engine)
    db = custom_db if custom_db is not None else SessionLocal()
    should_close = custom_db is None

    try:
        # 2. Initialize RBAC Roles & Permissions
        print("[1/7] Initializing RBAC Roles & Permissions...")
        init_rbac_system(db)

        # 3. Seed Demo Users for all 5 roles
        print("[2/7] Seeding Demo User Accounts for All 5 Roles...")
        roles_by_name = {r.name: r for r in db.query(Role).all()}

        demo_users_spec = [
            {
                "email": "admin@gem.gov.in",
                "name": "Smt. Rajeshwari Iyer",
                "org": "Government e-Marketplace (GeM) HQ",
                "role": UserRoleEnum.ADMIN.value,
                "is_superuser": True,
            },
            {
                "email": "officer@gem.gov.in",
                "name": "Dr. Vikramaditya Sharma",
                "org": "Ministry of Road Transport & Highways",
                "role": UserRoleEnum.PROCUREMENT_OFFICER.value,
                "is_superuser": False,
            },
            {
                "email": "bidder@vendor.in",
                "name": "Ananya Deshmukh",
                "org": "Apex Cybernetics India Pvt Ltd",
                "role": UserRoleEnum.BIDDER.value,
                "is_superuser": False,
            },
            {
                "email": "reviewer@gem.gov.in",
                "name": "Col. Sanjeev Nair (Retd.)",
                "org": "GeM Technical Evaluation Committee",
                "role": UserRoleEnum.REVIEWER.value,
                "is_superuser": False,
            },
            {
                "email": "auditor@gem.gov.in",
                "name": "CMA Prateek Chatterjee",
                "org": "Comptroller and Auditor General (CAG) Audit Cell",
                "role": UserRoleEnum.AUDITOR.value,
                "is_superuser": False,
            },
        ]

        users = {}
        for spec in demo_users_spec:
            existing = db.query(User).filter(User.email == spec["email"]).first()
            if not existing:
                u = User(
                    id=str(uuid.uuid4()),
                    email=spec["email"],
                    hashed_password=get_password_hash("DemoPass123!"),
                    full_name=spec["name"],
                    organization_name=spec["org"],
                    is_active=True,
                    is_superuser=spec["is_superuser"],
                )
                db.add(u)
                db.commit()
                if spec["role"] in roles_by_name:
                    u.roles.append(roles_by_name[spec["role"]])
                db.commit()
                users[spec["email"]] = u
                print(f"  + Created User: {spec['email']} [{spec['role']}]")
            else:
                users[spec["email"]] = existing
                print(f"  * User exists: {spec['email']}")

        officer = users["officer@gem.gov.in"]
        bidder = users["bidder@vendor.in"]
        reviewer = users["reviewer@gem.gov.in"]

        # 4. Seed Realistic Tenders with Requirements
        print("[3/7] Seeding Procurement Tenders & Requirements...")
        t1 = db.query(Tender).filter(Tender.tender_number == "GEM/2026/B/90821").first()
        if not t1:
            t1 = Tender(
                id=str(uuid.uuid4()),
                tender_number="GEM/2026/B/90821",
                title="Turnkey Deployment of AI-Powered Traffic Telematics & ANPR Cameras",
                description="Supply, installation, calibration, and 5-year SLA maintenance of high-resolution automated number-plate recognition cameras and speed sensor nodes across National Highway 48.",
                organization="Ministry of Road Transport & Highways",
                category="GOODS",
                submission_deadline=datetime.now(timezone.utc) + timedelta(days=25),
                status=TenderStatusEnum.PUBLISHED,
                created_by_id=officer.id,
            )
            db.add(t1)
            db.commit()

            # Add requirements
            r1 = TenderRequirement(
                id=str(uuid.uuid4()),
                tender_id=t1.id,
                category=RequirementCategoryEnum.ELIGIBILITY,
                requirement_text="Bidder must possess active and valid Indian GSTIN registration.",
                parameter="gstin",
                operator="==",
                threshold_value="27AAACA1234B1ZV",
                mandatory=True,
            )
            r2 = TenderRequirement(
                id=str(uuid.uuid4()),
                tender_id=t1.id,
                category=RequirementCategoryEnum.FINANCIAL,
                requirement_text="Minimum average annual turnover for last 3 financial years must exceed INR 50,000,000.",
                parameter="annual_turnover",
                operator=">=",
                threshold_value="50000000",
                unit="INR",
                mandatory=True,
            )
            r3 = TenderRequirement(
                id=str(uuid.uuid4()),
                tender_id=t1.id,
                category=RequirementCategoryEnum.EXPERIENCE,
                requirement_text="Bidder must possess valid ISO/IEC 27001 Information Security certification.",
                parameter="iso_27001",
                operator="exists",
                mandatory=False,
            )
            db.add_all([r1, r2, r3])
            db.commit()
            print(f"  + Created Tender: {t1.tender_number} (with 3 requirements)")

        # 5. Seed Bid Submission with Supporting Documents
        print("[4/7] Seeding Bid Submission & Uploaded Documents...")
        bid = db.query(Bid).filter(Bid.bid_number == "BID/2026/GEM/001").first()
        if not bid:
            bid = Bid(
                id=str(uuid.uuid4()),
                tender_id=t1.id,
                bidder_id=bidder.id,
                bid_number="BID/2026/GEM/001",
                status=BidStatusEnum.SUBMITTED,
                submission_date=datetime.now(timezone.utc) - timedelta(hours=3),
                notes="Bidder complies with all NHAI telematics specifications and provides 5-year SLA.",
            )
            db.add(bid)
            db.commit()

            # Add Bid Document 1: GST Certificate
            doc1 = BidDocument(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                document_type=DocumentTypeEnum.GST_CERTIFICATE,
                filename="apex_cybernetics_gst_certificate.pdf",
                file_path="bids/apex_cybernetics_gst_certificate.pdf",
                file_size=245800,
                mime_type="application/pdf",
                file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                status=DocumentStatusEnum.PROCESSED,
            )
            # Add Bid Document 2: Audited Financials
            doc2 = BidDocument(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                document_type=DocumentTypeEnum.FINANCIAL,
                filename="apex_audited_financial_statements_2025.pdf",
                file_path="bids/apex_audited_financial_statements_2025.pdf",
                file_size=589120,
                mime_type="application/pdf",
                file_hash="cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce",
                status=DocumentStatusEnum.PROCESSED,
            )
            db.add_all([doc1, doc2])
            db.commit()
            print(f"  + Created Bid: {bid.bid_number} with 2 documents")

            # 6. OCR Extraction & Grounded Evidence
            print("[5/7] Seeding OCR Extractions, Entities & Evidence Traceability...")
            ext1 = DocumentExtraction(
                id=str(uuid.uuid4()),
                document_id=doc1.id,
                raw_text="GOVERNMENT OF INDIA - GST CERTIFICATE\nLegal Name: Apex Cybernetics India Pvt Ltd\nGSTIN: 27AAACA1234B1ZV\nPAN: AAACA1234B\nStatus: Active Regular Taxpayer",
                total_pages=1,
                ocr_confidence=0.98,
                status="COMPLETED",
            )
            ext2 = DocumentExtraction(
                id=str(uuid.uuid4()),
                document_id=doc2.id,
                raw_text="INDEPENDENT AUDITOR'S REPORT FY 2024-25\nApex Cybernetics India Pvt Ltd\nAnnual Revenue from Operations: INR 72,500,000.00\nNet Profit: INR 14,200,000.00",
                total_pages=2,
                ocr_confidence=0.96,
                status="COMPLETED",
            )
            db.add_all([ext1, ext2])
            db.commit()

            entity1 = ExtractedEntity(
                id=str(uuid.uuid4()),
                extraction_id=ext1.id,
                entity_type="GSTIN",
                raw_value="27AAACA1234B1ZV",
                normalized_value="27AAACA1234B1ZV",
                page_number=1,
                confidence=0.99,
                source_snippet="GSTIN: 27AAACA1234B1ZV",
            )
            entity2 = ExtractedEntity(
                id=str(uuid.uuid4()),
                extraction_id=ext2.id,
                entity_type="FINANCIAL_TURNOVER",
                raw_value="INR 72,500,000.00",
                normalized_value="72500000.0",
                page_number=1,
                confidence=0.97,
                source_snippet="Annual Revenue from Operations: INR 72,500,000.00",
            )
            db.add_all([entity1, entity2])
            db.commit()

            ev1 = Evidence(
                id=str(uuid.uuid4()),
                bid_document_id=doc1.id,
                entity_id=entity1.id,
                page_number=1,
                field_name="gstin",
                extracted_value="27AAACA1234B1ZV",
                normalized_value="27AAACA1234B1ZV",
                confidence=0.99,
                snippet_text="GSTIN: 27AAACA1234B1ZV — Legal Name: Apex Cybernetics India Pvt Ltd",
                source_type="DOCUMENT_OCR",
            )
            ev2 = Evidence(
                id=str(uuid.uuid4()),
                bid_document_id=doc2.id,
                entity_id=entity2.id,
                page_number=1,
                field_name="annual_turnover",
                extracted_value="72500000.0",
                normalized_value="72500000.0",
                confidence=0.97,
                snippet_text="Annual Revenue from Operations: INR 72,500,000.00",
                source_type="DOCUMENT_OCR",
            )
            db.add_all([ev1, ev2])
            db.commit()

            # 7. Seed Compliance Verdicts & Mock Verification Badges
            print("[6/7] Seeding Compliance Verdicts, Mock Government Verifications & Human Review...")
            v1 = VerificationRecord(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                verification_type="GST",
                provider_name="GSTN_PORTAL_MOCK",
                reference_id="27AAACA1234B1ZV",
                status=VerificationStatusEnum.VERIFIED,
                is_mock=True,
                response_payload={
                    "status": "Active",
                    "trade_name": "Apex Cybernetics India Pvt Ltd",
                    "registration_date": "2018-04-10",
                    "is_simulated": True,
                },
            )
            db.add(v1)
            db.commit()

            req_list = db.query(TenderRequirement).filter(TenderRequirement.tender_id == t1.id).all()
            cr1 = ComplianceResult(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                requirement_id=req_list[0].id,
                evidence_id=ev1.id,
                status=ComplianceStatusEnum.COMPLIANT,
                reason="Extracted GSTIN exactly matches criteria and verified active on GSTN portal (Mock).",
                confidence=0.99,
                evaluated_by="RULE_ENGINE",
            )
            cr2 = ComplianceResult(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                requirement_id=req_list[1].id,
                evidence_id=ev2.id,
                status=ComplianceStatusEnum.COMPLIANT,
                reason="Audited turnover of INR 72,500,000 exceeds mandatory threshold of INR 50,000,000.",
                confidence=0.97,
                evaluated_by="RULE_ENGINE",
            )
            db.add_all([cr1, cr2])
            db.commit()

            # Review Task & Decision Override
            rt = ReviewTask(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                compliance_result_id=cr1.id,
                assigned_to_id=reviewer.id,
                trigger_reason="Compliance evaluator flagged requirement for technical committee verification.",
                status=ReviewStatusEnum.APPROVED,
            )
            db.add(rt)
            db.commit()

            rd = ReviewDecision(
                id=str(uuid.uuid4()),
                task_id=rt.id,
                reviewer_id=reviewer.id,
                original_decision="NEEDS_REVIEW",
                new_decision="COMPLIANT",
                justification="Independently confirmed incorporation certificate and active taxpayer filing status.",
                comments="Technical committee recommends approval.",
            )
            db.add(rd)
            db.commit()

            # Compliance Report
            rep = Report(
                id=str(uuid.uuid4()),
                bid_id=bid.id,
                tender_id=t1.id,
                report_number=f"REP-2026-{uuid.uuid4().hex[:6].upper()}",
                file_path=f"reports/bid_evaluation_{bid.id}.pdf",
                summary={
                    "verdict": "COMPLIANT",
                    "total_requirements": 3,
                    "compliant_count": 2,
                    "non_compliant_count": 0,
                    "needs_review_count": 0,
                },
                generated_by_id=officer.id,
            )
            db.add(rep)
            db.commit()

            # Notifications
            n1 = Notification(
                id=str(uuid.uuid4()),
                user_id=bidder.id,
                title="Compliance Verification Completed",
                message=f"Your bid {bid.bid_number} for tender {t1.tender_number} has been verified COMPLIANT.",
                notification_type="SUCCESS",
                is_read=False,
                related_resource_type="bid",
                related_resource_id=bid.id,
            )
            n2 = Notification(
                id=str(uuid.uuid4()),
                user_id=officer.id,
                title="Bid Submitted",
                message=f"Vendor {bidder.organization_name} submitted bid {bid.bid_number}.",
                notification_type="INFO",
                is_read=True,
                related_resource_type="bid",
                related_resource_id=bid.id,
            )
            db.add_all([n1, n2])
            db.commit()

            # Audit Logs
            log_audit_event(
                db=db,
                action="DEMO_SYSTEM_INITIALIZATION",
                resource_type="platform",
                actor_id=officer.id,
                actor_email=officer.email,
                new_state={"version": "1.0.0", "sih_demo_dataset": "LOADED"},
            )

        print("[7/7] Demo Data Seeding Complete!")
        print("==================================================================")
        print("  DEMO USER CREDENTIALS (Password for all: DemoPass123!)")
        print("  1. ADMIN:                admin@gem.gov.in")
        print("  2. PROCUREMENT OFFICER:  officer@gem.gov.in")
        print("  3. BIDDER:               bidder@vendor.in")
        print("  4. REVIEWER:             reviewer@gem.gov.in")
        print("  5. AUDITOR:              auditor@gem.gov.in")
        print("==================================================================")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        raise e
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    seed_database()
