from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.extraction import (
    BidExtractionSummaryResponse,
    DocumentExtractionDetailResponse,
)
from backend.app.services.extraction_service import (
    extract_bid_all_documents,
    extract_document_entities,
    get_bid_extraction_summary,
    get_document_extraction_details,
)

router = APIRouter()


@router.post(
    "/bid/{bid_id}/document/{document_id}",
    response_model=DocumentExtractionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Run AI Entity Extraction on Document",
)
def extract_single_document(
    bid_id: str,
    document_id: str,
    request: Request,
    force_reextract: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Extract structured entities (GSTIN, PAN, turnover, experience, etc.)
    from a supporting bid document with grounded evidence tracing.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return extract_document_entities(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
        force_reextract=force_reextract,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/bid/{bid_id}",
    response_model=BidExtractionSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Run AI Extraction on All Bid Documents",
)
def extract_all_bid_docs(
    bid_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Run entity extraction across all uploaded supporting documents of a bid.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return extract_bid_all_documents(
        db=db,
        bid_id=bid_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/bid/{bid_id}/document/{document_id}",
    response_model=DocumentExtractionDetailResponse,
    summary="Get Document Extraction & Entities",
)
def get_doc_extraction(
    bid_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve extracted entities and evidence citations for a specific document.
    """
    return get_document_extraction_details(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
    )


@router.get(
    "/bid/{bid_id}/entities",
    response_model=BidExtractionSummaryResponse,
    summary="Get All Extracted Entities for Bid",
)
def get_all_bid_entities(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve all aggregated extracted entities and evidence records for a bid submission.
    """
    return get_bid_extraction_summary(
        db=db,
        bid_id=bid_id,
        user=current_user,
    )
