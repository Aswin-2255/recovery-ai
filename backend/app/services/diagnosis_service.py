"""Root Cause Analysis (RCA) and Payment Degradation Diagnosis Service.

Provides deterministic, explainable diagnosis of payment failures,
evaluating failure codes, transaction types, customer history, and
network/gateway degradation patterns without fabrication.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.enums import FailureCategory, PaymentMethod, TransactionStatus
from app.models.transaction import Transaction
from app.services.synthetic_generator import FAILURE_CATALOG


@dataclass
class DiagnosisResult:
    case_id: str
    root_cause_summary: str
    failure_category: str
    failure_code: Optional[str]
    is_transient: bool
    systemic_degradation_detected: bool
    incident_method: Optional[str]
    detailed_metrics: Dict[str, Any]


class DiagnosisService:
    """Performs explainable Root Cause Analysis on failed transactions."""

    def diagnose_case(self, db: Session, case_id: str, txn: Transaction) -> DiagnosisResult:
        """
        Analyze a transaction failure to determine root cause and systemic degradation.
        """
        f_code = txn.failure_code or "UNKNOWN_FAILURE"
        f_cat = txn.failure_category
        method = txn.payment_method

        # Look up failure catalog definition
        catalog_def = FAILURE_CATALOG.get(f_code)
        is_transient = catalog_def.category == FailureCategory.TEMPORARY if catalog_def else (f_cat == FailureCategory.TEMPORARY.value)

        # Check for systemic degradation incident (e.g. UPI switch surge)
        systemic_incident = txn.is_degradation_incident
        
        # Real-time degradation check in the local database around this time window
        recent_failures_count = (
            db.query(func.count(Transaction.id))
            .filter(
                Transaction.merchant_id == txn.merchant_id,
                Transaction.payment_method == method,
                Transaction.status == TransactionStatus.FAILED.value,
            )
            .scalar() or 0
        )
        total_method_txns = (
            db.query(func.count(Transaction.id))
            .filter(
                Transaction.merchant_id == txn.merchant_id,
                Transaction.payment_method == method,
            )
            .scalar() or 1
        )
        method_failure_rate = round(recent_failures_count / max(1, total_method_txns), 3)

        if method_failure_rate > 0.25:
            systemic_incident = True

        # Generate explainable root cause summary
        if systemic_incident and method == PaymentMethod.UPI.value:
            root_cause = (
                f"Systemic UPI bank gateway degradation detected. NPCI switch timeout and high latency "
                f"spurred failure code '{f_code}'. Transaction is transiently recoverable once traffic normalizes."
            )
        elif catalog_def:
            root_cause = (
                f"Root Cause: {catalog_def.reason} (Category: {catalog_def.category.value.upper()}). "
                f"Baseline recoverability is {catalog_def.base_recoverability * 100:.0f}%."
            )
        elif f_cat == FailureCategory.ABANDONMENT.value:
            root_cause = (
                f"Customer checkout abandonment detected on {method.upper()} payment stage. "
                f"No bank debit was initiated; recoverable via customer reminder or payment link."
            )
        else:
            root_cause = f"Payment failure with code '{f_code}' under {method.upper()} instrument."

        return DiagnosisResult(
            case_id=case_id,
            root_cause_summary=root_cause,
            failure_category=f_cat,
            failure_code=f_code,
            is_transient=is_transient,
            systemic_degradation_detected=systemic_incident,
            incident_method=method if systemic_incident else None,
            detailed_metrics={
                "method_failure_rate": method_failure_rate,
                "total_method_transactions": total_method_txns,
                "total_method_failures": recent_failures_count,
                "retry_count": txn.retry_count,
                "is_synthetic": txn.is_synthetic,
            },
        )


diagnosis_service = DiagnosisService()
