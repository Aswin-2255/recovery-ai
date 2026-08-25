"""Tests for synthetic payment generator reproducibility and distributions."""
import pytest
from app.services.synthetic_generator import SyntheticPaymentGenerator, FAILURE_CATALOG
from app.models.enums import PaymentMethod, TransactionStatus, FailureCategory


def test_generator_deterministic_reproducibility():
    """Verify that generating with identical seeds produces identical records."""
    gen1 = SyntheticPaymentGenerator(seed=1234)
    mcht1 = gen1.generate_merchant()
    custs1 = gen1.generate_customers(merchant_id=mcht1.id, count=20)
    txns1, cases1, audits1 = gen1.generate_dataset(mcht1, custs1, total_transactions=100)

    gen2 = SyntheticPaymentGenerator(seed=1234)
    mcht2 = gen2.generate_merchant()
    custs2 = gen2.generate_customers(merchant_id=mcht2.id, count=20)
    txns2, cases2, audits2 = gen2.generate_dataset(mcht2, custs2, total_transactions=100)

    # Assert exact matching
    assert len(txns1) == len(txns2) == 100
    assert len(cases1) == len(cases2)
    assert len(audits1) == len(audits2)

    for t1, t2 in zip(txns1, txns2):
        assert t1.id == t2.id
        assert t1.amount == t2.amount
        assert t1.payment_method == t2.payment_method
        assert t1.status == t2.status
        assert t1.failure_code == t2.failure_code
        assert t1.timestamp == t2.timestamp

    for c1, c2 in zip(cases1, cases2):
        assert c1.id == c2.id
        assert c1.revenue_at_risk == c2.revenue_at_risk
        assert c1.recovery_probability == c2.recovery_probability
        assert c1.classification == c2.classification


def test_generator_different_seeds_produce_distinct_data():
    """Verify that different seeds produce distinct datasets."""
    gen1 = SyntheticPaymentGenerator(seed=42)
    m1 = gen1.generate_merchant()
    c1 = gen1.generate_customers(m1.id, count=10)
    txns1, _, _ = gen1.generate_dataset(m1, c1, total_transactions=50)

    gen2 = SyntheticPaymentGenerator(seed=999)
    m2 = gen2.generate_merchant()
    c2 = gen2.generate_customers(m2.id, count=10)
    txns2, _, _ = gen2.generate_dataset(m2, c2, total_transactions=50)

    # First transaction amounts or IDs should differ
    amounts1 = [t.amount for t in txns1[:10]]
    amounts2 = [t.amount for t in txns2[:10]]
    assert amounts1 != amounts2


def test_generator_incident_creation_and_degradation():
    """Verify that UPI failure rate spikes during the simulated incident window."""
    gen = SyntheticPaymentGenerator(seed=42)
    mcht = gen.generate_merchant()
    custs = gen.generate_customers(mcht.id, count=30)
    txns, cases, _ = gen.generate_dataset(mcht, custs, total_transactions=300, include_incident=True)

    incident_txns = [t for t in txns if t.is_degradation_incident]
    assert len(incident_txns) > 0, "Incident transactions should be detected"

    for itxn in incident_txns:
        assert itxn.status in [TransactionStatus.FAILED.value, TransactionStatus.ABANDONED.value]
        assert itxn.payment_method == PaymentMethod.UPI.value or itxn.failure_category != FailureCategory.NONE.value


def test_failure_catalog_completeness():
    """Ensure failure catalog covers required scenarios."""
    required_codes = [
        "BAD_REQUEST_GATEWAY_TIMEOUT",
        "NETWORK_ERROR",
        "BANK_SYSTEM_BUSY",
        "OTP_TIMEOUT",
        "INSUFFICIENT_FUNDS",
        "INVALID_CARD_NUMBER",
        "EXPIRED_CARD",
        "CHECKOUT_DROPOFF_AT_PAYMENT_SELECT",
        "MANDATE_INSUFFICIENT_FUNDS",
    ]
    for code in required_codes:
        assert code in FAILURE_CATALOG
        assert FAILURE_CATALOG[code].base_recoverability >= 0.0
        assert FAILURE_CATALOG[code].base_recoverability <= 1.0
