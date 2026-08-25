"""RecoveryCase entity model for tracking revenue-at-risk workflows."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(String(64), primary_key=True, default=lambda: f"case_{uuid.uuid4().hex[:14]}")
    transaction_id = Column(String(64), ForeignKey("transactions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)

    revenue_at_risk = Column(Float, nullable=False)
    recovery_probability = Column(Float, nullable=True)  # 0.0 to 1.0 from ML model
    priority = Column(String(32), default="medium", nullable=False, index=True)  # critical, high, medium, low
    classification = Column(String(32), default="uncertain", nullable=False, index=True)  # recoverable, uncertain, unlikely_to_recover
    status = Column(String(32), default="open", nullable=False, index=True)  # open, diagnosed, in_progress, recovered, unrecoverable, escalated, stopped

    reason = Column(String(512), nullable=True)
    root_cause_summary = Column(String(1024), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    transaction = relationship("Transaction", back_populates="recovery_case")
    merchant = relationship("Merchant", back_populates="recovery_cases")
    actions = relationship("RecoveryAction", back_populates="recovery_case", cascade="all, delete-orphan", order_by="RecoveryAction.created_at")
    decisions = relationship("AgentDecision", back_populates="recovery_case", cascade="all, delete-orphan", order_by="AgentDecision.created_at")

    __table_args__ = (
        Index("ix_recovery_cases_mcht_status", "merchant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<RecoveryCase(id='{self.id}', at_risk={self.revenue_at_risk}, status='{self.status}', prob={self.recovery_probability})>"
