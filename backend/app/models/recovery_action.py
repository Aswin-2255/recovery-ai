"""RecoveryAction entity model for recording discrete bounded recovery actions."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String(64), primary_key=True, default=lambda: f"act_{uuid.uuid4().hex[:14]}")
    recovery_case_id = Column(String(64), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True)

    action_type = Column(String(64), nullable=False)  # smart_retry, payment_link, fallback_payment_method, customer_reminder, manual_escalation
    status = Column(String(32), default="pending", nullable=False, index=True)  # pending, executing, completed, failed, blocked_by_policy
    amount_recovered = Column(Float, default=0.0, nullable=False)
    result = Column(String(512), nullable=True)  # summary text e.g. "Payment successful via UPI retry"
    execution_details_json = Column(Text, nullable=True)  # raw payload / response parameters

    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    recovery_case = relationship("RecoveryCase", back_populates="actions")

    __table_args__ = (
        Index("ix_recovery_actions_case_status", "recovery_case_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<RecoveryAction(id='{self.id}', type='{self.action_type}', status='{self.status}', recovered={self.amount_recovered})>"
