"""Pydantic schemas for policy engine and guardrails."""
from typing import Optional, List
from pydantic import BaseModel, Field


class PolicyEvaluationRequest(BaseModel):
    case_id: Optional[str] = None
    action_type: str = Field(description="Action type e.g. smart_retry, payment_link, fallback_payment_method")
    retry_count: int = Field(default=0, ge=0)
    max_retries_allowed: int = Field(default=3, ge=1)
    amount: float = Field(default=1000.0, gt=0.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    failure_code: Optional[str] = None
    customer_trust_score: float = Field(default=1.0, ge=0.0, le=1.0)


class PolicyEvaluationResult(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None
    suggested_alternative: Optional[str] = None
    rules_checked: List[str] = Field(default_factory=list)
    confidence_passed: bool
    retry_limit_passed: bool
    amount_threshold_passed: bool
    action_applicability_passed: bool


class PolicyConfigRead(BaseModel):
    max_recovery_retries: int
    min_recovery_confidence: float
    auto_recovery_threshold_inr: float
    stopping_rules: List[str]
    enforced_guardrails: List[str]
