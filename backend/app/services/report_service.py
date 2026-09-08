import io
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import settings
from backend.app.core.deps import get_user_roles
from backend.app.models.bid import Bid, BidDocument
from backend.app.models.compliance import (
    ComplianceResult,
    ComplianceStatusEnum,
    VerificationRecord,
)
from backend.app.models.document_extraction import Evidence
from backend.app.models.report import Report
from backend.app.models.review import ReviewDecision, ReviewTask
from backend.app.models.tender import Tender, TenderRequirement
from backend.app.models.user import User
from backend.app.schemas.report import ReportListResponse, ReportResponse
from backend.app.services.audit_service import log_audit_event

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)


def _check_report_access(report_or_bid: Any, user: User) -> None:
    """Validate user has permission to access this report."""
    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )
    bidder_id = getattr(report_or_bid, "bidder_id", None)
    if not bidder_id and hasattr(report_or_bid, "bid") and report_or_bid.bid:
        bidder_id = report_or_bid.bid.bidder_id

    if not is_staff and bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to access reports for this bid.",
        )


def _report_to_response(rep: Report) -> ReportResponse:
    gen_by_name = rep.generated_by.full_name if rep.generated_by else None
    return ReportResponse(
        id=rep.id,
        bid_id=rep.bid_id,
        tender_id=rep.tender_id,
        report_number=rep.report_number,
        file_path=rep.file_path,
        summary=rep.summary,
        generated_by_id=rep.generated_by_id,
        generated_by_name=gen_by_name,
        created_at=rep.created_at,
    )


def _generate_pdf_file(
    output_path: str,
    report_number: str,
    tender: Tender,
    bid: Bid,
    results: List[ComplianceResult],
    review_decisions: List[ReviewDecision],
    generator_user: User,
) -> None:
    """Build a professional procurement compliance evaluation PDF report using ReportLab."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf_doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    bold_small = ParagraphStyle(
        "BoldSmall",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
    )

    # Header Banner
    story.append(Paragraph("BID COMPLIANCE & EVALUATION REPORT", title_style))
    story.append(
        Paragraph(
            f"Report Reference: <b>{report_number}</b> • Generated: {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M UTC')}",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=12))

    # Tender & Bid Details Table
    tender_data = [
        [
            Paragraph("<b>Tender Title:</b>", body_style),
            Paragraph(tender.title or "N/A", body_style),
            Paragraph("<b>Bid Reference:</b>", body_style),
            Paragraph(bid.bid_number or bid.id[:8], body_style),
        ],
        [
            Paragraph("<b>Tender Number:</b>", body_style),
            Paragraph(tender.tender_number or "N/A", body_style),
            Paragraph("<b>Bidder Name:</b>", body_style),
            Paragraph(bid.bidder.full_name or bid.bidder.organization_name or "Bidder", body_style),
        ],
        [
            Paragraph("<b>Procurement Entity:</b>", body_style),
            Paragraph(tender.organization or "N/A", body_style),
            Paragraph("<b>Evaluator:</b>", body_style),
            Paragraph(generator_user.full_name or generator_user.email, body_style),
        ],
    ]
    t_table = Table(tender_data, colWidths=[90, 180, 90, 180])
    t_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_table)
    story.append(Spacer(1, 12))

    # Overall Summary
    total = len(results)
    compliant_count = sum(1 for r in results if r.status == ComplianceStatusEnum.COMPLIANT)
    non_compliant_count = sum(1 for r in results if r.status == ComplianceStatusEnum.NON_COMPLIANT)
    needs_review_count = sum(1 for r in results if r.status == ComplianceStatusEnum.NEEDS_REVIEW)
    mandatory_results = [r for r in results if r.requirement and r.requirement.mandatory]
    mandatory_passed = all(r.status == ComplianceStatusEnum.COMPLIANT for r in mandatory_results) if mandatory_results else False

    verdict_text = "COMPLIANT" if (mandatory_passed and non_compliant_count == 0) else ("NON_COMPLIANT" if non_compliant_count > 0 else "NEEDS_REVIEW")
    verdict_color = colors.HexColor("#10b981") if verdict_text == "COMPLIANT" else (colors.HexColor("#ef4444") if verdict_text == "NON_COMPLIANT" else colors.HexColor("#f59e0b"))

    summary_data = [
        [
            Paragraph(f"<b>Overall Compliance Verdict: <font color='{verdict_color.hexval()}'>{verdict_text}</font></b>", section_heading),
            Paragraph(f"<b>Total Criteria:</b> {total} | <b>Compliant:</b> {compliant_count} | <b>Non-Compliant:</b> {non_compliant_count} | <b>Reviews:</b> {needs_review_count}", body_style),
        ]
    ]
    sum_table = Table(summary_data, colWidths=[240, 300])
    sum_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(sum_table)
    story.append(Spacer(1, 14))

    # Requirement Breakdown Table
    story.append(Paragraph("Tender Specification & Evidence Evaluation Breakdown", section_heading))
    
    table_rows = [
        [
            Paragraph("<b>Category / Requirement</b>", bold_small),
            Paragraph("<b>Mandatory</b>", bold_small),
            Paragraph("<b>Extracted Evidence & Source</b>", bold_small),
            Paragraph("<b>Status</b>", bold_small),
            Paragraph("<b>Evaluation Reason</b>", bold_small),
        ]
    ]

    for r in results:
        req = r.requirement
        ev = r.evidence
        doc = ev.bid_document if ev else None
        
        req_text = req.requirement_text if req else "Requirement"
        cat_text = req.category.value if req and hasattr(req.category, "value") else "OTHER"
        is_mand = "YES" if (req and req.mandatory) else "NO"
        
        ev_str = f"{ev.extracted_value or 'N/A'}" if ev else "No evidence provided"
        if doc:
            ev_str += f"<br/><font color='#64748b'>Doc: {doc.filename[:20]} (p.{ev.page_number or 1})</font>"

        status_str = r.status.value if hasattr(r.status, "value") else str(r.status)
        reason_str = r.reason or ""

        table_rows.append(
            [
                Paragraph(f"<b>[{cat_text}]</b><br/>{req_text}", body_style),
                Paragraph(is_mand, body_style),
                Paragraph(ev_str, body_style),
                Paragraph(f"<b>{status_str}</b>", body_style),
                Paragraph(reason_str, body_style),
            ]
        )

    req_table = Table(table_rows, colWidths=[150, 45, 120, 75, 150])
    req_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(req_table)
    story.append(Spacer(1, 14))

    # Human Review Decisions (if any)
    if review_decisions:
        story.append(Paragraph("Human Review Decisions & Overrides", section_heading))
        rev_rows = [
            [
                Paragraph("<b>Reviewer</b>", bold_small),
                Paragraph("<b>Original Decision</b>", bold_small),
                Paragraph("<b>Final Decision</b>", bold_small),
                Paragraph("<b>Justification</b>", bold_small),
                Paragraph("<b>Timestamp</b>", bold_small),
            ]
        ]
        for rd in review_decisions:
            rev_name = rd.reviewer.full_name if rd.reviewer else "Staff Reviewer"
            rev_rows.append(
                [
                    Paragraph(rev_name, body_style),
                    Paragraph(rd.original_decision, body_style),
                    Paragraph(f"<b>{rd.new_decision}</b>", body_style),
                    Paragraph(rd.justification, body_style),
                    Paragraph(rd.created_at.strftime("%d-%b-%Y %H:%M"), body_style),
                ]
            )
        rev_table = Table(rev_rows, colWidths=[110, 80, 80, 180, 90])
        rev_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(rev_table)
        story.append(Spacer(1, 14))

    # Confidentiality & Audit Footer
    footer_text = Paragraph(
        "<b>OFFICIAL PROCUREMENT RECORD</b>: Generated by BIDVERIFY Platform. "
        "Contains grounded evidence citations and deterministic compliance evaluations. "
        "External registry checks are marked (Mock Gateway) in test environments.",
        subtitle_style,
    )
    story.append(KeepTogether([HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")), Spacer(1, 4), footer_text]))

    pdf_doc.build(story)



def generate_bid_compliance_report(
    db: Session,
    bid_id: str,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> ReportResponse:
    """Generate a formal compliance verification report PDF and JSON payload."""
    bid = (
        db.query(Bid)
        .options(
            selectinload(Bid.tender).selectinload(Tender.requirements),
            selectinload(Bid.bidder),
            selectinload(Bid.compliance_results).selectinload(ComplianceResult.requirement),
            selectinload(Bid.compliance_results).selectinload(ComplianceResult.evidence).selectinload(Evidence.bid_document),
            selectinload(Bid.review_tasks).selectinload(ReviewTask.decisions).selectinload(ReviewDecision.reviewer),
        )
        .filter(Bid.id == bid_id)
        .first()
    )
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_report_access(bid, user)

    report_id = str(uuid.uuid4())
    report_num = f"RPT-BID-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    # Collect all review decisions across tasks
    all_decisions: List[ReviewDecision] = []
    for t in (bid.review_tasks or []):
        for d in (t.decisions or []):
            all_decisions.append(d)

    # Build file storage path
    storage_dir = os.path.join(settings.STORAGE_LOCAL_DIR, "reports")
    os.makedirs(storage_dir, exist_ok=True)
    pdf_filename = f"{report_id}.pdf"
    pdf_abs_path = os.path.join(storage_dir, pdf_filename)

    # Generate PDF
    _generate_pdf_file(
        output_path=pdf_abs_path,
        report_number=report_num,
        tender=bid.tender,
        bid=bid,
        results=bid.compliance_results or [],
        review_decisions=all_decisions,
        generator_user=user,
    )

    # Summary payload
    total_reqs = len(bid.compliance_results or [])
    compliant_c = sum(1 for r in (bid.compliance_results or []) if r.status == ComplianceStatusEnum.COMPLIANT)
    non_compliant_c = sum(1 for r in (bid.compliance_results or []) if r.status == ComplianceStatusEnum.NON_COMPLIANT)
    needs_review_c = sum(1 for r in (bid.compliance_results or []) if r.status == ComplianceStatusEnum.NEEDS_REVIEW)

    summary_payload = {
        "tender_number": bid.tender.tender_number if bid.tender else None,
        "tender_title": bid.tender.title if bid.tender else None,
        "bid_number": bid.bid_number,
        "bidder_name": bid.bidder.full_name or bid.bidder.organization_name if bid.bidder else None,
        "total_requirements": total_reqs,
        "compliant_count": compliant_c,
        "non_compliant_count": non_compliant_c,
        "needs_review_count": needs_review_c,
        "overall_verdict": "COMPLIANT" if (non_compliant_c == 0 and needs_review_c == 0 and total_reqs > 0) else ("NON_COMPLIANT" if non_compliant_c > 0 else "NEEDS_REVIEW"),
        "review_decisions_count": len(all_decisions),
    }

    report_record = Report(
        id=report_id,
        bid_id=bid.id,
        tender_id=bid.tender_id,
        report_number=report_num,
        file_path=pdf_abs_path,
        summary=summary_payload,
        generated_by_id=user.id,
    )
    db.add(report_record)
    db.commit()
    db.refresh(report_record)

    log_audit_event(
        db=db,
        action="REPORT_GENERATED",
        resource_type="report",
        resource_id=report_record.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "report_id": report_record.id,
            "report_number": report_num,
            "bid_id": bid.id,
            "file_path": pdf_abs_path,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    from backend.app.services.notification_service import create_notification
    create_notification(
        db=db,
        user_id=bid.bidder_id,
        title="Compliance Report Generated",
        message=f"Official compliance report {report_num} has been generated for your bid.",
        notification_type="SUCCESS",
        related_resource_type="report",
        related_resource_id=report_record.id,
    )

    return _report_to_response(report_record)


def list_bid_reports(
    db: Session,
    bid_id: str,
    user: User,
) -> ReportListResponse:
    """List all reports generated for a specific bid."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_report_access(bid, user)

    reports = (
        db.query(Report)
        .options(selectinload(Report.generated_by))
        .filter(Report.bid_id == bid.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    items = [_report_to_response(r) for r in reports]

    return ReportListResponse(
        items=items,
        total=len(items),
    )


def get_report_detail(
    db: Session,
    report_id: str,
    user: User,
) -> ReportResponse:
    """Retrieve metadata of a single report."""
    rep = (
        db.query(Report)
        .options(selectinload(Report.generated_by), selectinload(Report.bid))
        .filter(Report.id == report_id)
        .first()
    )
    if not rep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    _check_report_access(rep, user)
    return _report_to_response(rep)


def get_report_file(
    db: Session,
    report_id: str,
    user: User,
) -> Tuple[str, str]:
    """Retrieve the physical PDF file path and download filename for a report."""
    rep = (
        db.query(Report)
        .options(selectinload(Report.bid))
        .filter(Report.id == report_id)
        .first()
    )
    if not rep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    _check_report_access(rep, user)

    if not rep.file_path or not os.path.exists(rep.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found on disk")

    filename = f"{rep.report_number}.pdf"
    return rep.file_path, filename
