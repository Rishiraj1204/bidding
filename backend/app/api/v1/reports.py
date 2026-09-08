from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.report import (
    GenerateReportRequest,
    ReportListResponse,
    ReportResponse,
)
from backend.app.services.report_service import (
    generate_bid_compliance_report,
    get_report_detail,
    get_report_file,
    list_bid_reports,
)

router = APIRouter()


@router.post(
    "/bid/{bid_id}/generate",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Bid Compliance Report",
)
def generate_report_endpoint(
    bid_id: str,
    request: Request,
    payload: Optional[GenerateReportRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate a formal PDF compliance and evaluation report for a Tender + Bid.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return generate_bid_compliance_report(
        db=db,
        bid_id=bid_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/bid/{bid_id}",
    response_model=ReportListResponse,
    summary="List Reports for Bid",
)
def list_reports_endpoint(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List all generated reports for a bid.
    """
    return list_bid_reports(
        db=db,
        bid_id=bid_id,
        user=current_user,
    )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get Report Metadata",
)
def get_report_endpoint(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve metadata for a specific report.
    """
    return get_report_detail(
        db=db,
        report_id=report_id,
        user=current_user,
    )


@router.get(
    "/{report_id}/download",
    summary="Download Report PDF",
)
def download_report_endpoint(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Download the generated PDF report file.
    """
    file_path, filename = get_report_file(db=db, report_id=report_id, user=current_user)
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )
