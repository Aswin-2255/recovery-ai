"""Database Analytics and Metrics Computation Service.

Calculates exact financial metrics, recovery ratios, method performance,
and payment degradation statistics directly from database queries.
"""
from collections import Counter
import time
from typing import Dict, Any, List, Callable, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Merchant, Customer, Transaction, RecoveryCase, RecoveryAction, AuditLog
from app.models.enums import (
    TransactionStatus,
    RecoveryCaseStatus,
    PaymentMethod,
    RecoveryClassification,
    ActionType,
    ActionStatus,
)
from app.schemas.analytics import (
    BatchEvaluationRequest,
    BatchEvaluationResponse,
    CategoryBreakdownItem,
    ActionBreakdownItem,
)
from app.services.synthetic_generator import SyntheticPaymentGenerator
from app.services.recovery_lifecycle_service import recovery_lifecycle_service


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

    @staticmethod
    def _build_breakdown(
        evaluated_cases: List[RecoveryCase],
        txn_map: Dict[str, Transaction],
        evaluated_actions: List[RecoveryAction],
        key_extractor: Callable[[Transaction], str],
    ) -> Dict[str, CategoryBreakdownItem]:
        """Reusable aggregation helper for category and failure code breakdowns."""
        items: Dict[str, Dict[str, Any]] = {}
        case_map = {c.id: c for c in evaluated_cases}

        for case in evaluated_cases:
            txn = txn_map.get(case.transaction_id)
            key = key_extractor(txn) if txn else "unknown"
            if key not in items:
                items[key] = {
                    "total_evaluated": 0,
                    "revenue_at_risk": 0.0,
                    "recovered_count": 0,
                    "amount_recovered": 0.0,
                }
            items[key]["total_evaluated"] += 1
            items[key]["revenue_at_risk"] += txn.amount if txn else 0.0
            if case.status == RecoveryCaseStatus.RECOVERED.value:
                items[key]["recovered_count"] += 1

        for action in evaluated_actions:
            if action.status == ActionStatus.COMPLETED.value and action.amount_recovered > 0:
                case = case_map.get(action.recovery_case_id)
                if case:
                    txn = txn_map.get(case.transaction_id)
                    key = key_extractor(txn) if txn else "unknown"
                    if key in items:
                        items[key]["amount_recovered"] += action.amount_recovered

        return {
            key: CategoryBreakdownItem(
                category=key,
                total_evaluated=data["total_evaluated"],
                revenue_at_risk=round(data["revenue_at_risk"], 2),
                recovered_count=data["recovered_count"],
                amount_recovered=round(data["amount_recovered"], 2),
                recovery_rate=round(
                    (data["recovered_count"] / data["total_evaluated"] * 100) if data["total_evaluated"] > 0 else 0.0,
                    2,
                ),
                recovery_efficiency=round(
                    (data["amount_recovered"] / data["revenue_at_risk"] * 100) if data["revenue_at_risk"] > 0 else 0.0,
                    2,
                ),
            )
            for key, data in sorted(items.items())
        }

    def evaluate_batch(self, db: Session, request: BatchEvaluationRequest) -> BatchEvaluationResponse:
        """
        Process a reproducible batch of synthetic failed transactions through the
        existing 6-stage recovery lifecycle and produce measurable financial recovery metrics.
        """
        start_time = time.perf_counter()
        generator = SyntheticPaymentGenerator(seed=request.seed)

        # 1. Ensure merchant exists
        merchant = (
            db.query(Merchant).filter_by(id=request.merchant_id).first()
            if request.merchant_id
            else db.query(Merchant).first()
        )
        if not merchant:
            merchant = generator.generate_merchant()
            if request.merchant_id:
                merchant.id = request.merchant_id
            db.add(merchant)
            db.flush()

        # 2. Ensure customers exist
        customers = generator.generate_customers(merchant_id=str(merchant.id), count=60)
        for cust in customers:
            if not db.query(Customer).filter_by(id=cust.id).first():
                db.add(cust)
        db.flush()

        # 3. Generate dataset
        transactions, initial_cases, audit_logs = generator.generate_dataset(
            merchant=merchant,
            customers=customers,
            total_transactions=request.total_transactions,
            include_incident=request.include_incident,
        )

        # 4. Persist generated batch entities cleanly
        for txn in transactions:
            if not db.query(Transaction).filter_by(id=txn.id).first():
                db.add(txn)
        db.flush()

        for case in initial_cases:
            if not db.query(RecoveryCase).filter_by(id=case.id).first():
                db.add(case)
        db.flush()

        for audit in audit_logs:
            if not db.query(AuditLog).filter_by(id=audit.id).first():
                db.add(audit)
        db.commit()

        # 5. Process each case through the 6-stage recovery lifecycle
        batch_case_ids = [c.id for c in initial_cases]
        for case_id in batch_case_ids:
            recovery_lifecycle_service.run_full_lifecycle(db=db, case_id=case_id)

        # 6. Aggregate results for this evaluated batch
        batch_txn_ids = [t.id for t in transactions]
        evaluated_txns = db.query(Transaction).filter(Transaction.id.in_(batch_txn_ids)).all()
        evaluated_cases = db.query(RecoveryCase).filter(RecoveryCase.id.in_(batch_case_ids)).all()
        evaluated_actions = (
            db.query(RecoveryAction)
            .filter(RecoveryAction.recovery_case_id.in_(batch_case_ids))
            .all()
        )

        txn_map = {t.id: t for t in evaluated_txns}

        total_txns_count = len(evaluated_txns)
        total_volume = sum(t.amount for t in evaluated_txns)
        total_at_risk = sum(txn_map[c.transaction_id].amount for c in evaluated_cases if c.transaction_id in txn_map)

        recoverable_count = sum(1 for c in evaluated_cases if c.classification == RecoveryClassification.RECOVERABLE.value)
        recovered_count = sum(1 for c in evaluated_cases if c.status == RecoveryCaseStatus.RECOVERED.value)
        unrecoverable_count = sum(1 for c in evaluated_cases if c.status == RecoveryCaseStatus.UNRECOVERABLE.value)
        stopped_count = sum(1 for c in evaluated_cases if c.status == RecoveryCaseStatus.STOPPED.value)

        failed_attempts_count = sum(1 for a in evaluated_actions if a.status == ActionStatus.FAILED.value)
        total_recovered = sum(a.amount_recovered for a in evaluated_actions if a.status == ActionStatus.COMPLETED.value)

        total_cases_count = len(evaluated_cases)
        recovery_rate = (recovered_count / total_cases_count * 100) if total_cases_count > 0 else 0.0
        recovery_efficiency = (total_recovered / total_at_risk * 100) if total_at_risk > 0 else 0.0

        # Category and Failure Code Breakdowns via unified helper
        by_failure_category = self._build_breakdown(
            evaluated_cases, txn_map, evaluated_actions,
            lambda t: t.failure_category if t.failure_category else "unknown",
        )
        by_failure_code = self._build_breakdown(
            evaluated_cases, txn_map, evaluated_actions,
            lambda t: t.failure_code if t.failure_code else "UNKNOWN",
        )

        # Action Breakdown
        action_stats: Dict[str, Dict[str, Any]] = {
            act_type.value: {
                "attempt_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "blocked_by_policy_count": 0,
                "amount_recovered": 0.0,
            }
            for act_type in ActionType
        }

        for action in evaluated_actions:
            atype = action.action_type
            if atype not in action_stats:
                action_stats[atype] = {
                    "attempt_count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "blocked_by_policy_count": 0,
                    "amount_recovered": 0.0,
                }
            action_stats[atype]["attempt_count"] += 1
            if action.status == ActionStatus.COMPLETED.value:
                action_stats[atype]["success_count"] += 1
                action_stats[atype]["amount_recovered"] += action.amount_recovered
            elif action.status == ActionStatus.FAILED.value:
                action_stats[atype]["failed_count"] += 1
            elif action.status == ActionStatus.BLOCKED_BY_POLICY.value:
                action_stats[atype]["blocked_by_policy_count"] += 1

        by_recovery_action = {
            atype: ActionBreakdownItem(
                action_type=atype,
                attempt_count=data["attempt_count"],
                success_count=data["success_count"],
                failed_count=data["failed_count"],
                blocked_by_policy_count=data["blocked_by_policy_count"],
                amount_recovered=round(data["amount_recovered"], 2),
            )
            for atype, data in sorted(action_stats.items())
            if data["attempt_count"] > 0
        }

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return BatchEvaluationResponse(
            seed=request.seed,
            total_transactions_evaluated=total_txns_count,
            total_transaction_value=round(total_volume, 2),
            total_revenue_at_risk=round(total_at_risk, 2),
            recoverable_cases=recoverable_count,
            recovered_cases=recovered_count,
            unrecoverable_cases=unrecoverable_count,
            policy_stopped_cases=stopped_count,
            failed_recovery_attempts=failed_attempts_count,
            total_amount_recovered=round(total_recovered, 2),
            recovery_rate=round(recovery_rate, 2),
            recovery_efficiency=round(recovery_efficiency, 2),
            by_failure_category=by_failure_category,
            by_failure_code=by_failure_code,
            by_recovery_action=by_recovery_action,
            execution_time_ms=elapsed_ms,
        )


analytics_service = AnalyticsService()

