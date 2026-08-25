"""Unit tests for SQLAlchemy database models."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
    CasePriority,
    RecoveryClassification,
    RecoveryCaseStatus,
    ActionType,
    ActionStatus,
    AgentDecisionType,
    ActorType,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session for model unit testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def test_merchant_creation_and_fields(db_session):
    """Test Merchant model creation and default values."""
    merchant = Merchant(
        name="Test Merchant Ltd",
        email="finance@testmerchant.com",
    )
    db_session.add(merchant)
    db_session.commit()

    assert merchant.id.startswith("mcht_")
    assert merchant.api_key.startswith("key_")
    assert merchant.auto_recovery_enabled is True
    assert merchant.created_at is not None


def test_customer_creation_and_relationships(db_session):
    """Test Customer creation and Merchant relationship."""
    merchant = Merchant(name="Merchant Co", email="ops@merchant.co")
    db_session.add(merchant)
    db_session.commit()

    customer = Customer(
        merchant_id=merchant.id,
        name="Priya Sharma",
        email="priya.sharma@example.com",
        phone="+919876543210",
        historical_success_count=5,
        trust_score=0.95,
    )
    db_session.add(customer)
    db_session.commit()

    assert customer.id.startswith("cust_")
    assert customer.merchant.name == "Merchant Co"
    assert len(merchant.customers) == 1


def test_transaction_and_recovery_case_lifecycle(db_session):
    """Test Transaction -> RecoveryCase -> RecoveryAction -> AgentDecision linkage."""
    merchant = Merchant(name="Fintech Merchant", email="hello@fintech.in")
    db_session.add(merchant)
    db_session.commit()

    customer = Customer(
        merchant_id=merchant.id,
        name="Rahul Verma",
        email="rahul@example.com",
    )
    db_session.add(customer)
    db_session.commit()

    # Failed transaction
    txn = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=4500.0,
        currency="INR",
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        failure_reason="Gateway timeout during switch routing",
        retry_count=1,
    )
    db_session.add(txn)
    db_session.commit()

    assert txn.id.startswith("txn_")
    assert txn.status == "failed"

    # Associated Recovery Case
    case = RecoveryCase(
        transaction_id=txn.id,
        merchant_id=merchant.id,
        revenue_at_risk=4500.0,
        recovery_probability=0.82,
        priority=CasePriority.HIGH.value,
        classification=RecoveryClassification.RECOVERABLE.value,
        status=RecoveryCaseStatus.OPEN.value,
        reason=txn.failure_reason,
    )
    db_session.add(case)
    db_session.commit()

    assert case.id.startswith("case_")
    assert case.transaction.amount == 4500.0
    assert txn.recovery_case.id == case.id

    # Agent Decision
    decision = AgentDecision(
        recovery_case_id=case.id,
        decision=AgentDecisionType.RECOMMEND_ACTION.value,
        recommended_action=ActionType.SMART_RETRY.value,
        reasoning_summary="Transient gateway timeout with 82% recovery likelihood",
        confidence=0.85,
        policy_approved=True,
    )
    db_session.add(decision)
    db_session.commit()

    # Recovery Action
    action = RecoveryAction(
        recovery_case_id=case.id,
        action_type=ActionType.SMART_RETRY.value,
        status=ActionStatus.COMPLETED.value,
        amount_recovered=4500.0,
        result="Smart retry successful on second gateway attempt",
    )
    db_session.add(action)
    db_session.commit()

    assert len(case.decisions) == 1
    assert len(case.actions) == 1
    assert case.actions[0].amount_recovered == 4500.0


def test_audit_log_recording(db_session):
    """Test creating and querying AuditLog entries."""
    audit = AuditLog(
        entity_type="recovery_case",
        entity_id="case_001",
        actor=ActorType.AI_AGENT.value,
        action="DECISION_RECORDED",
        what_happened="Agent evaluated case and recommended smart retry",
        what_caused_it="Temporary payment failure due to NPCI switch congestion",
        action_taken="Scheduled immediate smart retry",
        result="Policy approved; scheduled for execution",
    )
    db_session.add(audit)
    db_session.commit()

    fetched = db_session.query(AuditLog).filter_by(entity_id="case_001").first()
    assert fetched is not None
    assert fetched.actor == "ai_agent"
    assert fetched.action == "DECISION_RECORDED"
