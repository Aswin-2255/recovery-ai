"""Transaction entity model capturing payments, failures, and metadata."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(64), primary_key=True, default=lambda: f"txn_{uuid.uuid4().hex[:14]}")
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(64), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String(64), nullable=True, index=True)

    amount = Column(Float, nullable=False)
    currency = Column(String(8), default="INR", nullable=False)
    payment_method = Column(String(32), nullable=False, index=True)  # upi, card, netbanking, wallet, emi
    transaction_type = Column(String(32), default="one_time", nullable=False)  # one_time, subscription, invoice, checkout
    status = Column(String(32), default="pending", nullable=False, index=True)  # success, failed, abandoned, pending

    failure_category = Column(String(32), default="none", nullable=False)  # none, temporary, permanent, abandonment, systemic_degradation
    failure_code = Column(String(64), nullable=True, index=True)  # e.g. GATEWAY_TIMEOUT, INSUFFICIENT_FUNDS
    failure_reason = Column(String(512), nullable=True)  # human-readable explanation

    retry_count = Column(Integer, default=0, nullable=False)
    max_retries_allowed = Column(Integer, default=3, nullable=False)
    gateway_reference = Column(String(128), nullable=True)

    is_synthetic = Column(Boolean, default=True, nullable=False)
    is_degradation_incident = Column(Boolean, default=False, nullable=False, index=True)

    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")
    recovery_case = relationship("RecoveryCase", back_populates="transaction", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_transactions_mcht_status_ts", "merchant_id", "status", "timestamp"),
        Index("ix_transactions_method_status", "payment_method", "status"),
    )

    def __repr__(self) -> str:
        return f"<Transaction(id='{self.id}', amount={self.amount}, method='{self.payment_method}', status='{self.status}')>"
