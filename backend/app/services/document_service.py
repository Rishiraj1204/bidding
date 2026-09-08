import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from backend.app.core.deps import get_user_roles
from backend.app.core.storage import get_storage_provider
from backend.app.models.bid import Bid, BidDocument, BidStatusEnum, DocumentTypeEnum
from backend.app.models.document_extraction import DocumentExtraction
from backend.app.models.tender import DocumentStatusEnum, Tender, TenderDocument, TenderStatusEnum
from backend.app.models.user import Role, User, UserRoleEnum
from backend.app.ocr.provider import get_ocr_provider
from backend.app.schemas.document import (
    BidDocumentListResponse,
    BidDocumentResponse,
    OCRExtractionResponse,
    TenderDocumentListResponse,
    TenderDocumentResponse,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.services.notification_service import create_notification
from backend.app.utils.file_validation import validate_file_security


# =========================================================================
# TENDER DOCUMENTS SERVICE
# =========================================================================

def _tender_doc_to_response(doc: TenderDocument) -> TenderDocumentResponse:
    return TenderDocumentResponse(
        id=doc.id,
        tender_id=doc.tender_id,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        file_hash=doc.file_hash,
        status=doc.status,
        created_at=doc.created_at,
    )


def _notify_tender_document_visibility(
    db: Session,
    tender: Tender,
    document: TenderDocument,
    uploader: User,
) -> None:
    """Notify tender administrators and procurement officers about a new specification."""
    recipients = (
        db.query(User)
        .join(User.roles)
        .filter(
            Role.name.in_(
                [
                    UserRoleEnum.ADMIN.value,
                    UserRoleEnum.PROCUREMENT_OFFICER.value,
                ]
            ),
            User.id != uploader.id,
            User.is_active.is_(True),
        )
        .distinct()
        .all()
    )

    for recipient in recipients:
        create_notification(
            db=db,
            user_id=recipient.id,
            title="Tender specification uploaded",
            message=(
                f"{uploader.full_name} uploaded '{document.filename}' "
                f"for tender {tender.tender_number}."
            ),
            notification_type="INFO",
            related_resource_type="tender",
            related_resource_id=tender.id,
        )


def upload_tender_document(
    db: Session,
    tender_id: str,
    file: UploadFile,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> TenderDocumentResponse:
    """
    Upload a document attachment for a Tender.
    Restricted to the creating Procurement Officer or Admins.
    """
    # 1. Validate tender
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found",
        )

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles
    is_officer = "PROCUREMENT_OFFICER" in user_roles

    if not is_admin and (tender.created_by_id != user.id and not is_officer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload documents for this tender.",
        )

    if not is_admin and tender.status not in {TenderStatusEnum.DRAFT, TenderStatusEnum.PUBLISHED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot upload documents to tender in '{tender.status.value}' status.",
        )

    # 2. Read and validate file content
    try:
        content = file.file.read()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded file data.",
        )

    clean_filename, mime_type, file_size = validate_file_security(
        content=content,
        filename=file.filename or "tender_spec.pdf",
        content_type=file.content_type,
    )

    # 3. Save file using StorageProvider
    storage_provider = get_storage_provider()
    storage_key, sha256_hash, _ = storage_provider.save_file(
        content=content,
        original_filename=clean_filename,
        subfolder="tenders",
    )

    # 4. Create database record
    doc = TenderDocument(
        id=str(uuid.uuid4()),
        tender_id=tender.id,
        filename=clean_filename,
        file_path=storage_key,
        file_size=file_size,
        mime_type=mime_type,
        file_hash=sha256_hash,
        status=DocumentStatusEnum.PROCESSED,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        action="TENDER_DOCUMENT_UPLOADED",
        resource_type="tender_document",
        resource_id=doc.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "tender_id": tender.id,
            "filename": clean_filename,
            "file_size": file_size,
            "file_hash": sha256_hash,
            "mime_type": mime_type,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    _notify_tender_document_visibility(
        db=db,
        tender=tender,
        document=doc,
        uploader=user,
    )

    return _tender_doc_to_response(doc)


def get_tender_documents(
    db: Session,
    tender_id: str,
    user: User,
) -> TenderDocumentListResponse:
    """List documents attached to a tender."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"}))

    if tender.status == TenderStatusEnum.DRAFT and not is_staff and tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tender is in draft state and documents are not accessible to public bidders.",
        )

    docs = (
        db.query(TenderDocument)
        .filter(TenderDocument.tender_id == tender.id)
        .order_by(TenderDocument.created_at.desc())
        .all()
    )
    return TenderDocumentListResponse(
        items=[_tender_doc_to_response(d) for d in docs],
        total=len(docs),
    )


def get_tender_document_by_id(
    db: Session,
    tender_id: str,
    document_id: str,
    user: User,
) -> TenderDocumentResponse:
    """Fetch tender document metadata."""
    doc = (
        db.query(TenderDocument)
        .options(selectinload(TenderDocument.tender))
        .filter(TenderDocument.id == document_id, TenderDocument.tender_id == tender_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender document not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"}))

    if doc.tender.status == TenderStatusEnum.DRAFT and not is_staff and doc.tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Tender is in draft.",
        )

    return _tender_doc_to_response(doc)


def download_tender_document(
    db: Session,
    tender_id: str,
    document_id: str,
    user: User,
) -> Tuple[bytes, str, str]:
    """Retrieve raw file content for download/view."""
    doc = (
        db.query(TenderDocument)
        .options(selectinload(TenderDocument.tender))
        .filter(TenderDocument.id == document_id, TenderDocument.tender_id == tender_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender document not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"}))

    if doc.tender.status == TenderStatusEnum.DRAFT and not is_staff and doc.tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to draft tender document.",
        )

    storage_provider = get_storage_provider()
    content = storage_provider.get_file_bytes(doc.file_path)
    return content, doc.filename, doc.mime_type


def delete_tender_document(
    db: Session,
    tender_id: str,
    document_id: str,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """Delete a tender document (only permitted in DRAFT state by creator or Admin)."""
    doc = (
        db.query(TenderDocument)
        .options(selectinload(TenderDocument.tender))
        .filter(TenderDocument.id == document_id, TenderDocument.tender_id == tender_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender document not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles

    if not is_admin and doc.tender.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete documents from this tender.",
        )

    if not is_admin and doc.tender.status != TenderStatusEnum.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete documents from a tender in '{doc.tender.status.value}' status.",
        )

    # Delete from storage provider
    storage_provider = get_storage_provider()
    storage_provider.delete_file(doc.file_path)

    filename = doc.filename
    db.delete(doc)
    db.commit()

    log_audit_event(
        db=db,
        action="TENDER_DOCUMENT_DELETED",
        resource_type="tender_document",
        resource_id=document_id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"filename": filename, "tender_id": tender_id},
        new_state=None,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": f"Document '{filename}' deleted successfully", "status": "success"}


# =========================================================================
# BID DOCUMENTS & OCR SERVICE
# =========================================================================

def _bid_doc_to_response(doc: BidDocument) -> BidDocumentResponse:
    has_ocr = False
    ocr_conf = None
    if doc.extractions:
        latest = doc.extractions[-1]
        has_ocr = latest.status == "COMPLETED"
        ocr_conf = latest.ocr_confidence

    return BidDocumentResponse(
        id=doc.id,
        bid_id=doc.bid_id,
        document_type=doc.document_type,
        filename=doc.filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        file_hash=doc.file_hash,
        status=doc.status,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        has_ocr=has_ocr,
        ocr_confidence=ocr_conf,
    )


def upload_bid_document(
    db: Session,
    bid_id: str,
    file: UploadFile,
    document_type: DocumentTypeEnum,
    user: User,
    auto_ocr: bool = True,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidDocumentResponse:
    """
    Upload a supporting document for a Bid (with automatic OCR processing pipeline).
    Strictly verifies bidder ownership to prevent IDOR.
    """
    # 1. Fetch bid and tender
    bid = (
        db.query(Bid)
        .options(selectinload(Bid.tender))
        .filter(Bid.id == bid_id)
        .first()
    )
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles

    # IDOR Check
    if not is_admin and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not own this bid submission.",
        )

    if bid.status != BidStatusEnum.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot upload documents to a bid in '{bid.status.value}' status. Only DRAFT bids accept uploads.",
        )

    # Check tender submission deadline
    now_utc = datetime.now(timezone.utc)
    deadline = bid.tender.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender submission deadline has expired. Document upload locked.",
        )

    # 2. Read and validate file content
    try:
        content = file.file.read()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded file data.",
        )

    clean_filename, mime_type, file_size = validate_file_security(
        content=content,
        filename=file.filename or "supporting_doc.pdf",
        content_type=file.content_type,
    )

    # 3. Store file using StorageProvider
    storage_provider = get_storage_provider()
    storage_key, sha256_hash, _ = storage_provider.save_file(
        content=content,
        original_filename=clean_filename,
        subfolder="bids",
    )

    # 4. Create BidDocument record (Status: UPLOADED)
    bid_doc = BidDocument(
        id=str(uuid.uuid4()),
        bid_id=bid.id,
        document_type=document_type,
        filename=clean_filename,
        file_path=storage_key,
        file_size=file_size,
        mime_type=mime_type,
        file_hash=sha256_hash,
        status=DocumentStatusEnum.UPLOADED,
    )
    db.add(bid_doc)
    db.commit()
    db.refresh(bid_doc)

    # 5. Execute OCR Extraction Pipeline if auto_ocr is True
    if auto_ocr:
        bid_doc.status = DocumentStatusEnum.PROCESSING
        db.commit()

        ocr_provider = get_ocr_provider()
        ocr_result = ocr_provider.extract_text(
            content=content,
            filename=clean_filename,
            mime_type=mime_type,
        )

        extraction = DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=bid_doc.id,
            raw_text=ocr_result.raw_text,
            total_pages=ocr_result.total_pages,
            ocr_confidence=ocr_result.ocr_confidence,
            extracted_data={
                "page_results": [p.model_dump() for p in ocr_result.page_results],
                "metadata": ocr_result.metadata,
            },
            status=ocr_result.status,
            error_message=ocr_result.error_message,
        )
        db.add(extraction)

        if ocr_result.status == "COMPLETED":
            bid_doc.status = DocumentStatusEnum.PROCESSED
        else:
            bid_doc.status = DocumentStatusEnum.FAILED

        db.commit()
        db.refresh(bid_doc)

    log_audit_event(
        db=db,
        action="BID_DOCUMENT_UPLOADED",
        resource_type="bid_document",
        resource_id=bid_doc.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "bid_id": bid.id,
            "filename": clean_filename,
            "document_type": document_type.value,
            "file_size": file_size,
            "file_hash": sha256_hash,
            "status": bid_doc.status.value,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Reload with extractions
    bid_doc = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.extractions))
        .filter(BidDocument.id == bid_doc.id)
        .first()
    )
    return _bid_doc_to_response(bid_doc)


def get_bid_documents(
    db: Session,
    bid_id: str,
    user: User,
) -> BidDocumentListResponse:
    """List documents attached to a bid with RBAC + IDOR isolation."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    if not is_staff and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view documents for this bid.",
        )

    docs = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.extractions))
        .filter(BidDocument.bid_id == bid.id)
        .order_by(BidDocument.created_at.desc())
        .all()
    )

    return BidDocumentListResponse(
        items=[_bid_doc_to_response(d) for d in docs],
        total=len(docs),
    )


def get_bid_document_by_id(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
) -> BidDocumentResponse:
    """Retrieve metadata for a single bid document."""
    doc = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.bid), selectinload(BidDocument.extractions))
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    if not is_staff and doc.bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: IDOR protection violation.",
        )

    return _bid_doc_to_response(doc)


def download_bid_document(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
) -> Tuple[bytes, str, str]:
    """Retrieve binary content for a bid document."""
    doc = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.bid))
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    if not is_staff and doc.bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not have permission to download this document.",
        )

    storage_provider = get_storage_provider()
    content = storage_provider.get_file_bytes(doc.file_path)
    return content, doc.filename, doc.mime_type


def delete_bid_document(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """Delete a bid document (only allowed in DRAFT bid status by owner or Admin)."""
    doc = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.bid).selectinload(Bid.tender))
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    user_roles = get_user_roles(user)
    is_admin = user.is_superuser or "ADMIN" in user_roles

    if not is_admin and doc.bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete documents from this bid.",
        )

    if doc.bid.status != BidStatusEnum.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete documents from a bid in '{doc.bid.status.value}' status.",
        )

    # Check deadline
    now_utc = datetime.now(timezone.utc)
    deadline = doc.bid.tender.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tender submission deadline has passed. Modifications locked.",
        )

    storage_provider = get_storage_provider()
    storage_provider.delete_file(doc.file_path)

    filename = doc.filename
    db.delete(doc)
    db.commit()

    log_audit_event(
        db=db,
        action="BID_DOCUMENT_DELETED",
        resource_type="bid_document",
        resource_id=document_id,
        actor_id=user.id,
        actor_email=user.email,
        previous_state={"filename": filename, "bid_id": bid_id},
        new_state=None,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": f"Document '{filename}' deleted successfully", "status": "success"}


def process_bid_document_ocr(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
) -> OCRExtractionResponse:
    """Manually trigger / re-run OCR extraction on an existing bid document."""
    doc = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.bid))
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    if not is_staff and doc.bid.bidder_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # Fetch file content
    storage_provider = get_storage_provider()
    content = storage_provider.get_file_bytes(doc.file_path)

    doc.status = DocumentStatusEnum.PROCESSING
    db.commit()

    ocr_provider = get_ocr_provider()
    ocr_result = ocr_provider.extract_text(
        content=content,
        filename=doc.filename,
        mime_type=doc.mime_type,
    )

    # Check if extraction already exists
    existing_ext = (
        db.query(DocumentExtraction)
        .filter(DocumentExtraction.document_id == doc.id)
        .first()
    )

    if existing_ext:
        existing_ext.raw_text = ocr_result.raw_text
        existing_ext.total_pages = ocr_result.total_pages
        existing_ext.ocr_confidence = ocr_result.ocr_confidence
        existing_ext.extracted_data = {
            "page_results": [p.model_dump() for p in ocr_result.page_results],
            "metadata": ocr_result.metadata,
        }
        existing_ext.status = ocr_result.status
        existing_ext.error_message = ocr_result.error_message
        extraction = existing_ext
    else:
        extraction = DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            raw_text=ocr_result.raw_text,
            total_pages=ocr_result.total_pages,
            ocr_confidence=ocr_result.ocr_confidence,
            extracted_data={
                "page_results": [p.model_dump() for p in ocr_result.page_results],
                "metadata": ocr_result.metadata,
            },
            status=ocr_result.status,
            error_message=ocr_result.error_message,
        )
        db.add(extraction)

    if ocr_result.status == "COMPLETED":
        doc.status = DocumentStatusEnum.PROCESSED
    else:
        doc.status = DocumentStatusEnum.FAILED

    db.commit()
    db.refresh(extraction)

    return OCRExtractionResponse(
        id=extraction.id,
        document_id=extraction.document_id,
        raw_text=extraction.raw_text,
        total_pages=extraction.total_pages,
        ocr_confidence=extraction.ocr_confidence,
        extracted_data=extraction.extracted_data,
        status=extraction.status,
        error_message=extraction.error_message,
        created_at=extraction.created_at,
    )


def get_bid_document_ocr(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
) -> OCRExtractionResponse:
    """Retrieve OCR extraction result for a bid document."""
    doc = (
        db.query(BidDocument)
        .options(selectinload(BidDocument.bid), selectinload(BidDocument.extractions))
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )

    if not is_staff and doc.bid.bidder_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if not doc.extractions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No OCR extraction available for this document. Try running OCR processing first.",
        )

    extraction = doc.extractions[-1]
    return OCRExtractionResponse(
        id=extraction.id,
        document_id=extraction.document_id,
        raw_text=extraction.raw_text,
        total_pages=extraction.total_pages,
        ocr_confidence=extraction.ocr_confidence,
        extracted_data=extraction.extracted_data,
        status=extraction.status,
        error_message=extraction.error_message,
        created_at=extraction.created_at,
    )
