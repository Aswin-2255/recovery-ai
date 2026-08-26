"""Pydantic schemas for recovery actions and lifecycle workflow execution."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class RecoveryActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_case_id: str
    action_type: str
    status: str
    amount_recovered: float
    result: Optional[str] = None
    execution_details_json: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime


class AgentDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_case_id: str
    decision: str
    recommended_action: Optional[str] = None
    reasoning_summary: str
    confidence: float
    policy_approved: bool
    policy_rejection_reason: Optional[str] = None
    execution_payload_json: Optional[str] = None
    created_at: datetime


class ExecuteActionRequest(BaseModel):
    action_type: str = Field(description="Action to execute e.g. smart_retry, payment_link, fallback_payment_method, customer_reminder, manual_escalation")
    force_mode: Optional[str] = Field(default="simulator", description="simulator or razorpay_test")


class ExecuteActionResult(BaseModel):
    action_id: str
    case_id: str
    action_type: str
    status: str
    policy_approved: bool
    policy_rejection_reason: Optional[str] = None
    amount_recovered: float
    result_message: str
    executed_at: datetime


class FullRecoveryWorkflowResult(BaseModel):
    case_id: str
    transaction_id: str
    lifecycle_stage_completed: str = "6_MEASURE"
    stages_executed: List[str]
    root_cause: str
    decision: str
    recommended_action: Optional[str]
    policy_approved: bool
    action_status: str
    amount_at_risk: float
    amount_recovered: float
    case_final_status: str
    audit_log_ids: List[str]
    timestamp: datetime
