"""Pydantic schemas for transactions."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PaymentMethod, TransactionType, TransactionStatus, FailureCategory


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    customer_id: str
    order_id: Optional[str] = None
    amount: float
    currency: str = "INR"
    payment_method: str
    transaction_type: str
    status: str
    failure_category: str
    failure_code: Optional[str] = None
    failure_reason: Optional[str] = None
    retry_count: int
    max_retries_allowed: int
    gateway_reference: Optional[str] = None
    is_synthetic: bool
    is_degradation_incident: bool
    timestamp: datetime
    created_at: datetime


class TransactionFilter(BaseModel):
    status: Optional[str] = None
    payment_method: Optional[str] = None
    is_degradation_incident: Optional[bool] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class SimulateFailureRequest(BaseModel):
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    amount: float = Field(gt=0.0, description="Amount in INR")
    payment_method: PaymentMethod = PaymentMethod.UPI
    transaction_type: TransactionType = TransactionType.ONE_TIME
    failure_code: str = Field(default="BAD_REQUEST_GATEWAY_TIMEOUT")
    is_degradation_incident: bool = False
