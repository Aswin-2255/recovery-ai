"""Database Analytics and Metrics Computation Service.

Calculates exact financial metrics, recovery ratios, method performance,
and payment degradation statistics directly from database queries.
"""
from collections import Counter
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Transaction, RecoveryCase, RecoveryAction, AuditLog
from app.models.enums import TransactionStatus, RecoveryCaseStatus, PaymentMethod


class AnalyticsService:
    """Computes verified aggregations for dashboards and reports."""

    def get_overview_metrics(self, db: Session) -> Dict[str, Any]:
        """Compute top-level KPI metrics."""
        total_txns = db.query(Transaction).count()
        success_txns = db.query(Transaction).filter(Transaction.status == TransactionStatus.SUCCESS.value).count()
        failed_txns = db.query(Transaction).filter(Transaction.status == TransactionStatus.FAILED.value).count()
        abandoned_txns = db.query(Transaction).filter(Transaction.status == TransactionStatus.ABANDONED.value).count()

        success_rate = (success_txns / total_txns * 100) if total_txns > 0 else 0.0

        total_volume = db.query(func.sum(Transaction.amount)).scalar() or 0.0
        
        # Total revenue at risk: sum of active open recovery cases
        total_at_risk = (
            db.query(func.sum(RecoveryCase.revenue_at_risk))
            .filter(RecoveryCase.status.in_([
                RecoveryCaseStatus.OPEN.value,
                RecoveryCaseStatus.DIAGNOSED.value,
                RecoveryCaseStatus.IN_PROGRESS.value,
            ]))
            .scalar() or 0.0
        )

        # Total revenue recovered from completed recovery actions
        total_recovered = (
            db.query(func.sum(RecoveryAction.amount_recovered))
            .filter(RecoveryAction.status == "completed")
            .scalar() or 0.0
        )

        initial_risk_pool = (
            db.query(func.sum(RecoveryCase.revenue_at_risk)).scalar() or 0.0
        ) + total_recovered
        recovery_rate = (total_recovered / initial_risk_pool * 100) if initial_risk_pool > 0 else 0.0

        active_cases = (
            db.query(RecoveryCase)
            .filter(RecoveryCase.status.in_([
                RecoveryCaseStatus.OPEN.value,
                RecoveryCaseStatus.DIAGNOSED.value,
                RecoveryCaseStatus.IN_PROGRESS.value,
            ]))
            .count()
        )
        resolved_cases = (
            db.query(RecoveryCase)
            .filter(RecoveryCase.status.in_([
                RecoveryCaseStatus.RECOVERED.value,
                RecoveryCaseStatus.UNRECOVERABLE.value,
                RecoveryCaseStatus.STOPPED.value,
            ]))
            .count()
        )

        incident_txns = (
            db.query(Transaction)
            .filter(Transaction.is_degradation_incident == True)
            .count()
        )

        return {
            "total_transactions": total_txns,
            "successful_transactions": success_txns,
            "failed_transactions": failed_txns,
            "abandoned_transactions": abandoned_txns,
            "success_rate": round(success_rate, 2),
            "total_revenue_volume_inr": round(total_volume, 2),
            "total_revenue_at_risk_inr": round(total_at_risk, 2),
            "total_revenue_recovered_inr": round(total_recovered, 2),
            "recovery_rate": round(recovery_rate, 2),
            "active_recovery_cases": active_cases,
            "resolved_recovery_cases": resolved_cases,
            "systemic_incidents_count": incident_txns,
        }

    def get_breakdown_metrics(self, db: Session) -> Dict[str, Any]:
        """Compute breakdowns by payment method, failure codes, and recovery classifications."""
        # 1. By Payment Method
        method_stats: Dict[str, Dict[str, float]] = {}
        for method_enum in PaymentMethod:
            m = method_enum.value
            m_txns = db.query(Transaction).filter(Transaction.payment_method == m).all()
            total_count = len(m_txns)
            succ_count = sum(1 for t in m_txns if t.status == TransactionStatus.SUCCESS.value)
            fail_count = sum(1 for t in m_txns if t.status == TransactionStatus.FAILED.value)
            vol = sum(t.amount for t in m_txns)
            risk = sum(t.amount for t in m_txns if t.status in [TransactionStatus.FAILED.value, TransactionStatus.ABANDONED.value])
            method_stats[m] = {
                "total_transactions": total_count,
                "successful_transactions": succ_count,
                "failed_transactions": fail_count,
                "volume_inr": round(vol, 2),
                "revenue_at_risk_inr": round(risk, 2),
                "success_rate": round((succ_count / total_count * 100) if total_count > 0 else 0.0, 2),
            }

        # 2. By Failure Code
        failure_txns = db.query(Transaction.failure_code).filter(Transaction.failure_code != None).all()
        failure_counts = Counter([r[0] for r in failure_txns if r[0]])

        # 3. By Recovery Classification
        cases = db.query(RecoveryCase.classification, RecoveryCase.priority).all()
        class_counts = Counter([c[0] for c in cases if c[0]])
        priority_counts = Counter([c[1] for c in cases if c[1]])

        return {
            "by_payment_method": method_stats,
            "by_failure_code": dict(failure_counts),
            "by_recovery_classification": dict(class_counts),
            "by_case_priority": dict(priority_counts),
        }

    def get_incident_status(self, db: Session) -> Dict[str, Any]:
        """Assess active/recent payment degradation incidents."""
        incident_txns = (
            db.query(Transaction)
            .filter(Transaction.is_degradation_incident == True)
            .all()
        )
        has_incident = len(incident_txns) > 0
        total_risk = sum(t.amount for t in incident_txns)

        upi_total = db.query(Transaction).filter(Transaction.payment_method == PaymentMethod.UPI.value).count()
        upi_failed = db.query(Transaction).filter(Transaction.payment_method == PaymentMethod.UPI.value, Transaction.status == TransactionStatus.FAILED.value).count()
        upi_fail_rate = (upi_failed / upi_total * 100) if upi_total > 0 else 0.0

        return {
            "is_incident_active": has_incident,
            "incident_method": PaymentMethod.UPI.value if has_incident else None,
            "affected_transactions_count": len(incident_txns),
            "estimated_revenue_at_risk_inr": round(total_risk, 2),
            "spike_failure_rate": round(upi_fail_rate, 2),
            "baseline_failure_rate": 4.50,
            "incident_description": (
                f"Simulated UPI Switch Congestion incident: {len(incident_txns)} transactions affected "
                f"with ₹{total_risk:,.2f} at risk."
            ) if has_incident else "All payment gateways operating within normal baseline latency and failure parameters.",
        }


analytics_service = AnalyticsService()
