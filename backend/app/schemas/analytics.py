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
