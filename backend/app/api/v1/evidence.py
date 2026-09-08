from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.extraction import BidEvidenceListResponse, EvidenceResponse
from backend.app.services.extraction_service import (
    get_bid_evidence_list,
    get_evidence_detail,
)

router = APIRouter()


@router.get(
    "/bid/{bid_id}",
    response_model=BidEvidenceListResponse,
    summary="List Evidence Records for Bid",
)
def list_bid_evidence(
    bid_id: str,
    field_name: Optional[str] = Query(None, description="Filter by extracted field (e.g. gstin, pan_number, annual_turnover)"),
    document_id: Optional[str] = Query(None, description="Filter by source document ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve all grounded evidence records linking extracted fields to document citations.
    """
    return get_bid_evidence_list(
        db=db,
        bid_id=bid_id,
        user=current_user,
        field_name=field_name,
        document_id=document_id,
    )


@router.get(
    "/bid/{bid_id}/document/{document_id}",
    response_model=BidEvidenceListResponse,
    summary="List Evidence Records for Document",
)
def list_document_evidence(
    bid_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve evidence records grounded in a specific supporting document.
    """
    return get_bid_evidence_list(
        db=db,
        bid_id=bid_id,
        user=current_user,
        document_id=document_id,
    )


@router.get(
    "/{evidence_id}",
    response_model=EvidenceResponse,
    summary="Get Evidence Item Detail",
)
def get_evidence_item(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Fetch a single evidence record with full traceability citations.
    """
    return get_evidence_detail(
        db=db,
        evidence_id=evidence_id,
        user=current_user,
    )
