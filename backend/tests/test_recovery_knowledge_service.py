"""Focused tests for deterministic recovery knowledge retrieval."""
from app.services.recovery_knowledge_service import recovery_knowledge_service


def test_gateway_timeout_retrieves_gateway_timeout_knowledge():
    results = recovery_knowledge_service.retrieve(
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        payment_method="upi",
        amount=3750.0,
        retry_count=0,
    )

    assert results[0].scenario == "gateway_timeout"


def test_insufficient_funds_retrieves_insufficient_funds_knowledge():
    results = recovery_knowledge_service.retrieve(failure_code="INSUFFICIENT_FUNDS")

    assert results[0].scenario == "insufficient_funds"


def test_payment_pending_retrieves_pending_payment_knowledge():
    results = recovery_knowledge_service.retrieve(failure_code="PAYMENT_PENDING")

    assert results[0].scenario == "payment_pending"


def test_retrieval_accepts_full_transaction_context():
    results = recovery_knowledge_service.retrieve(
        failure_code="BANK_SYSTEM_BUSY",
        payment_method="upi",
        amount=12000.0,
        retry_count=1,
        diagnosis="Systemic UPI gateway degradation and bank congestion detected",
    )

    assert results[0].scenario == "bank_timeout_or_busy"


def test_unknown_failure_returns_safe_fallback_knowledge():
    results = recovery_knowledge_service.retrieve(failure_code="UNSUPPORTED_FAILURE")

    assert len(results) == 1
    assert results[0].scenario == "unknown_failure"
    assert "Do not automatically retry" in results[0].do_not_retry_conditions


def test_retrieval_results_include_required_structured_fields():
    item = recovery_knowledge_service.retrieve(failure_code="NETWORK_ERROR")[0]

    assert item.scenario
    assert item.failure_codes
    assert item.description
    assert item.likely_root_cause
    assert item.recommended_recovery_actions
    assert item.retry_guidance
    assert item.risk_considerations
    assert item.policy_considerations
    assert item.do_not_retry_conditions
    assert item.escalation_conditions
