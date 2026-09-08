from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user, require_roles
from backend.app.models.bid import DocumentTypeEnum
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.document import (
    BidDocumentListResponse,
    BidDocumentResponse,
    OCRExtractionResponse,
    TenderDocumentListResponse,
    TenderDocumentResponse,
)
from backend.app.services.document_service import (
    delete_bid_document,
    delete_tender_document,
    download_bid_document,
    download_tender_document,
    get_bid_document_by_id,
    get_bid_document_ocr,
    get_bid_documents,
    get_tender_document_by_id,
    get_tender_documents,
    process_bid_document_ocr,
    upload_bid_document,
    upload_tender_document,
)

router = APIRouter()


# =========================================================================
# TENDER DOCUMENT ENDPOINTS
# =========================================================================

@router.post(
    "/tender/{tender_id}",
    response_model=TenderDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Tender Document Attachment",
)
def upload_tender_doc(
    tender_id: str,
    request: Request,
    file: UploadFile = File(..., description="Tender specification or RFP file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRoleEnum.PROCUREMENT_OFFICER.value,
        UserRoleEnum.ADMIN.value,
    )),
):
    """
    Upload a tender specification or RFP document.
    Restricted to Procurement Officers and Admins.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return upload_tender_document(
        db=db,
        tender_id=tender_id,
        file=file,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/tender/{tender_id}",
    response_model=TenderDocumentListResponse,
    summary="List Tender Documents",
)
def list_tender_docs(
    tender_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List all document attachments for a tender.
    Bidders can view published tender documents; Officers/Admins can view drafts.
    """
    return get_tender_documents(db=db, tender_id=tender_id, user=current_user)


@router.get(
    "/tender/{tender_id}/{document_id}",
    response_model=TenderDocumentResponse,
    summary="Get Tender Document Metadata",
)
def get_tender_doc(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get metadata for a specific tender document.
    """
    return get_tender_document_by_id(
        db=db,
        tender_id=tender_id,
        document_id=document_id,
        user=current_user,
    )


@router.get(
    "/tender/{tender_id}/{document_id}/download",
    summary="Download Tender Document",
)
def download_tender_doc(
    tender_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Download or stream tender document file bytes securely.
    """
    content, filename, mime_type = download_tender_document(
        db=db,
        tender_id=tender_id,
        document_id=document_id,
        user=current_user,
    )
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


@router.delete(
    "/tender/{tender_id}/{document_id}",
    summary="Delete Tender Document",
)
def delete_tender_doc(
    tender_id: str,
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRoleEnum.PROCUREMENT_OFFICER.value,
        UserRoleEnum.ADMIN.value,
    )),
):
    """
    Delete a tender document.
    Allowed only in DRAFT status by the creating Officer or Admins.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return delete_tender_document(
        db=db,
        tender_id=tender_id,
        document_id=document_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


# =========================================================================
# BID DOCUMENT & OCR ENDPOINTS
# =========================================================================

@router.post(
    "/bid/{bid_id}",
    response_model=BidDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Bid Document with OCR Processing",
)
def upload_bid_doc(
    bid_id: str,
    request: Request,
    file: UploadFile = File(..., description="Supporting document file (PDF, PNG, JPG, etc.)"),
    document_type: DocumentTypeEnum = Form(DocumentTypeEnum.OTHER, description="Category of the document"),
    auto_ocr: bool = Query(True, description="Automatically trigger OCR text extraction"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRoleEnum.BIDDER.value,
        UserRoleEnum.ADMIN.value,
    )),
):
    """
    Upload a supporting bid document (GST, PAN, financial audit, experience certificate).
    Runs automatic OCR text extraction pipeline.
    Strictly verifies bidder ownership to protect against IDOR.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return upload_bid_document(
        db=db,
        bid_id=bid_id,
        file=file,
        document_type=document_type,
        user=current_user,
        auto_ocr=auto_ocr,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.get(
    "/bid/{bid_id}",
    response_model=BidDocumentListResponse,
    summary="List Bid Supporting Documents",
)
def list_bid_docs(
    bid_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List supporting documents for a bid.
    Bidders can only view their own bid documents. Officers/Admins/Reviewers have audit access.
    """
    return get_bid_documents(db=db, bid_id=bid_id, user=current_user)


@router.get(
    "/bid/{bid_id}/{document_id}",
    response_model=BidDocumentResponse,
    summary="Get Bid Document Metadata",
)
def get_bid_doc(
    bid_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get metadata and OCR processing status for a single bid document.
    """
    return get_bid_document_by_id(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
    )


@router.get(
    "/bid/{bid_id}/{document_id}/download",
    summary="Download Bid Document",
)
def download_bid_doc(
    bid_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Download or view bid document file bytes securely.
    """
    content, filename, mime_type = download_bid_document(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
    )
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


@router.delete(
    "/bid/{bid_id}/{document_id}",
    summary="Delete Bid Document",
)
def delete_bid_doc(
    bid_id: str,
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete a bid document.
    Allowed only in DRAFT bid status prior to tender deadline by the bidder or Admins.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return delete_bid_document(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/bid/{bid_id}/{document_id}/process-ocr",
    response_model=OCRExtractionResponse,
    summary="Trigger/Re-run OCR Extraction",
)
def trigger_ocr(
    bid_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Trigger or re-run OCR text extraction on an existing bid document.
    """
    return process_bid_document_ocr(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
    )


@router.get(
    "/bid/{bid_id}/{document_id}/ocr",
    response_model=OCRExtractionResponse,
    summary="Get OCR Extraction Result",
)
def get_ocr_result(
    bid_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve extracted OCR text, page-by-page breakdown, and confidence score for a bid document.
    """
    return get_bid_document_ocr(
        db=db,
        bid_id=bid_id,
        document_id=document_id,
        user=current_user,
    )
