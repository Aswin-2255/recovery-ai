"""Customer entity model with payment history telemetry."""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(64), primary_key=True, default=lambda: f"cust_{uuid.uuid4().hex[:12]}")
    merchant_id = Column(String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(32), nullable=True)
    historical_success_count = Column(Integer, default=0, nullable=False)
    historical_failure_count = Column(Integer, default=0, nullable=False)
    total_spend_inr = Column(Float, default=0.0, nullable=False)
    trust_score = Column(Float, default=1.0, nullable=False)  # 0.0 to 1.0 based on success history
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="customers")
    transactions = relationship("Transaction", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Customer(id='{self.id}', name='{self.name}', email='{self.email}')>"
