"""AuditLog entity model for maintaining an immutable trail of events, causes, and interventions."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime, Text, Index
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, default=lambda: f"aud_{uuid.uuid4().hex[:14]}")
    entity_type = Column(String(64), nullable=False, index=True)  # transaction, recovery_case, recovery_action, agent_decision, merchant
    entity_id = Column(String(64), nullable=False, index=True)

    actor = Column(String(64), nullable=False)  # system, ai_agent, policy_engine, merchant, simulator, razorpay_webhook
    action = Column(String(64), nullable=False, index=True)  # RISK_DETECTED, DIAGNOSIS_COMPLETED, DECISION_RECORDED, etc.

    what_happened = Column(Text, nullable=False)
    what_caused_it = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor_action", "actor", "action"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id='{self.id}', action='{self.action}', entity='{self.entity_type}:{self.entity_id}')>"
