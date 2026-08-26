"""Pydantic schemas for Razorpay webhooks."""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RazorpayWebhookPayload(BaseModel):
    event: str = Field(description="Event name e.g. payment.failed, payment.captured, order.paid")
    account_id: Optional[str] = None
    contains: list[str] = Field(default_factory=lambda: ["payment"])
    payload: Dict[str, Any] = Field(description="Event entity payload")
    created_at: int = Field(description="Unix timestamp")


class WebhookVerificationResult(BaseModel):
    success: bool
    event: str
    entity_id: Optional[str] = None
    signature_valid: bool
    idempotent_processed: bool
    recovery_case_id: Optional[str] = None
    message: str
