"""Unit tests for RecoverAI Policy Guardrails Engine."""
import pytest
from app.services.policy_engine import PolicyEngine, policy_engine
from app.models.enums import ActionType, FailureCategory


def test_policy_engine_max_retries_veto():
    """Policy Engine must veto actions when max retries limit is reached."""
    pe = PolicyEngine(max_retries=3)
    
    # 0 retries -> approved
    d0 = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.85,
        retry_count=0,
        amount_inr=1500.0,
    )
    assert d0.approved is True
    assert d0.retry_limit_passed is True

    # 3 retries -> vetoed
    d3 = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.85,
        retry_count=3,
        amount_inr=1500.0,
    )
    assert d3.approved is False
    assert d3.retry_limit_passed is False
    assert "Max retry limit" in (d3.rejection_reason or "")


def test_policy_engine_terminal_failure_blocking():
    """Policy Engine must forbid smart retries on permanent/terminal bank failure codes."""
    pe = PolicyEngine()
    
    # Invalid card checksum cannot be retried automatically
    decision = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.90,
        retry_count=0,
        amount_inr=2000.0,
        failure_code="INVALID_CARD_NUMBER",
    )
    assert decision.approved is False
    assert decision.action_applicability_passed is False
    assert "terminal failure code" in (decision.rejection_reason or "")
    assert decision.suggested_alternative == ActionType.FALLBACK_METHOD.value


def test_policy_engine_high_value_threshold_guardrail():
    """Policy Engine must prevent automated retries above configured INR threshold."""
    pe = PolicyEngine(auto_recovery_threshold_inr=50000.0)
    
    decision = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.95,
        retry_count=0,
        amount_inr=75000.0,
    )
    assert decision.approved is False
    assert decision.amount_threshold_passed is False
    assert "exceeds automatic retry threshold" in (decision.rejection_reason or "")
    assert decision.suggested_alternative == ActionType.MANUAL_ESCALATION.value


def test_policy_engine_confidence_threshold_guardrail():
    """Policy Engine must veto decisions when agent confidence is below threshold."""
    pe = PolicyEngine(min_confidence=0.60)
    
    decision = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.45,
        retry_count=0,
        amount_inr=1000.0,
    )
    assert decision.approved is False
    assert decision.confidence_passed is False
    assert "below minimum threshold" in (decision.rejection_reason or "")


def test_policy_engine_checkout_abandonment_rule():
    """Policy Engine forbids automated retries on checkout abandonment without user engagement."""
    pe = PolicyEngine()
    
    decision = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.80,
        retry_count=0,
        amount_inr=2500.0,
        failure_category=FailureCategory.ABANDONMENT.value,
    )
    assert decision.approved is False
    assert decision.action_applicability_passed is False
    assert decision.suggested_alternative == ActionType.CUSTOMER_REMINDER.value


def test_policy_engine_merchant_auto_recovery_disabled():
    """Policy Engine halts actions when merchant disables automated recovery."""
    pe = PolicyEngine()
    
    decision = pe.evaluate(
        action_type=ActionType.SMART_RETRY.value,
        confidence=0.90,
        retry_count=0,
        amount_inr=1000.0,
        merchant_auto_enabled=False,
    )
    assert decision.approved is False
    assert "disabled automated recovery" in (decision.rejection_reason or "")
