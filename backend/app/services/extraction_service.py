import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from backend.app.ai.provider import get_ai_provider
from backend.app.core.deps import get_user_roles
from backend.app.models.bid import Bid, BidDocument
from backend.app.models.document_extraction import DocumentExtraction, Evidence, ExtractedEntity
from backend.app.models.user import User
from backend.app.schemas.extraction import (
    BidEvidenceListResponse,
    BidExtractionSummaryResponse,
    DocumentExtractionDetailResponse,
    EvidenceResponse,
    ExtractedEntityResponse,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.services.document_service import process_bid_document_ocr


def _entity_to_response(entity: ExtractedEntity) -> ExtractedEntityResponse:
    return ExtractedEntityResponse(
        id=entity.id,
        extraction_id=entity.extraction_id,
        entity_type=entity.entity_type,
        raw_value=entity.raw_value,
        normalized_value=entity.normalized_value,
        page_number=entity.page_number or 1,
        confidence=entity.confidence,
        source_snippet=entity.source_snippet,
        created_at=entity.created_at,
    )


def _evidence_to_response(ev: Evidence) -> EvidenceResponse:
    doc_filename = ev.bid_document.filename if ev.bid_document else None
    doc_type = ev.bid_document.document_type.value if ev.bid_document and hasattr(ev.bid_document.document_type, "value") else None
    return EvidenceResponse(
        id=ev.id,
        bid_document_id=ev.bid_document_id,
        entity_id=ev.entity_id,
        page_number=ev.page_number or 1,
        field_name=ev.field_name,
        extracted_value=ev.extracted_value,
        normalized_value=ev.normalized_value,
        confidence=ev.confidence,
        snippet_text=ev.snippet_text,
        source_type=ev.source_type,
        created_at=ev.created_at,
        document_filename=doc_filename,
        document_type=doc_type,
    )


def _check_bid_access(bid: Bid, user: User) -> None:
    """Validate user has permission to access this bid's extraction data."""
    user_roles = get_user_roles(user)
    is_staff = user.is_superuser or bool(
        user_roles.intersection({"ADMIN", "PROCUREMENT_OFFICER", "REVIEWER", "AUDITOR"})
    )
    if not is_staff and bid.bidder_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to view or extract data from this bid.",
        )


def extract_document_entities(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
    force_reextract: bool = False,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> DocumentExtractionDetailResponse:
    """
    Execute AI Entity Extraction and Evidence ground-truthing on a BidDocument.
    Strictly verifies ownership to prevent IDOR.
    """
    # 1. Fetch bid and document
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    doc = (
        db.query(BidDocument)
        .options(
            selectinload(BidDocument.extractions).selectinload(DocumentExtraction.entities),
            selectinload(BidDocument.evidence_records),
        )
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    # 2. Ensure OCR is available; if not, run OCR
    if not doc.extractions or not doc.extractions[-1].raw_text:
        process_bid_document_ocr(db, bid_id, document_id, user)
        db.refresh(doc)

    extraction = doc.extractions[-1] if doc.extractions else None
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve OCR text for document extraction.",
        )

    # 3. If OCR failed, record empty extraction
    if extraction.status == "FAILED" or not extraction.raw_text:
        return DocumentExtractionDetailResponse(
            id=extraction.id,
            document_id=doc.id,
            raw_text=extraction.raw_text,
            total_pages=extraction.total_pages,
            ocr_confidence=extraction.ocr_confidence,
            status="FAILED",
            error_message=extraction.error_message or "Document OCR failed or text is empty.",
            entities=[],
            evidence_records=[],
            extracted_data={},
            created_at=extraction.created_at,
        )

    # 4. Invoke AI Extraction Provider
    ai_provider = get_ai_provider()
    extraction_result = ai_provider.extract_entities(
        raw_text=extraction.raw_text,
        document_type=doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
        filename=doc.filename,
    )

    # 5. Clean prior entities & evidence for clean idempotent re-extraction
    if extraction.entities:
        for ent in extraction.entities:
            db.delete(ent)
    if doc.evidence_records:
        for ev in doc.evidence_records:
            db.delete(ev)
    db.flush()

    # 6. Persist Extracted Entities and Evidence Records
    persisted_entities: List[ExtractedEntity] = []
    persisted_evidence: List[Evidence] = []

    for raw_ent in extraction_result.entities:
        ent = ExtractedEntity(
            id=str(uuid.uuid4()),
            extraction_id=extraction.id,
            entity_type=raw_ent.entity_type,
            raw_value=raw_ent.raw_value,
            normalized_value=raw_ent.normalized_value,
            page_number=raw_ent.page_number or 1,
            confidence=raw_ent.confidence,
            source_snippet=raw_ent.source_snippet,
        )
        db.add(ent)
        persisted_entities.append(ent)

        # Create linked evidence record
        evidence = Evidence(
            id=str(uuid.uuid4()),
            bid_document_id=doc.id,
            entity_id=ent.id,
            page_number=raw_ent.page_number or 1,
            field_name=raw_ent.entity_type,
            extracted_value=raw_ent.raw_value,
            normalized_value=raw_ent.normalized_value,
            confidence=raw_ent.confidence,
            snippet_text=raw_ent.source_snippet,
            source_type="AI_EXTRACTION",
        )
        db.add(evidence)
        persisted_evidence.append(evidence)

    extraction.extracted_data = {
        "entity_count": len(persisted_entities),
        "fields_extracted": [e.entity_type for e in persisted_entities],
        "summary": extraction_result.summary,
    }
    db.commit()

    # Reload with full relationships
    extraction = (
        db.query(DocumentExtraction)
        .options(
            selectinload(DocumentExtraction.entities),
            selectinload(DocumentExtraction.document).selectinload(BidDocument.evidence_records),
        )
        .filter(DocumentExtraction.id == extraction.id)
        .first()
    )

    log_audit_event(
        db=db,
        action="DOCUMENT_AI_EXTRACTED",
        resource_type="document_extraction",
        resource_id=extraction.id,
        actor_id=user.id,
        actor_email=user.email,
        new_state={
            "bid_id": bid_id,
            "document_id": document_id,
            "entity_count": len(persisted_entities),
            "fields": [e.entity_type for e in persisted_entities],
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return DocumentExtractionDetailResponse(
        id=extraction.id,
        document_id=doc.id,
        raw_text=extraction.raw_text,
        total_pages=extraction.total_pages,
        ocr_confidence=extraction.ocr_confidence,
        status=extraction.status,
        error_message=extraction.error_message,
        entities=[_entity_to_response(e) for e in extraction.entities],
        evidence_records=[_evidence_to_response(ev) for ev in doc.evidence_records],
        extracted_data=extraction.extracted_data,
        created_at=extraction.created_at,
    )


def extract_bid_all_documents(
    db: Session,
    bid_id: str,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> BidExtractionSummaryResponse:
    """
    Run AI extraction across all supporting documents attached to a bid.
    """
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    docs = db.query(BidDocument).filter(BidDocument.bid_id == bid.id).all()
    for doc in docs:
        extract_document_entities(
            db=db,
            bid_id=bid.id,
            document_id=doc.id,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return get_bid_extraction_summary(db=db, bid_id=bid.id, user=user)


def get_document_extraction_details(
    db: Session,
    bid_id: str,
    document_id: str,
    user: User,
) -> DocumentExtractionDetailResponse:
    """Retrieve extraction details and entities for a single document."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    doc = (
        db.query(BidDocument)
        .options(
            selectinload(BidDocument.extractions).selectinload(DocumentExtraction.entities),
            selectinload(BidDocument.evidence_records),
        )
        .filter(BidDocument.id == document_id, BidDocument.bid_id == bid_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid document not found")

    if not doc.extractions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extraction found for this document. Please trigger extraction first.",
        )

    extraction = doc.extractions[-1]
    return DocumentExtractionDetailResponse(
        id=extraction.id,
        document_id=doc.id,
        raw_text=extraction.raw_text,
        total_pages=extraction.total_pages,
        ocr_confidence=extraction.ocr_confidence,
        status=extraction.status,
        error_message=extraction.error_message,
        entities=[_entity_to_response(e) for e in extraction.entities],
        evidence_records=[_evidence_to_response(ev) for ev in doc.evidence_records],
        extracted_data=extraction.extracted_data,
        created_at=extraction.created_at,
    )


def get_bid_extraction_summary(
    db: Session,
    bid_id: str,
    user: User,
) -> BidExtractionSummaryResponse:
    """Aggregated summary of all extracted entities and evidence for a bid."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    docs = (
        db.query(BidDocument)
        .options(
            selectinload(BidDocument.extractions).selectinload(DocumentExtraction.entities),
            selectinload(BidDocument.evidence_records),
        )
        .filter(BidDocument.bid_id == bid.id)
        .all()
    )

    all_entities: List[ExtractedEntityResponse] = []
    all_evidence: List[EvidenceResponse] = []

    for doc in docs:
        for ext in doc.extractions:
            for ent in ext.entities:
                all_entities.append(_entity_to_response(ent))
        for ev in doc.evidence_records:
            all_evidence.append(_evidence_to_response(ev))

    return BidExtractionSummaryResponse(
        bid_id=bid.id,
        total_documents=len(docs),
        total_entities_extracted=len(all_entities),
        total_evidence_records=len(all_evidence),
        entities=all_entities,
        evidence=all_evidence,
    )


def get_bid_evidence_list(
    db: Session,
    bid_id: str,
    user: User,
    field_name: Optional[str] = None,
    document_id: Optional[str] = None,
) -> BidEvidenceListResponse:
    """Fetch evidence records for a bid with optional field_name and document_id filters."""
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")

    _check_bid_access(bid, user)

    query = (
        db.query(Evidence)
        .join(BidDocument, Evidence.bid_document_id == BidDocument.id)
        .options(selectinload(Evidence.bid_document))
        .filter(BidDocument.bid_id == bid.id)
    )

    if document_id:
        query = query.filter(Evidence.bid_document_id == document_id)

    if field_name:
        query = query.filter(Evidence.field_name.ilike(field_name.strip()))

    records = query.order_by(Evidence.created_at.desc()).all()
    items = [_evidence_to_response(ev) for ev in records]

    return BidEvidenceListResponse(
        items=items,
        total=len(items),
    )


def get_evidence_detail(
    db: Session,
    evidence_id: str,
    user: User,
) -> EvidenceResponse:
    """Retrieve a single evidence item with traceability links."""
    ev = (
        db.query(Evidence)
        .options(
            selectinload(Evidence.bid_document).selectinload(BidDocument.bid),
            selectinload(Evidence.entity),
        )
        .filter(Evidence.id == evidence_id)
        .first()
    )
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence record not found")

    _check_bid_access(ev.bid_document.bid, user)
    return _evidence_to_response(ev)
