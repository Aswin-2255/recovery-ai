"""Deterministic recovery knowledge retrieval for payment-failure contexts.

This module is intentionally separate from the recovery lifecycle.  It provides
structured reference material for a future AI consumer without making decisions
or executing actions.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class RecoveryKnowledgeItem:
    """Structured, project-local guidance for one payment recovery scenario."""

    scenario: str
    failure_codes: Tuple[str, ...]
    description: str
    likely_root_cause: str
    recommended_recovery_actions: Tuple[str, ...]
    retry_guidance: str
    risk_considerations: str
    policy_considerations: str
    do_not_retry_conditions: str
    escalation_conditions: str
    applicable_payment_methods: Tuple[str, ...] = ()


RECOVERY_KNOWLEDGE_BASE: Tuple[RecoveryKnowledgeItem, ...] = (
    RecoveryKnowledgeItem(
        scenario="gateway_timeout",
        failure_codes=("BAD_REQUEST_GATEWAY_TIMEOUT",),
        description="A payment request timed out while a gateway or switch was processing it.",
        likely_root_cause="Transient gateway or payment-network latency; final payment state may need confirmation.",
        recommended_recovery_actions=("smart_retry", "status_check", "payment_link"),
        retry_guidance="Retry only after checking that no successful debit or capture was recorded; use bounded retry attempts.",
        risk_considerations="A timeout can leave the final payment state uncertain, creating duplicate-charge risk.",
        policy_considerations="Apply the existing retry-count, confidence, amount, and merchant auto-recovery guardrails.",
        do_not_retry_conditions="Do not retry when the payment is already captured, a duplicate debit is suspected, or retry limits are reached.",
        escalation_conditions="Escalate when the payment state cannot be reconciled or repeated timeouts indicate a wider incident.",
        applicable_payment_methods=("upi", "card", "netbanking"),
    ),
    RecoveryKnowledgeItem(
        scenario="bank_timeout_or_busy",
        failure_codes=("BANK_SYSTEM_BUSY",),
        description="The issuing bank or its switch reported temporary congestion or a timeout.",
        likely_root_cause="Temporary issuing-bank capacity or connectivity degradation.",
        recommended_recovery_actions=("smart_retry", "payment_link", "manual_escalation"),
        retry_guidance="Use delayed, bounded retry after a cooldown; prefer an alternate customer-facing option if the issue persists.",
        risk_considerations="Rapid repeated retries can worsen customer friction during a bank-side outage.",
        policy_considerations="Keep retries within configured limits and stop automated intervention when policy rejects it.",
        do_not_retry_conditions="Do not retry after the configured retry limit or when a confirmed bank decline replaces the temporary status.",
        escalation_conditions="Escalate when failures cluster for the same payment method or bank, suggesting systemic degradation.",
        applicable_payment_methods=("upi", "card", "netbanking"),
    ),
    RecoveryKnowledgeItem(
        scenario="insufficient_funds",
        failure_codes=("INSUFFICIENT_FUNDS", "MANDATE_INSUFFICIENT_FUNDS"),
        description="The debit could not be completed because the payer account lacked sufficient balance.",
        likely_root_cause="Insufficient available balance at the time of debit.",
        recommended_recovery_actions=("payment_link", "customer_reminder", "manual_escalation"),
        retry_guidance="Avoid immediate repeat debit; use a customer-facing reminder or payment link and retry only with a valid customer-triggered opportunity.",
        risk_considerations="Repeated automatic debit attempts can create poor customer experience and do not resolve a balance shortage.",
        policy_considerations="Respect retry limits and use customer-facing actions instead of assuming funds have changed.",
        do_not_retry_conditions="Do not immediately retry the same failed debit or continue after retry limits are reached.",
        escalation_conditions="Escalate recurring or high-value unpaid balances for merchant review.",
        applicable_payment_methods=("upi", "card", "netbanking"),
    ),
    RecoveryKnowledgeItem(
        scenario="authentication_failure",
        failure_codes=("OTP_TIMEOUT", "RECURRING_AUTH_FAILED"),
        description="Customer or recurring-payment authentication did not complete successfully.",
        likely_root_cause="Expired one-time password, incomplete authentication, or bank-side recurring authentication failure.",
        recommended_recovery_actions=("payment_link", "customer_reminder", "fallback_payment_method"),
        retry_guidance="Invite the customer to re-authenticate through a fresh flow rather than replaying a stale authentication attempt.",
        risk_considerations="Automatic retries cannot supply missing customer authentication and may cause repeated failed attempts.",
        policy_considerations="Treat customer authentication as required; retain the existing policy veto for inappropriate retries.",
        do_not_retry_conditions="Do not retry an expired or incomplete authentication flow without renewed customer interaction.",
        escalation_conditions="Escalate repeated authentication failures for a recurring payment or when customer support intervention is needed.",
        applicable_payment_methods=("card", "upi", "netbanking"),
    ),
    RecoveryKnowledgeItem(
        scenario="payment_pending",
        failure_codes=("PAYMENT_PENDING", "PENDING"),
        description="The payment outcome is pending and has not reached a final success or failure state.",
        likely_root_cause="Asynchronous processing or delayed confirmation from the payment network.",
        recommended_recovery_actions=("status_check", "manual_escalation"),
        retry_guidance="Wait for a final status and reconcile it before proposing another payment attempt.",
        risk_considerations="Retrying a pending payment can cause duplicate collection if the original payment later succeeds.",
        policy_considerations="No automatic retry should bypass final-state verification.",
        do_not_retry_conditions="Do not retry while the original payment remains pending or its final status is unknown.",
        escalation_conditions="Escalate long-running pending payments or reconciliation mismatches for manual review.",
        applicable_payment_methods=("upi", "card", "netbanking", "wallet", "emi"),
    ),
    RecoveryKnowledgeItem(
        scenario="network_failure",
        failure_codes=("NETWORK_ERROR",),
        description="A transient network connection failed during payment processing.",
        likely_root_cause="Temporary connectivity interruption between payment components.",
        recommended_recovery_actions=("smart_retry", "status_check", "payment_link"),
        retry_guidance="Confirm the original payment state, then use a bounded delayed retry for transient connectivity failures.",
        risk_considerations="Network errors may obscure whether the original request reached the payment processor.",
        policy_considerations="Use existing confidence, retry, and merchant settings before automatic recovery.",
        do_not_retry_conditions="Do not retry if a capture is confirmed, a duplicate transaction is suspected, or limits are exhausted.",
        escalation_conditions="Escalate repeated failures across a payment method or merchant integration path.",
        applicable_payment_methods=("upi", "card", "netbanking", "wallet"),
    ),
    RecoveryKnowledgeItem(
        scenario="duplicate_transaction",
        failure_codes=("DUPLICATE_TRANSACTION", "DUPLICATE_PAYMENT"),
        description="A potential duplicate transaction or duplicate collection attempt was detected.",
        likely_root_cause="A customer retry, network ambiguity, or repeated submission may have created overlapping payment attempts.",
        recommended_recovery_actions=("status_check", "manual_escalation"),
        retry_guidance="Reconcile the original payment before any new collection attempt.",
        risk_considerations="Additional automatic retries can duplicate a debit or customer charge.",
        policy_considerations="Treat duplicate-risk cases as a stop condition for automatic collection until reconciled.",
        do_not_retry_conditions="Do not retry while any related transaction might still be captured or pending.",
        escalation_conditions="Always escalate unresolved duplicate-charge risk for manual reconciliation.",
        applicable_payment_methods=("upi", "card", "netbanking", "wallet", "emi"),
    ),
    RecoveryKnowledgeItem(
        scenario="checkout_abandonment",
        failure_codes=("CHECKOUT_DROPOFF_AT_PAYMENT_SELECT", "USER_CANCELLED"),
        description="The customer left checkout before completing payment.",
        likely_root_cause="Customer friction, indecision, or an abandoned checkout flow rather than a completed debit failure.",
        recommended_recovery_actions=("customer_reminder", "payment_link", "fallback_payment_method"),
        retry_guidance="Do not perform a backend payment retry; offer a customer-initiated return path instead.",
        risk_considerations="Backend retries are inappropriate when no completed payment attempt exists.",
        policy_considerations="Existing policy forbids automated backend retry for abandonment without customer engagement.",
        do_not_retry_conditions="Do not use smart retry for checkout abandonment or explicit user cancellation.",
        escalation_conditions="Escalate only when repeated abandonment indicates a checkout usability or payment-method issue.",
        applicable_payment_methods=("upi", "card", "netbanking", "wallet", "emi"),
    ),
    RecoveryKnowledgeItem(
        scenario="temporary_gateway_degradation",
        failure_codes=("SYSTEMIC_GATEWAY_DEGRADATION",),
        description="A cluster of temporary payment failures indicates a possible gateway or payment-network degradation incident.",
        likely_root_cause="Shared upstream gateway, switch, or bank-side availability degradation.",
        recommended_recovery_actions=("status_check", "manual_escalation", "payment_link"),
        retry_guidance="Pause aggressive retries and wait for recovery signals; use a bounded retry only after the incident subsides.",
        risk_considerations="Retry storms can increase load and produce duplicate or confusing customer payment attempts.",
        policy_considerations="Existing policy limits still apply; incident handling must not bypass them.",
        do_not_retry_conditions="Do not fan out automated retries during an active systemic degradation signal.",
        escalation_conditions="Escalate when failure-rate monitoring identifies a payment-method or gateway-wide incident.",
        applicable_payment_methods=("upi", "card", "netbanking"),
    ),
    RecoveryKnowledgeItem(
        scenario="unknown_failure",
        failure_codes=(),
        description="No project-local knowledge entry matches the supplied failure context.",
        likely_root_cause="Unknown; the available context is insufficient for a specific recovery recommendation.",
        recommended_recovery_actions=("status_check", "manual_escalation"),
        retry_guidance="Do not assume a retry is safe until the original payment state and failure reason are known.",
        risk_considerations="An unsupported failure can hide a completed payment, terminal decline, or customer-authentication requirement.",
        policy_considerations="Continue to enforce the existing Policy Engine before any action.",
        do_not_retry_conditions="Do not automatically retry unknown failures without reconciliation.",
        escalation_conditions="Escalate for diagnosis when the failure cannot be classified from available transaction context.",
    ),
)


class RecoveryKnowledgeService:
    """Ranks the local knowledge base using deterministic metadata and keywords."""

    def retrieve(
        self,
        failure_code: Optional[str] = None,
        payment_method: Optional[str] = None,
        amount: Optional[float] = None,
        retry_count: Optional[int] = None,
        diagnosis: Optional[str] = None,
        limit: int = 3,
    ) -> List[RecoveryKnowledgeItem]:
        """Return relevant guidance without making a recovery decision or changing state."""
        if limit < 1:
            return []

        normalized_code = (failure_code or "").strip().upper()
        normalized_method = (payment_method or "").strip().lower()
        query_tokens = set((diagnosis or "").lower().replace("_", " ").split())
        scored_items = []

        known_failure_codes = {
            code
            for item in RECOVERY_KNOWLEDGE_BASE
            if item.scenario != "unknown_failure"
            for code in item.failure_codes
        }
        if normalized_code and normalized_code not in known_failure_codes:
            return [self._unknown_item()]

        for index, item in enumerate(RECOVERY_KNOWLEDGE_BASE):
            if item.scenario == "unknown_failure":
                continue

            score = 0
            if normalized_code in item.failure_codes:
                score += 100
            if normalized_method and normalized_method in item.applicable_payment_methods:
                score += 5
            scenario_tokens = set((item.scenario + " " + item.description + " " + item.likely_root_cause).lower().replace("_", " ").split())
            score += len(query_tokens & scenario_tokens)
            if retry_count is not None and retry_count > 0 and "retry" in item.retry_guidance.lower():
                score += 1
            if amount is not None and amount > 0:
                score += 0  # Accepted context for future ranking without changing current guidance.

            if score:
                scored_items.append((score, index, item))

        if not scored_items:
            return [self._unknown_item()]

        scored_items.sort(key=lambda result: (-result[0], result[1]))
        return [item for _, _, item in scored_items[:limit]]

    @staticmethod
    def _unknown_item() -> RecoveryKnowledgeItem:
        return next(item for item in RECOVERY_KNOWLEDGE_BASE if item.scenario == "unknown_failure")


recovery_knowledge_service = RecoveryKnowledgeService()
