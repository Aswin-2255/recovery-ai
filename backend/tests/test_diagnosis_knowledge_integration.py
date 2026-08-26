"""Focused tests for recovery knowledge attached to deterministic diagnosis."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Customer, Merchant, Transaction
from app.models.enums import PaymentMethod, TransactionStatus, FailureCategory
from app.services.diagnosis_service import diagnosis_service


@pytest.fixture
def diagnosis_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    merchant = Merchant(id="mcht_diagnosis", name="Diagnosis Store", email="diagnosis@example.com")
    customer = Customer(
        id="cust_diagnosis",
        merchant_id=merchant.id,
        name="Diagnosis Customer",
        email="customer@example.com",
    )
    session.add_all([merchant, customer])
    session.commit()
    try:
        yield session, merchant, customer
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _diagnose(diagnosis_db, failure_code, category, payment_method=PaymentMethod.UPI.value):
    session, merchant, customer = diagnosis_db
    txn = Transaction(
        id=f"txn_{failure_code.lower()}",
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=3750.0,
        payment_method=payment_method,
        status=TransactionStatus.FAILED.value,
        failure_category=category,
        failure_code=failure_code,
        retry_count=0,
    )
    session.add(txn)
    session.commit()
    return diagnosis_service.diagnose_case(db=session, case_id="case_diagnosis", txn=txn)


def test_diagnosis_adds_gateway_timeout_knowledge(diagnosis_db):
    result = _diagnose(diagnosis_db, "BAD_REQUEST_GATEWAY_TIMEOUT", FailureCategory.TEMPORARY.value)

    assert result.retrieved_knowledge[0].scenario == "gateway_timeout"


def test_diagnosis_adds_insufficient_funds_knowledge(diagnosis_db):
    result = _diagnose(diagnosis_db, "INSUFFICIENT_FUNDS", FailureCategory.PERMANENT.value)

    assert result.retrieved_knowledge[0].scenario == "insufficient_funds"


def test_diagnosis_uses_safe_knowledge_fallback_for_unknown_failure(diagnosis_db):
    result = _diagnose(diagnosis_db, "UNSUPPORTED_FAILURE", FailureCategory.PERMANENT.value)

    assert result.retrieved_knowledge[0].scenario == "unknown_failure"


def test_knowledge_context_does_not_change_existing_diagnosis(diagnosis_db):
    result = _diagnose(diagnosis_db, "BAD_REQUEST_GATEWAY_TIMEOUT", FailureCategory.TEMPORARY.value)

    assert result.is_transient is True
    assert result.systemic_degradation_detected is True
    assert "Systemic UPI bank gateway degradation detected" in result.root_cause_summary
    assert result.detailed_metrics["retry_count"] == 0
