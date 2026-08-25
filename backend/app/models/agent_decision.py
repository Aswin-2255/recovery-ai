"""AgentDecision entity model for recording AI agent recommendations and policy evaluations."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id = Column(String(64), primary_key=True, default=lambda: f"dec_{uuid.uuid4().hex[:14]}")
    recovery_case_id = Column(String(64), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True)

    decision = Column(String(64), nullable=False)  # recommend_action, escalate, stop
    recommended_action = Column(String(64), nullable=True)  # smart_retry, payment_link, fallback_payment_method, etc.
    reasoning_summary = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0

    policy_approved = Column(Boolean, default=False, nullable=False)
    policy_rejection_reason = Column(String(512), nullable=True)
    execution_payload_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    recovery_case = relationship("RecoveryCase", back_populates="decisions")

    def __repr__(self) -> str:
        return f"<AgentDecision(id='{self.id}', decision='{self.decision}', confidence={self.confidence}, approved={self.policy_approved})>"
