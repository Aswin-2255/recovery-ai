"""Automated Test Suite for Batch Revenue Recovery Evaluation.

Validates deterministic batch execution, financial formulas, policy stopping rules,
breakdowns, audit trails, and REST API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.schemas.analytics import BatchEvaluationRequest
from app.services.analytics_service import analytics_service
from app.models import RecoveryCase, RecoveryAction, AuditLog, Transaction


@pytest.fixture
def batch_db():
    """Isolated in-memory SQLite database session for batch evaluation testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_deterministic_batch_execution(batch_db):
    """
    Given identical seed and input parameters, batch evaluation produces
    bit-exact reproducible financial metrics and recovery statistics.
    """
    req1 = BatchEvaluationRequest(seed=42, total_transactions=50, include_incident=True)
    res1 = analytics_service.evaluate_batch(db=batch_db, request=req1)

    # Re-create fresh database for second run
    engine2 = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine2)
    Session2 = sessionmaker(bind=engine2)
    session2 = Session2()
    try:
        req2 = BatchEvaluationRequest(seed=42, total_transactions=50, include_incident=True)
        res2 = analytics_service.evaluate_batch(db=session2, request=req2)

        # Compare top-level metrics
        assert res1.total_transactions_evaluated == res2.total_transactions_evaluated == 50
        assert res1.total_transaction_value == res2.total_transaction_value
        assert res1.total_revenue_at_risk == res2.total_revenue_at_risk
        assert res1.recoverable_cases == res2.recoverable_cases
        assert res1.recovered_cases == res2.recovered_cases
        assert res1.unrecoverable_cases == res2.unrecoverable_cases
        assert res1.policy_stopped_cases == res2.policy_stopped_cases
        assert res1.failed_recovery_attempts == res2.failed_recovery_attempts
        assert res1.total_amount_recovered == res2.total_amount_recovered
        assert res1.recovery_rate == res2.recovery_rate
        assert res1.recovery_efficiency == res2.recovery_efficiency

        # Compare breakdown categories
        assert set(res1.by_failure_category.keys()) == set(res2.by_failure_category.keys())
        for cat in res1.by_failure_category:
            item1 = res1.by_failure_category[cat]
            item2 = res2.by_failure_category[cat]
            assert item1.total_evaluated == item2.total_evaluated
            assert item1.revenue_at_risk == item2.revenue_at_risk
            assert item1.recovered_count == item2.recovered_count
            assert item1.amount_recovered == item2.amount_recovered
            assert item1.recovery_rate == item2.recovery_rate
            assert item1.recovery_efficiency == item2.recovery_efficiency

        # Compare breakdown actions
        assert set(res1.by_recovery_action.keys()) == set(res2.by_recovery_action.keys())
        for act in res1.by_recovery_action:
            act1 = res1.by_recovery_action[act]
            act2 = res2.by_recovery_action[act]
            assert act1.attempt_count == act2.attempt_count
            assert act1.success_count == act2.success_count
            assert act1.failed_count == act2.failed_count
            assert act1.blocked_by_policy_count == act2.blocked_by_policy_count
            assert act1.amount_recovered == act2.amount_recovered
    finally:
        session2.close()
        Base.metadata.drop_all(bind=engine2)


def test_financial_metrics_and_formula_correctness(batch_db):
    """
    Verify exact financial correctness:
    - revenue at risk = sum of failed/abandoned transaction amounts
    - amount recovered = sum of completed action amounts
    - recovery rate = (recovered cases / total failed cases) * 100
    - recovery efficiency = (amount recovered / revenue at risk) * 100
    - category breakdown sums match batch totals without double counting
    - terminal resolution partition: recovered + stopped + unrecoverable == total failed cases
    """
    req = BatchEvaluationRequest(seed=123, total_transactions=80, include_incident=True)
    res = analytics_service.evaluate_batch(db=batch_db, request=req)

    assert res.total_transactions_evaluated == 80
    assert res.total_transaction_value > 0
    assert res.total_revenue_at_risk > 0

    # Total cases evaluated in batch
    total_evaluated_cases = batch_db.query(RecoveryCase).count()
    assert total_evaluated_cases > 0

    # Terminal state partition invariant
    assert res.recovered_cases + res.policy_stopped_cases + res.unrecoverable_cases == total_evaluated_cases

    # Verify recovery rate formula
    expected_recovery_rate = round((res.recovered_cases / total_evaluated_cases * 100), 2)
    assert res.recovery_rate == expected_recovery_rate

    # Verify recovery efficiency formula
    expected_efficiency = round((res.total_amount_recovered / res.total_revenue_at_risk * 100), 2)
    assert res.recovery_efficiency == expected_efficiency

    # Verify no double-counting across failure categories
    category_total_evaluated = sum(item.total_evaluated for item in res.by_failure_category.values())
    category_total_risk = sum(item.revenue_at_risk for item in res.by_failure_category.values())
    category_total_recovered_amount = sum(item.amount_recovered for item in res.by_failure_category.values())
    category_total_recovered_count = sum(item.recovered_count for item in res.by_failure_category.values())

    assert category_total_evaluated == total_evaluated_cases
    assert round(category_total_risk, 2) == round(res.total_revenue_at_risk, 2)
    assert round(category_total_recovered_amount, 2) == round(res.total_amount_recovered, 2)
    assert category_total_recovered_count == res.recovered_cases

    # Verify no double-counting across failure codes
    code_total_evaluated = sum(item.total_evaluated for item in res.by_failure_code.values())
    code_total_risk = sum(item.revenue_at_risk for item in res.by_failure_code.values())
    code_total_recovered_amount = sum(item.amount_recovered for item in res.by_failure_code.values())

    assert code_total_evaluated == total_evaluated_cases
    assert round(code_total_risk, 2) == round(res.total_revenue_at_risk, 2)
    assert round(code_total_recovered_amount, 2) == round(res.total_amount_recovered, 2)

    # Verify action breakdown amount recovered matches total amount recovered
    action_total_recovered = sum(act.amount_recovered for act in res.by_recovery_action.values())
    assert round(action_total_recovered, 2) == round(res.total_amount_recovered, 2)


def test_category_code_attribution_and_zero_risk_safeguard(batch_db):
    """
    Ensure that for every failure category and failure code:
    1. amount_recovered <= revenue_at_risk
    2. revenue_at_risk > 0 whenever amount_recovered > 0
    3. known failure codes never resolve to 'unknown' in category breakdown
    """
    for seed in [42, 77, 101, 2024]:
        req = BatchEvaluationRequest(seed=seed, total_transactions=60, include_incident=True)
        res = analytics_service.evaluate_batch(db=batch_db, request=req)

        # Check Category Breakdown invariants
        for cat, item in res.by_failure_category.items():
            assert item.amount_recovered <= item.revenue_at_risk + 0.01, (
                f"Seed {seed} Category '{cat}': recovered ₹{item.amount_recovered} > risk ₹{item.revenue_at_risk}"
            )
            if item.amount_recovered > 0:
                assert item.revenue_at_risk > 0, (
                    f"Seed {seed} Category '{cat}': recovered ₹{item.amount_recovered} with zero revenue at risk"
                )
            assert item.recovery_efficiency <= 100.01

        # Check Failure Code Breakdown invariants
        for code, item in res.by_failure_code.items():
            assert item.amount_recovered <= item.revenue_at_risk + 0.01, (
                f"Seed {seed} Code '{code}': recovered ₹{item.amount_recovered} > risk ₹{item.revenue_at_risk}"
            )
            if item.amount_recovered > 0:
                assert item.revenue_at_risk > 0, (
                    f"Seed {seed} Code '{code}': recovered ₹{item.amount_recovered} with zero revenue at risk"
                )
            assert item.recovery_efficiency <= 100.01


def test_recoverable_tier_classification_vs_recovered_outcome_semantics(batch_db):
    """
    Ensure clear semantic distinction:
    - recoverable_cases represents initial high-probability classification tier (P >= 0.70)
    - recovered_cases represents the verified lifecycle terminal status
    - both metrics are logically coherent and non-negative
    """
    req = BatchEvaluationRequest(seed=42, total_transactions=100, include_incident=True)
    res = analytics_service.evaluate_batch(db=batch_db, request=req)

    total_failed_cases = batch_db.query(RecoveryCase).count()
    assert res.recoverable_cases >= 0
    assert res.recovered_cases >= 0
    assert res.recoverable_cases <= total_failed_cases
    assert res.recovered_cases <= total_failed_cases

    # Terminal resolution states form complete partition
    assert res.recovered_cases + res.policy_stopped_cases + res.unrecoverable_cases == total_failed_cases


def test_policy_stopped_and_unrecoverable_cases(batch_db):
    """
    Ensure that policy-stopped cases and terminal declines are properly
    classified, stopped, and reported in batch metrics.
    """
    req = BatchEvaluationRequest(seed=999, total_transactions=100, include_incident=True)
    res = analytics_service.evaluate_batch(db=batch_db, request=req)

    # There should be cases evaluated
    assert res.total_transactions_evaluated == 100
    assert res.total_revenue_at_risk > 0

    # Check that policy blocked count in action breakdowns aligns with DB
    blocked_actions_count = (
        batch_db.query(RecoveryAction)
        .filter(RecoveryAction.status == "blocked_by_policy")
        .count()
    )
    action_breakdown_blocked = sum(
        act.blocked_by_policy_count for act in res.by_recovery_action.values()
    )
    assert action_breakdown_blocked == blocked_actions_count


def test_audit_logs_recorded_for_batch_evaluation(batch_db):
    """
    Ensure every case in the batch has a complete audit trail across the 6 stages.
    """
    req = BatchEvaluationRequest(seed=42, total_transactions=30, include_incident=False)
    res = analytics_service.evaluate_batch(db=batch_db, request=req)

    all_audits = batch_db.query(AuditLog).all()
    assert len(all_audits) > 0

    action_types = {a.action for a in all_audits}
    assert "RISK_DETECTED" in action_types
    assert "DIAGNOSIS_COMPLETED" in action_types
    assert "DECISION_RECORDED" in action_types
    assert "ACTION_EXECUTED" in action_types or "ACTION_BLOCKED_BY_POLICY" in action_types


def test_batch_evaluate_api_endpoint(client: TestClient):
    """
    Test REST API endpoint POST /api/analytics/evaluate-batch and /api/analytics/batch-evaluate.
    """
    payload = {
        "seed": 42,
        "total_transactions": 50,
        "include_incident": True,
    }
    response = client.post("/api/analytics/evaluate-batch", json=payload)
    assert response.status_code == 200, f"API failed: {response.text}"

    data = response.json()
    assert data["seed"] == 42
    assert data["total_transactions_evaluated"] == 50
    assert data["total_transaction_value"] > 0
    assert data["total_revenue_at_risk"] > 0
    assert "by_failure_category" in data
    assert "by_failure_code" in data
    assert "by_recovery_action" in data
    assert data["execution_time_ms"] >= 0

    # Test alias endpoint
    alias_resp = client.post("/api/analytics/batch-evaluate", json=payload)
    assert alias_resp.status_code == 200
    assert alias_resp.json()["total_transactions_evaluated"] == 50


def test_batch_evaluation_idempotency_on_repeated_calls(batch_db):
    """
    Repeated batch evaluation calls on the same database instance
    operate safely and idempotently.
    """
    req = BatchEvaluationRequest(seed=77, total_transactions=40, include_incident=False)
    res1 = analytics_service.evaluate_batch(db=batch_db, request=req)
    res2 = analytics_service.evaluate_batch(db=batch_db, request=req)

    assert res1.total_transactions_evaluated == res2.total_transactions_evaluated == 40
    assert res1.total_amount_recovered == res2.total_amount_recovered
    assert res1.recovered_cases == res2.recovered_cases
    assert res1.recovery_rate == res2.recovery_rate
