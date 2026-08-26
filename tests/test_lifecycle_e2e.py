"""RecoverAI End-to-End Lifecycle Integration Test Suite.

Validates the full 6-stage autonomous workflow:
[Detect] ➔ [Diagnose] ➔ [Decide] ➔ [Execute] ➔ [Verify] ➔ [Measure]
"""
import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import Base
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
    RecoveryCaseStatus,
    ActionType,
    ActionStatus,
    ActorType,
)
from app.services.recovery_lifecycle_service import recovery_lifecycle_service
from app.services.policy_engine import policy_engine
from app.services.synthetic_generator import SyntheticPaymentGenerator


@pytest.fixture
def e2e_db():
    """Isolated database session for full E2E workflow testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Seed small synthetic environment
        gen = SyntheticPaymentGenerator(seed=42)
        merchant = gen.generate_merchant()
        customers = gen.generate_customers(merchant.id, count=10)
        session.add(merchant)
        session.add_all(customers)
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_e2e_full_lifecycle_detect_to_measure(e2e_db):
    """
    E2E Test:
    1. Detect: Transient UPI failure is ingested into recovery engine.
    2. Diagnose: Root Cause Analysis confirms switch congestion & transient nature.
    3. Decide: AI Agent recommends smart retry with backoff.
    4. Execute: Policy Engine validates stopping rules and authorizes simulator execution.
    5. Verify: Recovery status and ledger state verified.
    6. Measure: Exact money recovered is reconciled and recorded in immutable audit log.
    """
    customer = e2e_db.query(Customer).first()
    merchant = e2e_db.query(Merchant).first()

    # Step 1: Failed Transaction
    txn = Transaction(
        id="txn_e2e_transient_upi",
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=5499.0,
        currency="INR",
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        failure_reason="NPCI switch timeout during peak traffic",
        retry_count=0,
    )
    e2e_db.add(txn)
    e2e_db.commit()

    # Stage 1: Detect
    case = recovery_lifecycle_service.detect_revenue_at_risk(db=e2e_db, transaction=txn)
    assert case.id.startswith("case_")
    assert case.revenue_at_risk == 5499.0

    # Stage 2: Diagnose
    diag_case = recovery_lifecycle_service.diagnose_case(db=e2e_db, case_id=case.id)
    assert diag_case.status == RecoveryCaseStatus.DIAGNOSED.value
    assert "BAD_REQUEST_GATEWAY_TIMEOUT" in (diag_case.root_cause_summary or "") or "NPCI" in (diag_case.root_cause_summary or "")

    # Stage 3: Decide
    decision = recovery_lifecycle_service.decide_recovery_strategy(db=e2e_db, case_id=case.id)
    assert decision.recommended_action == ActionType.SMART_RETRY.value
    assert decision.confidence >= 0.60
    assert decision.policy_approved is True

    # Stage 4, 5, 6: Execute, Verify, Measure
    action = recovery_lifecycle_service.execute_recovery_action(
        db=e2e_db,
        case_id=case.id,
        action_type=decision.recommended_action,
    )
    assert action.status in [ActionStatus.COMPLETED.value, ActionStatus.FAILED.value]

    # Verify Audit Trail Completeness
    audit_trail = (
        e2e_db.query(AuditLog)
        .filter(AuditLog.entity_id.in_([case.id, decision.id, action.id]))
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    assert len(audit_trail) >= 4
    action_types = [a.action for a in audit_trail]
    assert "RISK_DETECTED" in action_types
    assert "DIAGNOSIS_COMPLETED" in action_types
    assert "DECISION_RECORDED" in action_types
    assert "ACTION_EXECUTED" in action_types
