"""Integration tests for 6-Stage Revenue Recovery Lifecycle."""
from datetime import datetime, timezone
import json
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
    RecoveryCaseStatus,
    ActionType,
    ActionStatus,
)
from app.services.recovery_lifecycle_service import recovery_lifecycle_service
from app.services.diagnosis_service import diagnosis_service


@pytest.fixture
def lifecycle_db():
    """In-memory SQLite session for lifecycle testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Seed basic merchant and customer
        mcht = Merchant(id="mcht_life_01", name="Lifecycle Store", email="ops@lifecyclestore.com")
        session.add(mcht)
        session.flush()

        cust = Customer(
            id="cust_life_01",
            merchant_id=mcht.id,
            name="Aarav Sharma",
            email="aarav.sharma@example.com",
            trust_score=0.90,
        )
        session.add(cust)
        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_stage_1_detect_creates_case_and_audit(lifecycle_db):
    """Stage 1 [Detect]: Failed payment triggers recovery case creation and risk detection audit."""
    txn = Transaction(
        id="txn_fail_01",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=3500.0,
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        failure_reason="Gateway timeout during switch routing",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    assert case is not None
    assert case.revenue_at_risk == 3500.0
    assert case.status == RecoveryCaseStatus.OPEN.value
    assert case.recovery_probability > 0.50

    # Audit log check
    audit = lifecycle_db.query(AuditLog).filter_by(entity_id=case.id, action="RISK_DETECTED").first()
    assert audit is not None
    assert "₹3,500.00" in audit.what_happened


def test_stage_2_diagnose_performs_root_cause_analysis(lifecycle_db):
    """Stage 2 [Diagnose]: Root cause analysis populates explainable diagnostic summary."""
    txn = Transaction(
        id="txn_diag_01",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=4200.0,
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BANK_SYSTEM_BUSY",
        failure_reason="Issuing bank core banking switch congestion",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    diagnosed_case = recovery_lifecycle_service.diagnose_case(db=lifecycle_db, case_id=case.id)

    assert diagnosed_case.status == RecoveryCaseStatus.DIAGNOSED.value
    assert "BANK_SYSTEM_BUSY" in (diagnosed_case.root_cause_summary or "") or "NPCI" in (diagnosed_case.root_cause_summary or "") or "UPI" in (diagnosed_case.root_cause_summary or "")

    # Audit log check
    audit = lifecycle_db.query(AuditLog).filter_by(entity_id=case.id, action="DIAGNOSIS_COMPLETED").first()
    assert audit is not None


def test_stage_3_decide_formulates_strategy(lifecycle_db):
    """Stage 3 [Decide]: Formulates optimal intervention and runs policy pre-check."""
    txn = Transaction(
        id="txn_dec_01",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=1999.0,
        payment_method=PaymentMethod.CARD.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.PERMANENT.value,
        failure_code="INVALID_CARD_NUMBER",
        failure_reason="Card number checksum invalid",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    decision = recovery_lifecycle_service.decide_recovery_strategy(db=lifecycle_db, case_id=case.id)

    assert decision is not None
    assert decision.recommended_action == ActionType.FALLBACK_METHOD.value
    assert decision.confidence > 0.80

    audit = lifecycle_db.query(AuditLog).filter_by(entity_id=decision.id, action="DECISION_RECORDED").first()
    assert audit is not None


def test_decision_uses_retrieved_knowledge_as_recommendation_signal(lifecycle_db):
    """Authentication knowledge refines smart retry to a customer-facing action."""
    txn = Transaction(
        id="txn_decision_knowledge",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=2500.0,
        payment_method=PaymentMethod.CARD.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="OTP_TIMEOUT",
        failure_reason="Customer OTP expired",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    diagnosis = diagnosis_service.diagnose_case(db=lifecycle_db, case_id=case.id, txn=txn)
    decision = recovery_lifecycle_service.decide_recovery_strategy(db=lifecycle_db, case_id=case.id)
    payload = json.loads(decision.execution_payload_json)

    assert diagnosis.retrieved_knowledge[0].scenario == "authentication_failure"
    assert payload["knowledge_scenarios"][0] == "authentication_failure"
    assert payload["deterministic_action"] == ActionType.SMART_RETRY.value
    assert decision.recommended_action == ActionType.PAYMENT_LINK.value
    assert payload["knowledge_influenced_action"] is True
    assert decision.policy_approved is True


def test_policy_still_vetoes_knowledge_aligned_high_value_retry(lifecycle_db):
    """Knowledge-supported smart retry is still rejected by the Policy Engine."""
    txn = Transaction(
        id="txn_decision_policy_veto",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=75000.0,
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        failure_reason="Gateway timeout",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    decision = recovery_lifecycle_service.decide_recovery_strategy(db=lifecycle_db, case_id=case.id)
    payload = json.loads(decision.execution_payload_json)

    assert payload["knowledge_scenarios"][0] == "gateway_timeout"
    assert decision.recommended_action == ActionType.SMART_RETRY.value
    assert decision.policy_approved is False
    assert "exceeds automatic retry threshold" in (decision.policy_rejection_reason or "")


def test_full_autonomous_6_stage_workflow(lifecycle_db):
    """End-to-End: Complete 6-Stage Autonomous Lifecycle execution."""
    txn = Transaction(
        id="txn_full_01",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=2500.0,
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        failure_reason="NPCI switch timeout",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    result = recovery_lifecycle_service.run_full_lifecycle(db=lifecycle_db, case_id=case.id)

    assert result["lifecycle_stage_completed"] == "6_MEASURE"
    assert "1_DETECT" in result["stages_executed"]
    assert "2_DIAGNOSE" in result["stages_executed"]
    assert "3_DECIDE" in result["stages_executed"]
    assert "4_EXECUTE" in result["stages_executed"]
    assert "5_VERIFY" in result["stages_executed"]
    assert "6_MEASURE" in result["stages_executed"]
    assert len(result["audit_log_ids"]) >= 3


def test_terminal_recovered_case_reuses_existing_action(lifecycle_db):
    """A recovered case must not create a duplicate action or audit trail on replay."""
    txn = Transaction(
        id="txn_idempotent_recovered",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=3750.0,
        payment_method=PaymentMethod.UPI.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.TEMPORARY.value,
        failure_code="BAD_REQUEST_GATEWAY_TIMEOUT",
        failure_reason="Gateway timeout",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    decision = recovery_lifecycle_service.decide_recovery_strategy(db=lifecycle_db, case_id=case.id)
    first_action = recovery_lifecycle_service.execute_recovery_action(
        db=lifecycle_db, case_id=case.id, action_type=decision.recommended_action
    )
    assert case.status == RecoveryCaseStatus.RECOVERED.value

    action_count = lifecycle_db.query(RecoveryAction).filter_by(recovery_case_id=case.id).count()
    audit_count = lifecycle_db.query(AuditLog).count()

    replayed_action = recovery_lifecycle_service.execute_recovery_action(
        db=lifecycle_db, case_id=case.id, action_type=decision.recommended_action
    )
    replayed_workflow = recovery_lifecycle_service.run_full_lifecycle(db=lifecycle_db, case_id=case.id)

    assert replayed_action.id == first_action.id
    assert replayed_workflow["action_status"] == first_action.status
    assert lifecycle_db.query(RecoveryAction).filter_by(recovery_case_id=case.id).count() == action_count
    assert lifecycle_db.query(AuditLog).count() == audit_count


def test_terminal_stopped_case_reuses_existing_action(lifecycle_db):
    """A policy-stopped case must remain read-only on execute or recover replay."""
    txn = Transaction(
        id="txn_idempotent_stopped",
        merchant_id="mcht_life_01",
        customer_id="cust_life_01",
        amount=2000.0,
        payment_method=PaymentMethod.CARD.value,
        status=TransactionStatus.FAILED.value,
        failure_category=FailureCategory.PERMANENT.value,
        failure_code="INVALID_CARD_NUMBER",
        failure_reason="Invalid card number",
    )
    lifecycle_db.add(txn)
    lifecycle_db.commit()

    case = recovery_lifecycle_service.detect_revenue_at_risk(db=lifecycle_db, transaction=txn)
    first_action = recovery_lifecycle_service.execute_recovery_action(
        db=lifecycle_db, case_id=case.id, action_type=ActionType.SMART_RETRY.value
    )
    assert first_action.status == ActionStatus.BLOCKED_BY_POLICY.value
    assert case.status == RecoveryCaseStatus.STOPPED.value

    action_count = lifecycle_db.query(RecoveryAction).filter_by(recovery_case_id=case.id).count()
    audit_count = lifecycle_db.query(AuditLog).count()

    replayed_action = recovery_lifecycle_service.execute_recovery_action(
        db=lifecycle_db, case_id=case.id, action_type=ActionType.SMART_RETRY.value
    )
    replayed_workflow = recovery_lifecycle_service.run_full_lifecycle(db=lifecycle_db, case_id=case.id)

    assert replayed_action.id == first_action.id
    assert replayed_workflow["case_final_status"] == RecoveryCaseStatus.STOPPED.value
    assert lifecycle_db.query(RecoveryAction).filter_by(recovery_case_id=case.id).count() == action_count
    assert lifecycle_db.query(AuditLog).count() == audit_count
