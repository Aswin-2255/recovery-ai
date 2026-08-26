"""Audit Logs REST API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog
from app.schemas.audit_log import AuditLogRead

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Trail"])


@router.get("", response_model=List[AuditLogRead], summary="List Audit Logs")
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity: recovery_case, transaction, recovery_action, agent_decision"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    actor: Optional[str] = Query(None, description="Filter by actor: system, ai_agent, policy_engine, simulator, merchant"),
    action: Optional[str] = Query(None, description="Filter by action code"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Query immutable audit log entries with optional filters."""
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if actor:
        query = query.filter(AuditLog.actor == actor)
    if action:
        query = query.filter(AuditLog.action == action)

    return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
