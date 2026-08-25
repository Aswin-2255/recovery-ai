"""Tests for relational foreign keys, cascade deletes, and constraints."""
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
    PaymentMethod,
    TransactionStatus,
    ActionType,
    ActionStatus,
    AgentDecisionType,
)


@pytest.fixture
def db():
    """SQLite test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_merchant_cascade_deletion(db):
    """Deleting a merchant should cascade delete its customers, transactions, and recovery cases."""
    mcht = Merchant(name="Mcht Deletion Test", email="del@mcht.com")
    db.add(mcht)
    db.commit()

    cust = Customer(merchant_id=mcht.id, name="Cust 1", email="c1@mcht.com")
    db.add(cust)
    db.commit()

    txn = Transaction(
        merchant_id=mcht.id,
        customer_id=cust.id,
        amount=1200.0,
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
    )
    db.add(txn)
    db.commit()

    case = RecoveryCase(
        transaction_id=txn.id,
        merchant_id=mcht.id,
        revenue_at_risk=1200.0,
    )
    db.add(case)
    db.commit()

    assert db.query(Customer).count() == 1
    assert db.query(Transaction).count() == 1
    assert db.query(RecoveryCase).count() == 1

    # Delete merchant
    db.delete(mcht)
    db.commit()

    assert db.query(Merchant).count() == 0
    assert db.query(Customer).count() == 0
    assert db.query(Transaction).count() == 0
    assert db.query(RecoveryCase).count() == 0


def test_case_actions_and_decisions_ordering(db):
    """Verify recovery case child actions and decisions preserve creation ordering."""
    mcht = Merchant(name="Ordering Test", email="ord@mcht.com")
    db.add(mcht)
    db.flush()

    cust = Customer(merchant_id=mcht.id, name="Cust Order", email="cord@mcht.com")
    db.add(cust)
    db.flush()

    txn = Transaction(
        merchant_id=mcht.id,
        customer_id=cust.id,
        amount=5000.0,
        payment_method=PaymentMethod.CARD.value,
        status=TransactionStatus.FAILED.value,
    )
    db.add(txn)
    db.commit()

    case = RecoveryCase(transaction_id=txn.id, merchant_id=mcht.id, revenue_at_risk=5000.0)
    db.add(case)
    db.commit()

    act1 = RecoveryAction(recovery_case_id=case.id, action_type=ActionType.SMART_RETRY.value, status=ActionStatus.FAILED.value)
    act2 = RecoveryAction(recovery_case_id=case.id, action_type=ActionType.PAYMENT_LINK.value, status=ActionStatus.COMPLETED.value, amount_recovered=5000.0)
    db.add_all([act1, act2])
    db.commit()

    refreshed_case = db.query(RecoveryCase).filter_by(id=case.id).first()
    assert len(refreshed_case.actions) == 2
    assert refreshed_case.actions[0].action_type == ActionType.SMART_RETRY.value
    assert refreshed_case.actions[1].action_type == ActionType.PAYMENT_LINK.value
