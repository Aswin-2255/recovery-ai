"""RecoverAI Independent Policy Guardrails Engine.

The Policy Engine has ABSOLUTE VETO AUTHORITY.
No AI agent, scheduler, or external trigger can bypass policy evaluation.
All recovery interventions must be validated against hard stopping rules
before execution.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

from app.core.config import settings
from app.models.enums import ActionType, FailureCategory

logger = logging.getLogger(__name__)


# Terminal failure codes where automated retries are permanently blocked
TERMINAL_FAILURE_CODES = {
    "INVALID_CARD_NUMBER",
    "ACCOUNT_BLOCKED",
    "EXPIRED_CARD",
    "DO_NOT_HONOR",
}

# Actions requiring customer intervention rather than automated gateway retry
CUSTOMER_FACING_ACTIONS = {
    ActionType.PAYMENT_LINK.value,
    ActionType.FALLBACK_METHOD.value,
    ActionType.CUSTOMER_REMINDER.value,
}


@dataclass
class PolicyDecision:
    approved: bool
    rejection_reason: Optional[str] = None
    suggested_alternative: Optional[str] = None
    rules_checked: List[str] = field(default_factory=list)
    confidence_passed: bool = True
    retry_limit_passed: bool = True
    amount_threshold_passed: bool = True
    action_applicability_passed: bool = True


class PolicyEngine:
    """Deterministic, rule-based safety guardrail validator."""

    def __init__(
        self,
        max_retries: int = settings.MAX_RECOVERY_RETRIES,
        min_confidence: float = settings.MIN_RECOVERY_CONFIDENCE,
        auto_recovery_threshold_inr: float = settings.AUTO_RECOVERY_THRESHOLD_INR,
    ):
        self.max_retries = max_retries
        self.min_confidence = min_confidence
        self.auto_recovery_threshold_inr = auto_recovery_threshold_inr

    def evaluate(
        self,
        action_type: str,
        confidence: float,
        retry_count: int,
        amount_inr: float,
        failure_code: Optional[str] = None,
        failure_category: Optional[str] = None,
        customer_trust_score: float = 1.0,
        merchant_auto_enabled: bool = True,
    ) -> PolicyDecision:
        """
        Evaluate a proposed recovery action against all safety rules.

        Returns PolicyDecision with approval status and specific rule outcomes.
        """
        rules_checked = []
        
        # Rule 1: Merchant Global Auto-Recovery Enabled
        rules_checked.append("RULE_1_MERCHANT_AUTO_RECOVERY_ENABLED")
        if not merchant_auto_enabled:
            return PolicyDecision(
                approved=False,
                rejection_reason="Merchant has disabled automated recovery interventions.",
                suggested_alternative=ActionType.MANUAL_ESCALATION.value,
                rules_checked=rules_checked,
                action_applicability_passed=False,
            )

        # Rule 2: Max Retries Stopping Rule
        rules_checked.append("RULE_2_MAX_RETRY_LIMIT")
        retry_limit_passed = retry_count < self.max_retries
        if not retry_limit_passed:
            return PolicyDecision(
                approved=False,
                rejection_reason=f"Max retry limit ({self.max_retries}) reached. Transaction has already been retried {retry_count} times.",
                suggested_alternative=ActionType.MANUAL_ESCALATION.value if amount_inr >= 10000 else ActionType.PAYMENT_LINK.value,
                rules_checked=rules_checked,
                retry_limit_passed=False,
            )

        # Rule 3: Terminal Failure Code Guardrail (Anti-spam / Anti-fraud)
        rules_checked.append("RULE_3_TERMINAL_FAILURE_CHECK")
        if failure_code in TERMINAL_FAILURE_CODES and action_type == ActionType.SMART_RETRY.value:
            alternative = ActionType.FALLBACK_METHOD.value if failure_code in ["INVALID_CARD_NUMBER", "EXPIRED_CARD"] else ActionType.PAYMENT_LINK.value
            return PolicyDecision(
                approved=False,
                rejection_reason=f"Smart retry is forbidden on terminal failure code '{failure_code}'. Requires customer intervention.",
                suggested_alternative=alternative,
                rules_checked=rules_checked,
                action_applicability_passed=False,
            )

        # Rule 4: High Value Threshold Guardrail (Merchant Safeguard)
        rules_checked.append("RULE_4_HIGH_VALUE_THRESHOLD")
        amount_threshold_passed = amount_inr <= self.auto_recovery_threshold_inr
        if not amount_threshold_passed and action_type == ActionType.SMART_RETRY.value:
            return PolicyDecision(
                approved=False,
                rejection_reason=f"Transaction amount ₹{amount_inr:,.2f} exceeds automatic retry threshold of ₹{self.auto_recovery_threshold_inr:,.2f}. Requires manual merchant sign-off.",
                suggested_alternative=ActionType.MANUAL_ESCALATION.value,
                rules_checked=rules_checked,
                amount_threshold_passed=False,
            )

        # Rule 5: Confidence Threshold Guardrail
        rules_checked.append("RULE_5_MINIMUM_CONFIDENCE_THRESHOLD")
        confidence_passed = confidence >= self.min_confidence
        if not confidence_passed:
            return PolicyDecision(
                approved=False,
                rejection_reason=f"Agent decision confidence ({confidence:.2f}) is below minimum threshold ({self.min_confidence:.2f}).",
                suggested_alternative=ActionType.PAYMENT_LINK.value if action_type == ActionType.SMART_RETRY.value else ActionType.MANUAL_ESCALATION.value,
                rules_checked=rules_checked,
                confidence_passed=False,
            )

        # Rule 6: Customer Trust & Abandonment Policy
        rules_checked.append("RULE_6_CUSTOMER_TRUST_AND_ABANDONMENT")
        if failure_category == FailureCategory.ABANDONMENT.value and action_type == ActionType.SMART_RETRY.value:
            return PolicyDecision(
                approved=False,
                rejection_reason="Automated backend retry cannot recover a checkout abandonment. A customer reminder or payment link is required.",
                suggested_alternative=ActionType.CUSTOMER_REMINDER.value,
                rules_checked=rules_checked,
                action_applicability_passed=False,
            )

        # All guardrails passed
        return PolicyDecision(
            approved=True,
            rejection_reason=None,
            suggested_alternative=None,
            rules_checked=rules_checked,
            confidence_passed=True,
            retry_limit_passed=True,
            amount_threshold_passed=True,
            action_applicability_passed=True,
        )

    def get_config_summary(self) -> dict:
        """Returns active guardrail parameters and stopping rules."""
        return {
            "max_recovery_retries": self.max_retries,
            "min_recovery_confidence": self.min_confidence,
            "auto_recovery_threshold_inr": self.auto_recovery_threshold_inr,
            "stopping_rules": [
                f"Stop after {self.max_retries} retry attempts",
                "Stop smart retry on terminal bank decline codes (e.g. INVALID_CARD_NUMBER, ACCOUNT_BLOCKED)",
                f"Require manual escalation if amount > ₹{self.auto_recovery_threshold_inr:,.2f}",
                f"Reject actions with confidence < {self.min_confidence * 100:.0f}%",
                "Forbid automated retries on checkout abandonment without customer interaction",
            ],
            "enforced_guardrails": [
                "RULE_1_MERCHANT_AUTO_RECOVERY_ENABLED",
                "RULE_2_MAX_RETRY_LIMIT",
                "RULE_3_TERMINAL_FAILURE_CHECK",
                "RULE_4_HIGH_VALUE_THRESHOLD",
                "RULE_5_MINIMUM_CONFIDENCE_THRESHOLD",
                "RULE_6_CUSTOMER_TRUST_AND_ABANDONMENT",
            ],
        }


policy_engine = PolicyEngine()
