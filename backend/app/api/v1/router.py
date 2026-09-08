from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.tenders import router as tenders_router
from backend.app.api.v1.bids import router as bids_router
from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.extraction import router as extraction_router
from backend.app.api.v1.evidence import router as evidence_router
from backend.app.api.v1.compliance import router as compliance_router
from backend.app.api.v1.verification import router as verification_router
from backend.app.api.v1.review import router as review_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.notifications import router as notifications_router
from backend.app.api.v1.audit_logs import router as audit_logs_router

api_router = APIRouter()

# Register core endpoints
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users & RBAC"])
api_router.include_router(tenders_router, prefix="/tenders", tags=["Tender Management"])
api_router.include_router(bids_router, prefix="/bids", tags=["Bid Management"])
api_router.include_router(documents_router, prefix="/documents", tags=["Document Management & OCR"])
api_router.include_router(extraction_router, prefix="/extraction", tags=["AI Entity Extraction"])
api_router.include_router(evidence_router, prefix="/evidence", tags=["Evidence & Traceability"])
api_router.include_router(compliance_router, prefix="/compliance", tags=["Compliance Engine"])
api_router.include_router(verification_router, prefix="/verification", tags=["External Registry Verification"])
api_router.include_router(review_router, prefix="/review", tags=["Human Review Workflow"])
api_router.include_router(reports_router, prefix="/reports", tags=["Compliance Reports"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Operational Dashboards"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["User Notifications"])
api_router.include_router(audit_logs_router, prefix="/audit-logs", tags=["Security Audit Trail"])





