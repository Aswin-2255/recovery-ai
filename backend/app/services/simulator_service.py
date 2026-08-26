"""High-Fidelity Deterministic Simulator for Recovery Actions.

Simulates the execution of recovery actions (smart retry, payment link,
fallback method, customer reminder) against payment networks and customer
behavior models in development/test mode.
"""
from dataclasses import dataclass
import random
from typing import Optional, Tuple
from app.models.enums import ActionType, FailureCategory
from app.services.synthetic_generator import FAILURE_CATALOG


@dataclass
class SimulatorExecutionResult:
    success: bool
    amount_recovered: float
    message: str
    gateway_reference: Optional[str]
    failure_reason: Optional[str]


class RecoverySimulator:
    """Executes recovery actions deterministically based on seed and failure characteristics."""

    def __init__(self, default_seed: Optional[int] = 42):
        self.default_seed = default_seed

    def execute_action(
        self,
        action_type: str,
        amount_inr: float,
        failure_code: Optional[str],
        failure_category: Optional[str],
        customer_trust: float = 1.0,
        retry_attempt: int = 1,
        seed: Optional[int] = None,
    ) -> SimulatorExecutionResult:
        """
        Simulate the outcome of executing a bounded recovery action.
        """
        active_seed = seed if seed is not None else (int(amount_inr * 100) + retry_attempt)
        rng = random.Random(active_seed)

        catalog_def = FAILURE_CATALOG.get(failure_code or "")
        base_recoverability = catalog_def.base_recoverability if catalog_def else 0.50

        # Adjust probability based on action type
        if action_type == ActionType.SMART_RETRY.value:
            if failure_code in ["INVALID_CARD_NUMBER", "ACCOUNT_BLOCKED", "EXPIRED_CARD"]:
                # Smart retry on hard failure always fails
                return SimulatorExecutionResult(
                    success=False,
                    amount_recovered=0.0,
                    message=f"Smart retry failed: Bank rejected retry due to permanent decline ({failure_code}).",
                    gateway_reference=None,
                    failure_reason="PERMANENT_BANK_DECLINE",
                )
            # Smart retry succeeds with high probability for transient errors
            success_prob = min(0.95, base_recoverability * 1.15 - (0.05 * retry_attempt))

        elif action_type == ActionType.PAYMENT_LINK.value:
            # Payment link success depends heavily on customer trust and engagement
            success_prob = min(0.92, 0.40 + (0.50 * customer_trust))

        elif action_type == ActionType.FALLBACK_METHOD.value:
            # Fallback method (e.g. Card to UPI) bypasses card declines
            success_prob = min(0.90, 0.75 * customer_trust)

        elif action_type == ActionType.CUSTOMER_REMINDER.value:
            # Reminder for checkout abandonment / mandate
            success_prob = min(0.85, 0.50 + (0.40 * customer_trust))

        elif action_type == ActionType.MANUAL_ESCALATION.value:
            # Manual escalation handled offline
            return SimulatorExecutionResult(
                success=True,
                amount_recovered=0.0,
                message="Case escalated to merchant operations team for white-glove manual outreach.",
                gateway_reference="esc_manual_ops",
                failure_reason=None,
            )
        else:
            success_prob = 0.50

        # Roll deterministic outcome
        roll = rng.random()
        if roll <= success_prob:
            mock_ref = f"pay_recov_{rng.randint(100000, 999999)}"
            return SimulatorExecutionResult(
                success=True,
                amount_recovered=amount_inr,
                message=f"Recovery successful via {action_type.replace('_', ' ').title()}. Payment captured with ref {mock_ref}.",
                gateway_reference=mock_ref,
                failure_reason=None,
            )
        else:
            return SimulatorExecutionResult(
                success=False,
                amount_recovered=0.0,
                message=f"Recovery attempt via {action_type.replace('_', ' ').title()} was unsuccessful (customer did not complete or bank declined).",
                gateway_reference=None,
                failure_reason="CUSTOMER_INACTION_OR_BANK_DECLINE",
            )


recovery_simulator = RecoverySimulator()
