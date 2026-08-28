"""Pydantic schemas for metrics, analytics, and degradation incidents."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OverviewMetrics(BaseModel):
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    abandoned_transactions: int
    success_rate: float
    total_revenue_volume_inr: float
    total_revenue_at_risk_inr: float
    total_revenue_recovered_inr: float
    recovery_rate: float
    active_recovery_cases: int
    resolved_recovery_cases: int
    systemic_incidents_count: int


class BreakdownMetrics(BaseModel):
    by_payment_method: Dict[str, Dict[str, float]] = Field(
        description="Stats per payment method: total, success, failed, volume, at_risk"
    )
    by_failure_code: Dict[str, int] = Field(description="Frequency count by failure code")
    by_recovery_classification: Dict[str, int] = Field(
        description="Counts for recoverable, uncertain, unlikely_to_recover"
    )
    by_case_priority: Dict[str, int] = Field(description="Counts for critical, high, medium, low")


class IncidentStatusRead(BaseModel):
    is_incident_active: bool
    incident_method: Optional[str] = None
    affected_transactions_count: int
    estimated_revenue_at_risk_inr: float
    spike_failure_rate: float
    baseline_failure_rate: float
    incident_description: str


class BatchEvaluationRequest(BaseModel):
    seed: int = Field(default=42, description="Seed for deterministic dataset generation")
    total_transactions: int = Field(default=100, ge=5, le=1000, description="Total synthetic transactions to evaluate")
    include_incident: bool = Field(default=True, description="Whether to include simulated gateway degradation incident")
    merchant_id: Optional[str] = Field(default=None, description="Optional merchant ID")


class CategoryBreakdownItem(BaseModel):
    category: str = Field(description="Failure category or failure code name")
    total_evaluated: int = Field(description="Number of cases in this category/code")
    revenue_at_risk: float = Field(description="Total revenue at risk for this category/code in INR")
    recovered_count: int = Field(description="Number of cases successfully recovered")
    amount_recovered: float = Field(description="Total revenue recovered in INR")
    recovery_rate: float = Field(description="Percentage of cases recovered in this category/code")
    recovery_efficiency: float = Field(description="Percentage of revenue at risk recovered in this category/code")


class ActionBreakdownItem(BaseModel):
    action_type: str = Field(description="Recovery action type (e.g. smart_retry, payment_link)")
    attempt_count: int = Field(description="Total number of attempts executed for this action")
    success_count: int = Field(description="Number of successful/completed attempts")
    failed_count: int = Field(description="Number of failed attempts")
    blocked_by_policy_count: int = Field(description="Number of attempts blocked by Policy Engine")
    amount_recovered: float = Field(description="Total revenue recovered through this action type in INR")


class BatchEvaluationResponse(BaseModel):
    seed: int = Field(description="Random seed used for generation")
    total_transactions_evaluated: int = Field(description="Total transactions evaluated in the batch")
    total_transaction_value: float = Field(description="Total transaction volume across the batch in INR")
    total_revenue_at_risk: float = Field(description="Total initial revenue at risk from failed/abandoned transactions in INR")
    recoverable_cases: int = Field(description="Number of cases initially classified as recoverable")
    recovered_cases: int = Field(description="Number of cases successfully recovered")
    unrecoverable_cases: int = Field(description="Number of cases determined to be unrecoverable")
    policy_stopped_cases: int = Field(description="Number of cases stopped by Policy Engine guardrails")
    failed_recovery_attempts: int = Field(description="Number of recovery action attempts that failed")
    total_amount_recovered: float = Field(description="Total revenue successfully recovered in INR")
    recovery_rate: float = Field(description="Percentage of failed cases recovered (recovered / total failed * 100)")
    recovery_efficiency: float = Field(description="Percentage of revenue at risk recovered (amount recovered / revenue at risk * 100)")
    by_failure_category: Dict[str, CategoryBreakdownItem] = Field(description="Breakdown by failure category")
    by_failure_code: Dict[str, CategoryBreakdownItem] = Field(description="Breakdown by failure code")
    by_recovery_action: Dict[str, ActionBreakdownItem] = Field(description="Breakdown by recovery action type")
    execution_time_ms: float = Field(default=0.0, description="Total execution time in milliseconds")

