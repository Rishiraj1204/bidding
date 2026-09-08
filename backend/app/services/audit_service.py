from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.deps import get_user_roles
from backend.app.models.audit import AuditLog
from backend.app.models.user import User
from backend.app.schemas.audit import AuditLogListResponse, AuditLogResponse


SENSITIVE_KEYS = {"password", "hashed_password", "token", "access_token", "secret", "secret_key", "authorization"}


def _sanitize_dict(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively redact sensitive credentials and secrets from audit state dumps."""
    if data is None or not isinstance(data, dict):
        return data
    sanitized = {}
    for k, v in data.items():
        if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_dict(v)
        else:
            sanitized[k] = v
    return sanitized


def log_audit_event(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Record a system operation into the audit log."""
    audit_entry = AuditLog(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        previous_state=_sanitize_dict(previous_state),
        new_state=_sanitize_dict(new_state),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(audit_entry)
    db.commit()
    return audit_entry


def list_audit_logs(
    db: Session,
    user: User,
    actor_email: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> AuditLogListResponse:
    """
    Retrieve filterable audit logs for security & compliance auditing.
    Strictly restricted to ADMIN and AUDITOR roles.
    """
    user_roles = get_user_roles(user)
    is_authorized = user.is_superuser or bool(user_roles.intersection({"ADMIN", "AUDITOR"}))
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Only Administrators and Auditors are authorized to inspect system audit logs.",
        )

    query = db.query(AuditLog)

    if actor_email:
        query = query.filter(AuditLog.actor_email.ilike(f"%{actor_email}%"))
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    if start_date:
        query = query.filter(AuditLog.timestamp >= start_date)
    if end_date:
        query = query.filter(AuditLog.timestamp <= end_date)

    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size).all()

    response_items = [
        AuditLogResponse(
            id=log.id,
            actor_id=log.actor_id,
            actor_email=log.actor_email,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            previous_state=_sanitize_dict(log.previous_state),
            new_state=_sanitize_dict(log.new_state),
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            timestamp=log.timestamp,
        )
        for log in items
    ]

    return AuditLogListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
    )
