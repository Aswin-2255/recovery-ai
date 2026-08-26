"""Pydantic schemas for recovery cases."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.transaction import TransactionRead


class RecoveryActionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action_type: str
    status: str
    amount_recovered: float
    result: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime


class AgentDecisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    decision: str
    recommended_action: Optional[str] = None
    reasoning_summary: str
    confidence: float
    policy_approved: bool
    policy_rejection_reason: Optional[str] = None
    created_at: datetime


class RecoveryCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_id: str
    merchant_id: str
    revenue_at_risk: float
    recovery_probability: Optional[float] = None
    priority: str
    classification: str
    status: str
    reason: Optional[str] = None
    root_cause_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RecoveryCaseDetail(RecoveryCaseRead):
    transaction: Optional[TransactionRead] = None
    actions: List[RecoveryActionSummary] = Field(default_factory=list)
    decisions: List[AgentDecisionSummary] = Field(default_factory=list)


class RecoveryCaseFilter(BaseModel):
    status: Optional[str] = None
    classification: Optional[str] = None
    priority: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class DiagnoseResponse(BaseModel):
    case_id: str
    root_cause_summary: str
    failure_category: str
    failure_code: Optional[str]
    systemic_degradation_detected: bool
    is_transient: bool
    diagnosed_at: datetime
    retrieved_knowledge: List["RetrievedKnowledgeResponse"] = Field(default_factory=list)


class RetrievedKnowledgeResponse(BaseModel):
    scenario: str
    failure_codes: List[str]
    description: str
    likely_root_cause: str
    recommended_recovery_actions: List[str]
    retry_guidance: str
    risk_considerations: str
    policy_considerations: str
    do_not_retry_conditions: str
    escalation_conditions: str
    applicable_payment_methods: List[str] = Field(default_factory=list)


class DecideResponse(BaseModel):
    case_id: str
    decision: str
    recommended_action: Optional[str]
    confidence: float
    reasoning_summary: str
    policy_approved: bool
    policy_rejection_reason: Optional[str] = None
    decided_at: datetime
