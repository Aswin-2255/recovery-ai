"""Core 6-Stage Revenue Recovery Lifecycle Service.

Lifecycle: [Detect] ➔ [Diagnose] ➔ [Decide] ➔ [Execute] ➔ [Verify] ➔ [Measure]

Coordinates detection of revenue-at-risk, root cause analysis, agent decision strategy,
policy guardrail enforcement, action simulation/execution, verification, and ledger accounting.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy.orm import Session

from app.models import (
    Merchant,
    Customer,
    Transaction,
    RecoveryCase,
    RecoveryAction,
    AgentDecision,
    AuditLog,
    PaymentMethod,
    TransactionStatus,
    FailureCategory,
    CasePriority,
    RecoveryClassification,
    RecoveryCaseStatus,
    ActionType,
    ActionStatus,
    AgentDecisionType,
    ActorType,
)
from app.services.diagnosis_service import diagnosis_service
from app.services.policy_engine import policy_engine
from app.services.simulator_service import recovery_simulator
from app.services.synthetic_generator import FAILURE_CATALOG

logger = logging.getLogger(__name__)


class RecoveryLifecycleService:
    """Orchestrates the 6-stage revenue recovery workflow with full audit logging."""

    TERMINAL_CASE_STATUSES = {
        RecoveryCaseStatus.RECOVERED.value,
        RecoveryCaseStatus.STOPPED.value,
    }

    def _latest_action_for_case(self, db: Session, case_id: str) -> Optional[RecoveryAction]:
        """Return the action that completed a terminal case without creating a replay."""
        return (
            db.query(RecoveryAction)
            .filter_by(recovery_case_id=case_id)
            .order_by(RecoveryAction.created_at.desc())
            .first()
        )

    # -------------------------------------------------------------------------
    # STAGE 1: DETECT
    # -------------------------------------------------------------------------
    def detect_revenue_at_risk(
        self,
        db: Session,
        transaction: Transaction,
    ) -> RecoveryCase:
        """
        Stage 1 [Detect]: Evaluate whether a payment failure represents revenue-at-risk.
        Creates or retrieves the associated RecoveryCase and records an immutable audit log.
        """
        # If case already exists, return it
        existing_case = (
            db.query(RecoveryCase)
            .filter(RecoveryCase.transaction_id == transaction.id)
            .first()
        )
        if existing_case:
            return existing_case

        # Calculate initial recovery probability baseline
        f_def = FAILURE_CATALOG.get(transaction.failure_code or "")
        customer = db.query(Customer).filter_by(id=transaction.customer_id).first()
        trust = customer.trust_score if customer else 1.0

        if f_def:
            base_prob = f_def.base_recoverability * (0.6 + 0.4 * trust) - (0.08 * transaction.retry_count)
            recovery_prob = round(max(0.02, min(0.98, base_prob)), 3)
            classification = f_def.classification.value
        else:
            recovery_prob = 0.50
            classification = RecoveryClassification.UNCERTAIN.value

        # Priority calculation
        expected_value = transaction.amount * recovery_prob
        if expected_value >= 15000 or (transaction.amount >= 30000 and recovery_prob >= 0.5):
            priority = CasePriority.CRITICAL.value
        elif expected_value >= 4000:
            priority = CasePriority.HIGH.value
        elif expected_value >= 1000:
            priority = CasePriority.MEDIUM.value
        else:
            priority = CasePriority.LOW.value

        case = RecoveryCase(
            id=f"case_{uuid.uuid4().hex[:12]}",
            transaction_id=transaction.id,
            merchant_id=transaction.merchant_id,
            revenue_at_risk=transaction.amount,
            recovery_probability=recovery_prob,
            priority=priority,
            classification=classification,
            status=RecoveryCaseStatus.OPEN.value,
            reason=transaction.failure_reason,
            root_cause_summary=f"Payment failure code {transaction.failure_code} via {transaction.payment_method.upper()}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(case)
        db.flush()

        # Audit Log: RISK_DETECTED
        audit = AuditLog(
            id=f"aud_{uuid.uuid4().hex[:12]}",
            entity_type="recovery_case",
            entity_id=case.id,
            actor=ActorType.SYSTEM.value,
            action="RISK_DETECTED",
            what_happened=f"Revenue at risk of ₹{transaction.amount:,.2f} detected on transaction {transaction.id}",
            what_caused_it=f"Failure: {transaction.failure_code} ({transaction.failure_reason})",
            action_taken="Ingested payment failure and initialized recovery case",
            result=f"Classification: {classification.upper()}, Priority: {priority.upper()}, Probability: {recovery_prob:.2f}",
            metadata_json=json.dumps({
                "amount": transaction.amount,
                "payment_method": transaction.payment_method,
                "failure_code": transaction.failure_code,
                "probability": recovery_prob,
            }),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.commit()
        db.refresh(case)
        return case

    # -------------------------------------------------------------------------
    # STAGE 2: DIAGNOSE
    # -------------------------------------------------------------------------
    def diagnose_case(self, db: Session, case_id: str) -> RecoveryCase:
        """
        Stage 2 [Diagnose]: Root cause analysis on the payment failure.
        """
        clean_id = case_id.strip()
        case = db.query(RecoveryCase).filter(
            (RecoveryCase.id == clean_id) | (RecoveryCase.transaction_id == clean_id)
        ).first()
        if not case:
            raise ValueError(f"RecoveryCase '{case_id}' not found.")

        txn = db.query(Transaction).filter_by(id=case.transaction_id).first()
        if not txn:
            raise ValueError(f"Transaction '{case.transaction_id}' not found.")

        diag_result = diagnosis_service.diagnose_case(db=db, case_id=case_id, txn=txn)

        case.root_cause_summary = diag_result.root_cause_summary
        if case.status == RecoveryCaseStatus.OPEN.value:
            case.status = RecoveryCaseStatus.DIAGNOSED.value
        case.updated_at = datetime.now(timezone.utc)

        # Audit Log: DIAGNOSIS_COMPLETED
        audit = AuditLog(
            id=f"aud_{uuid.uuid4().hex[:12]}",
            entity_type="recovery_case",
            entity_id=case.id,
            actor=ActorType.SYSTEM.value,
            action="DIAGNOSIS_COMPLETED",
            what_happened=f"Root cause analysis completed for case {case.id}",
            what_caused_it=diag_result.root_cause_summary,
            action_taken="Diagnosed payment failure mechanics and degradation state",
            result=f"Is Transient: {diag_result.is_transient}, Systemic Incident: {diag_result.systemic_degradation_detected}",
            metadata_json=json.dumps(diag_result.detailed_metrics),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.commit()
        db.refresh(case)
        return case

    # -------------------------------------------------------------------------
    # STAGE 3: DECIDE
    # -------------------------------------------------------------------------
    def decide_recovery_strategy(self, db: Session, case_id: str) -> AgentDecision:
        """
        Stage 3 [Decide]: Select the optimal recovery intervention strategy.
        """
        clean_id = case_id.strip()
        case = db.query(RecoveryCase).filter(
            (RecoveryCase.id == clean_id) | (RecoveryCase.transaction_id == clean_id)
        ).first()
        if not case:
            raise ValueError(f"RecoveryCase '{case_id}' not found.")

        txn = db.query(Transaction).filter_by(id=case.transaction_id).first()
        customer = db.query(Customer).filter_by(id=txn.customer_id).first()
        trust = customer.trust_score if customer else 1.0

        f_code = txn.failure_code or ""
        f_cat = txn.failure_category
        method = txn.payment_method

        # Deterministic strategy selection
        if txn.retry_count >= txn.max_retries_allowed:
            rec_action = ActionType.MANUAL_ESCALATION.value
            decision_type = AgentDecisionType.ESCALATE.value
            reasoning = f"Maximum retries ({txn.max_retries_allowed}) exceeded. Recommending manual merchant escalation."
            confidence = 0.95
        elif f_code in ["INVALID_CARD_NUMBER", "EXPIRED_CARD"]:
            rec_action = ActionType.FALLBACK_METHOD.value
            decision_type = AgentDecisionType.RECOMMEND_ACTION.value
            reasoning = f"Card validation failed with {f_code}. Recommending fallback payment method switch (e.g. UPI / Netbanking)."
            confidence = 0.88
        elif f_code in ["ACCOUNT_BLOCKED", "DO_NOT_HONOR"]:
            rec_action = ActionType.PAYMENT_LINK.value
            decision_type = AgentDecisionType.RECOMMEND_ACTION.value
            reasoning = f"Bank hard decline ({f_code}). Direct retry is invalid; recommending targeted payment link to alternative account."
            confidence = 0.82
        elif f_cat == FailureCategory.ABANDONMENT.value or f_code in ["CHECKOUT_DROPOFF_AT_PAYMENT_SELECT", "USER_CANCELLED"]:
            rec_action = ActionType.CUSTOMER_REMINDER.value
            decision_type = AgentDecisionType.RECOMMEND_ACTION.value
            reasoning = "Checkout abandonment detected without debit attempt. Recommending omnichannel customer cart reminder with 1-click checkout."
            confidence = 0.85
        elif f_code in ["MANDATE_INSUFFICIENT_FUNDS", "RECURRING_AUTH_FAILED"]:
            rec_action = ActionType.PAYMENT_LINK.value
            decision_type = AgentDecisionType.RECOMMEND_ACTION.value
            reasoning = f"Subscription recurring charge failed ({f_code}). Recommending direct invoice payment link."
            confidence = 0.84
        elif f_cat == FailureCategory.TEMPORARY.value or f_code in ["BAD_REQUEST_GATEWAY_TIMEOUT", "NETWORK_ERROR", "BANK_SYSTEM_BUSY", "OTP_TIMEOUT"]:
            rec_action = ActionType.SMART_RETRY.value
            decision_type = AgentDecisionType.RECOMMEND_ACTION.value
            reasoning = f"Transient gateway latency/timeout on {method.upper()}. Recommending automated smart retry with exponential backoff."
            confidence = round(min(0.95, 0.75 + (0.20 * trust)), 2)
        else:
            rec_action = ActionType.PAYMENT_LINK.value
            decision_type = AgentDecisionType.RECOMMEND_ACTION.value
            reasoning = "Generic payment failure. Recommending dynamic payment link dispatch."
            confidence = 0.75

        # Check preliminary policy feasibility
        merchant = db.query(Merchant).filter_by(id=txn.merchant_id).first()
        policy_eval = policy_engine.evaluate(
            action_type=rec_action,
            confidence=confidence,
            retry_count=txn.retry_count,
            amount_inr=txn.amount,
            failure_code=f_code,
            failure_category=f_cat,
            customer_trust_score=trust,
            merchant_auto_enabled=merchant.auto_recovery_enabled if merchant else True,
        )

        decision = AgentDecision(
            id=f"dec_{uuid.uuid4().hex[:12]}",
            recovery_case_id=case.id,
            decision=decision_type,
            recommended_action=rec_action,
            reasoning_summary=reasoning,
            confidence=confidence,
            policy_approved=policy_eval.approved,
            policy_rejection_reason=policy_eval.rejection_reason,
            execution_payload_json=json.dumps({
                "proposed_action": rec_action,
                "confidence": confidence,
                "rules_checked": policy_eval.rules_checked,
            }),
            created_at=datetime.now(timezone.utc),
        )
        db.add(decision)
        db.flush()

        # Audit Log: DECISION_RECORDED
        audit = AuditLog(
            id=f"aud_{uuid.uuid4().hex[:12]}",
            entity_type="agent_decision",
            entity_id=decision.id,
            actor=ActorType.AI_AGENT.value,
            action="DECISION_RECORDED",
            what_happened=f"AI Agent formulated recovery strategy '{rec_action}' (confidence: {confidence:.2f})",
            what_caused_it=reasoning,
            action_taken="Submitted recommended intervention for Policy Engine evaluation",
            result=f"Policy Pre-Check: {'APPROVED' if policy_eval.approved else 'REJECTED: ' + str(policy_eval.rejection_reason)}",
            metadata_json=decision.execution_payload_json,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.commit()
        db.refresh(decision)
        return decision

    # -------------------------------------------------------------------------
    # STAGE 4: EXECUTE
    # -------------------------------------------------------------------------
    def execute_recovery_action(
        self,
        db: Session,
        case_id: str,
        action_type: str,
        force_mode: str = "simulator",
    ) -> RecoveryAction:
        """
        Stage 4 [Execute]: Validates through Policy Engine and executes bounded action.
        """
        clean_id = case_id.strip()
        case = db.query(RecoveryCase).filter(
            (RecoveryCase.id == clean_id) | (RecoveryCase.transaction_id == clean_id)
        ).first()
        if not case:
            raise ValueError(f"RecoveryCase '{case_id}' not found.")

        # A recovered or policy-stopped case is immutable from an execution
        # perspective. Return its original action so callers receive a stable,
        # idempotent result without creating another action or audit event.
        if case.status in self.TERMINAL_CASE_STATUSES:
            existing_action = self._latest_action_for_case(db=db, case_id=case.id)
            if existing_action:
                return existing_action
            raise ValueError(f"RecoveryCase '{case_id}' is terminal without a recovery action.")

        txn = db.query(Transaction).filter_by(id=case.transaction_id).first()
        merchant = db.query(Merchant).filter_by(id=case.merchant_id).first()
        customer = db.query(Customer).filter_by(id=txn.customer_id).first()
        trust = customer.trust_score if customer else 1.0

        # Run Policy Engine evaluation
        decision_record = (
            db.query(AgentDecision)
            .filter_by(recovery_case_id=case.id)
            .order_by(AgentDecision.created_at.desc())
            .first()
        )
        confidence = decision_record.confidence if decision_record else 0.80

        policy_decision = policy_engine.evaluate(
            action_type=action_type,
            confidence=confidence,
            retry_count=txn.retry_count,
            amount_inr=txn.amount,
            failure_code=txn.failure_code,
            failure_category=txn.failure_category,
            customer_trust_score=trust,
            merchant_auto_enabled=merchant.auto_recovery_enabled if merchant else True,
        )

        if not policy_decision.approved:
            # Policy Engine VETO
            action = RecoveryAction(
                id=f"act_{uuid.uuid4().hex[:12]}",
                recovery_case_id=case.id,
                action_type=action_type,
                status=ActionStatus.BLOCKED_BY_POLICY.value,
                amount_recovered=0.0,
                result=f"Blocked by Policy Engine: {policy_decision.rejection_reason}",
                execution_details_json=json.dumps({
                    "approved": False,
                    "rejection_reason": policy_decision.rejection_reason,
                    "suggested_alternative": policy_decision.suggested_alternative,
                    "rules_checked": policy_decision.rules_checked,
                }),
                executed_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )
            db.add(action)
            case.status = RecoveryCaseStatus.STOPPED.value
            case.updated_at = datetime.now(timezone.utc)

            audit = AuditLog(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="recovery_action",
                entity_id=action.id,
                actor=ActorType.POLICY_ENGINE.value,
                action="ACTION_BLOCKED_BY_POLICY",
                what_happened=f"Policy Engine vetoed '{action_type}' for case {case.id}",
                what_caused_it=policy_decision.rejection_reason,
                action_taken="Halted autonomous execution; suggested alternative: " + str(policy_decision.suggested_alternative),
                result="Action marked BLOCKED_BY_POLICY, case STOPPED",
                metadata_json=action.execution_details_json,
                timestamp=datetime.now(timezone.utc),
            )
            db.add(audit)
            db.commit()
            db.refresh(action)
            return action

        # Policy Approved -> Execute via Simulator or Razorpay Test Mode
        case.status = RecoveryCaseStatus.IN_PROGRESS.value
        db.flush()

        sim_result = recovery_simulator.execute_action(
            action_type=action_type,
            amount_inr=txn.amount,
            failure_code=txn.failure_code,
            failure_category=txn.failure_category,
            customer_trust=trust,
            retry_attempt=txn.retry_count + 1,
        )

        txn.retry_count += 1
        action_status = ActionStatus.COMPLETED.value if sim_result.success else ActionStatus.FAILED.value

        action = RecoveryAction(
            id=f"act_{uuid.uuid4().hex[:12]}",
            recovery_case_id=case.id,
            action_type=action_type,
            status=action_status,
            amount_recovered=sim_result.amount_recovered,
            result=sim_result.message,
            execution_details_json=json.dumps({
                "mode": force_mode,
                "gateway_reference": sim_result.gateway_reference,
                "failure_reason": sim_result.failure_reason,
                "retry_attempt": txn.retry_count,
            }),
            executed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(action)

        # Audit Log: ACTION_EXECUTED
        audit = AuditLog(
            id=f"aud_{uuid.uuid4().hex[:12]}",
            entity_type="recovery_action",
            entity_id=action.id,
            actor=ActorType.SIMULATOR.value if force_mode == "simulator" else ActorType.POLICY_ENGINE.value,
            action="ACTION_EXECUTED",
            what_happened=f"Executed recovery intervention '{action_type}' (attempt #{txn.retry_count})",
            what_caused_it=f"Policy approved action; executed via {force_mode}",
            action_taken=f"Sent intervention request to gateway/customer with amount ₹{txn.amount:,.2f}",
            result=sim_result.message,
            metadata_json=action.execution_details_json,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.commit()
        db.refresh(action)

        # Proceed to Verification and Measurement
        self.verify_and_measure(db=db, case=case, action=action, txn=txn, sim_result=sim_result)
        return action

    # -------------------------------------------------------------------------
    # STAGES 5 & 6: VERIFY & MEASURE
    # -------------------------------------------------------------------------
    def verify_and_measure(
        self,
        db: Session,
        case: RecoveryCase,
        action: RecoveryAction,
        txn: Transaction,
        sim_result: Any,
    ):
        """
        Stage 5 [Verify] & Stage 6 [Measure]: Validates final ledger state and records audit impact.
        """
        now = datetime.now(timezone.utc)

        if action.status == ActionStatus.COMPLETED.value and action.amount_recovered > 0:
            # Verified recovery
            txn.status = TransactionStatus.SUCCESS.value
            txn.gateway_reference = sim_result.gateway_reference
            case.status = RecoveryCaseStatus.RECOVERED.value
            case.revenue_at_risk = 0.0

            # Update customer spend and success count
            customer = db.query(Customer).filter_by(id=txn.customer_id).first()
            if customer:
                customer.historical_success_count += 1
                customer.total_spend_inr += action.amount_recovered

            audit = AuditLog(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="recovery_case",
                entity_id=case.id,
                actor=ActorType.SYSTEM.value,
                action="IMPACT_MEASURED",
                what_happened=f"Successfully recovered ₹{action.amount_recovered:,.2f} on transaction {txn.id}",
                what_caused_it=f"Verified recovery action '{action.action_type}' execution",
                action_taken="Updated transaction ledger to SUCCESS, reconciled recovered funds",
                result=f"Measured money recovered: ₹{action.amount_recovered:,.2f}, case status marked RECOVERED",
                metadata_json=json.dumps({
                    "amount_recovered": action.amount_recovered,
                    "action_id": action.id,
                    "gateway_ref": sim_result.gateway_reference,
                }),
                timestamp=now,
            )
            db.add(audit)

        elif action.status == ActionStatus.BLOCKED_BY_POLICY.value:
            case.status = RecoveryCaseStatus.STOPPED.value
        else:
            # Action failed
            if txn.retry_count >= txn.max_retries_allowed:
                case.status = RecoveryCaseStatus.UNRECOVERABLE.value
            else:
                case.status = RecoveryCaseStatus.OPEN.value

            audit = AuditLog(
                id=f"aud_{uuid.uuid4().hex[:12]}",
                entity_type="recovery_case",
                entity_id=case.id,
                actor=ActorType.SYSTEM.value,
                action="RECOVERY_ATTEMPT_FAILED",
                what_happened=f"Recovery attempt '{action.action_type}' failed on transaction {txn.id}",
                what_caused_it=action.result or "Gateway or customer declined attempt",
                action_taken=f"Updated retry count to {txn.retry_count}/{txn.max_retries_allowed}",
                result=f"Case status updated to {case.status.upper()}",
                metadata_json=json.dumps({"retry_count": txn.retry_count}),
                timestamp=now,
            )
            db.add(audit)

        case.updated_at = now
        db.commit()

    # -------------------------------------------------------------------------
    # FULL AUTONOMOUS 6-STAGE WORKFLOW
    # -------------------------------------------------------------------------
    def run_full_lifecycle(self, db: Session, case_id: str) -> Dict[str, Any]:
        """
        Runs the complete 6-stage lifecycle on a case end-to-end:
        Detect -> Diagnose -> Decide -> Execute -> Verify -> Measure
        """
        clean_id = case_id.strip()
        case = db.query(RecoveryCase).filter(
            (RecoveryCase.id == clean_id) | (RecoveryCase.transaction_id == clean_id)
        ).first()
        if not case:
            raise ValueError(f"RecoveryCase '{case_id}' not found.")

        # Replaying the full workflow after its terminal action must be a
        # read-only operation. Reuse the persisted result rather than running
        # diagnosis, decision, execution, or audit logging a second time.
        if case.status in self.TERMINAL_CASE_STATUSES:
            action = self._latest_action_for_case(db=db, case_id=case.id)
            if not action:
                raise ValueError(f"RecoveryCase '{case_id}' is terminal without a recovery action.")
            decision = (
                db.query(AgentDecision)
                .filter_by(recovery_case_id=case.id)
                .order_by(AgentDecision.created_at.desc())
                .first()
            )
            txn = db.query(Transaction).filter_by(id=case.transaction_id).first()
            audit_logs = (
                db.query(AuditLog)
                .filter_by(entity_id=case.id)
                .order_by(AuditLog.timestamp.asc())
                .all()
            )
            return {
                "case_id": case.id,
                "transaction_id": case.transaction_id,
                "lifecycle_stage_completed": "6_MEASURE",
                "stages_executed": ["1_DETECT", "2_DIAGNOSE", "3_DECIDE", "4_EXECUTE", "5_VERIFY", "6_MEASURE"],
                "root_cause": case.root_cause_summary or "",
                "decision": decision.decision if decision else "stop",
                "recommended_action": decision.recommended_action if decision else action.action_type,
                "policy_approved": decision.policy_approved if decision else action.status != ActionStatus.BLOCKED_BY_POLICY.value,
                "action_status": action.status,
                "amount_at_risk": txn.amount if txn else 0.0,
                "amount_recovered": action.amount_recovered,
                "case_final_status": case.status,
                "audit_log_ids": [audit.id for audit in audit_logs],
                "timestamp": case.updated_at,
            }

        stages_executed = ["1_DETECT"]

        # Stage 2: Diagnose
        self.diagnose_case(db=db, case_id=case_id)
        stages_executed.append("2_DIAGNOSE")

        # Stage 3: Decide
        decision = self.decide_recovery_strategy(db=db, case_id=case_id)
        stages_executed.append("3_DECIDE")

        # Stage 4 & 5 & 6: Execute, Verify, Measure
        action = self.execute_recovery_action(
            db=db,
            case_id=case_id,
            action_type=decision.recommended_action or ActionType.SMART_RETRY.value,
        )
        stages_executed.extend(["4_EXECUTE", "5_VERIFY", "6_MEASURE"])

        db.refresh(case)
        txn = db.query(Transaction).filter_by(id=case.transaction_id).first()

        # Gather audit logs
        audit_logs = (
            db.query(AuditLog)
            .filter_by(entity_id=case.id)
            .order_by(AuditLog.timestamp.asc())
            .all()
        )

        return {
            "case_id": case.id,
            "transaction_id": case.transaction_id,
            "lifecycle_stage_completed": "6_MEASURE",
            "stages_executed": stages_executed,
            "root_cause": case.root_cause_summary or "",
            "decision": decision.decision,
            "recommended_action": decision.recommended_action,
            "policy_approved": decision.policy_approved,
            "action_status": action.status,
            "amount_at_risk": txn.amount if txn else 0.0,
            "amount_recovered": action.amount_recovered,
            "case_final_status": case.status,
            "audit_log_ids": [a.id for a in audit_logs],
            "timestamp": datetime.now(timezone.utc),
        }


recovery_lifecycle_service = RecoveryLifecycleService()
