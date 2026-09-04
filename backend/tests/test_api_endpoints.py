"""Integration tests for RecoverAI REST API endpoints."""
from fastapi.testclient import TestClient
from app.models.enums import PaymentMethod, TransactionType


def test_transactions_api_flow(client: TestClient):
    """Test simulating a transaction failure and querying transaction endpoints."""
    # 1. Simulate failure
    payload = {
        "amount": 4999.0,
        "payment_method": "upi",
        "transaction_type": "one_time",
        "failure_code": "BAD_REQUEST_GATEWAY_TIMEOUT",
        "is_degradation_incident": True,
    }
    sim_resp = client.post("/api/transactions/simulate-failure", json=payload)
    assert sim_resp.status_code == 201
    case_data = sim_resp.json()
    assert "id" in case_data
    assert case_data["revenue_at_risk"] == 4999.0

    # 2. Query transactions list
    list_resp = client.get("/api/transactions?limit=10")
    assert list_resp.status_code == 200
    txns = list_resp.json()
    assert len(txns) > 0

    # 3. Query single transaction
    txn_id = case_data["transaction_id"]
    get_resp = client.get(f"/api/transactions/{txn_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == txn_id


def test_recovery_cases_api_flow(client: TestClient):
    """Test full recovery case lifecycle API endpoints."""
    # 1. Create a case via failure simulation
    sim_resp = client.post(
        "/api/transactions/simulate-failure",
        json={
            "amount": 2500.0,
            "payment_method": "card",
            "transaction_type": "checkout",
            "failure_code": "NETWORK_ERROR",
        },
    )
    assert sim_resp.status_code == 201
    case_id = sim_resp.json()["id"]

    # 2. Get case details
    get_resp = client.get(f"/api/recovery-cases/{case_id}")
    assert get_resp.status_code == 200
    case_detail = get_resp.json()
    assert case_detail["id"] == case_id
    assert "retrieved_knowledge" in case_detail
    assert len(case_detail["retrieved_knowledge"]) > 0
    assert case_detail["retrieved_knowledge"][0]["scenario"] == "network_failure"

    # 3. Diagnose endpoint
    diag_resp = client.post(f"/api/recovery-cases/{case_id}/diagnose")
    assert diag_resp.status_code == 200
    assert diag_resp.json()["case_id"] == case_id

    # 4. Decide endpoint
    decide_resp = client.post(f"/api/recovery-cases/{case_id}/decide")
    assert decide_resp.status_code == 200
    assert "recommended_action" in decide_resp.json()

    # 5. Full Autonomous Recover endpoint
    recover_resp = client.post(f"/api/recovery-cases/{case_id}/recover")
    assert recover_resp.status_code == 200
    assert recover_resp.json()["lifecycle_stage_completed"] == "6_MEASURE"


def test_diagnose_api_returns_retrieved_knowledge(client: TestClient):
    """Diagnosis response serializes the knowledge retrieved by DiagnosisService."""
    sim_resp = client.post(
        "/api/transactions/simulate-failure",
        json={
            "amount": 3750.0,
            "payment_method": "upi",
            "transaction_type": "one_time",
            "failure_code": "BAD_REQUEST_GATEWAY_TIMEOUT",
        },
    )
    assert sim_resp.status_code == 201

    diagnose_resp = client.post(f"/api/recovery-cases/{sim_resp.json()['id']}/diagnose")
    assert diagnose_resp.status_code == 200
    knowledge = diagnose_resp.json()["retrieved_knowledge"]

    assert knowledge[0]["scenario"] == "gateway_timeout"
    assert "smart_retry" in knowledge[0]["recommended_recovery_actions"]
    assert knowledge[0]["do_not_retry_conditions"]


def test_policies_api(client: TestClient):
    """Test Policy Engine configuration and evaluation endpoints."""
    # 1. Get active policy config
    config_resp = client.get("/api/policies")
    assert config_resp.status_code == 200
    config_data = config_resp.json()
    assert config_data["max_recovery_retries"] >= 1
    assert "stopping_rules" in config_data

    # 2. Evaluate policy guardrail
    eval_resp = client.post(
        "/api/policies/evaluate",
        json={
            "action_type": "smart_retry",
            "retry_count": 0,
            "amount": 5000.0,
            "confidence": 0.85,
        },
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["approved"] is True

    # 3. Evaluate exceeding retry limit
    eval_fail_resp = client.post(
        "/api/policies/evaluate",
        json={
            "action_type": "smart_retry",
            "retry_count": 5,
            "amount": 5000.0,
            "confidence": 0.85,
        },
    )
    assert eval_fail_resp.status_code == 200
    assert eval_fail_resp.json()["approved"] is False


def test_analytics_api(client: TestClient):
    """Test Analytics KPI and Breakdown endpoints."""
    # Overview
    ov_resp = client.get("/api/analytics/overview")
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()
    assert "total_transactions" in ov_data
    assert "success_rate" in ov_data
    assert "total_revenue_volume_inr" in ov_data

    # Breakdown
    bd_resp = client.get("/api/analytics/breakdown")
    assert bd_resp.status_code == 200
    bd_data = bd_resp.json()
    assert "by_payment_method" in bd_data
    assert "by_failure_code" in bd_data

    # Incidents
    inc_resp = client.get("/api/analytics/incidents")
    assert inc_resp.status_code == 200
    assert "is_incident_active" in inc_resp.json()


def test_audit_logs_api(client: TestClient):
    """Test Audit Log query endpoint."""
    resp = client.get("/api/audit-logs?limit=20")
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)


def test_razorpay_webhook_api(client: TestClient):
    """Test Razorpay Webhook ingestion with idempotency."""
    webhook_payload = {
        "event": "payment.failed",
        "account_id": "acc_mock_01",
        "created_at": 1724580000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_webhook_01",
                    "amount": 350000,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_test_wh_01",
                }
            }
        },
    }
    resp1 = client.post("/api/webhooks/razorpay", json=webhook_payload)
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True
    assert resp1.json()["idempotent_processed"] is True

    # Duplicate call -> idempotent deduplication
    resp2 = client.post("/api/webhooks/razorpay", json=webhook_payload)
    assert resp2.status_code == 200
    assert resp2.json()["idempotent_processed"] is False


def test_simulate_failure_persists_and_retrieves_case_immediately(client: TestClient):
    """
    Explicit test requested for full persistence flow:
    simulate-failure -> persist RecoveryCase -> return case_id -> GET case by same case_id -> diagnose -> decide -> execute -> recover
    """
    # 1. Simulate failure
    payload = {
        "amount": 3750.0,
        "payment_method": "upi",
        "transaction_type": "one_time",
        "failure_code": "BAD_REQUEST_GATEWAY_TIMEOUT",
        "is_degradation_incident": False,
    }
    sim_resp = client.post("/api/transactions/simulate-failure", json=payload)
    assert sim_resp.status_code == 201, f"Failed: {sim_resp.text}"
    case_data = sim_resp.json()
    case_id = case_data["id"]
    assert case_id.startswith("case_")
    assert case_data["revenue_at_risk"] == 3750.0

    # 2. Immediately retrieve the case via GET /api/recovery-cases/{case_id}
    get_resp = client.get(f"/api/recovery-cases/{case_id}")
    assert get_resp.status_code == 200, f"GET /api/recovery-cases/{case_id} failed: {get_resp.text}"
    retrieved_case = get_resp.json()
    assert retrieved_case["id"] == case_id
    assert retrieved_case["revenue_at_risk"] == 3750.0
    assert retrieved_case["status"] in ["open", "diagnosed"]

    # 3. Diagnose Stage
    diag_resp = client.post(f"/api/recovery-cases/{case_id}/diagnose")
    assert diag_resp.status_code == 200, f"POST diagnose failed: {diag_resp.text}"
    assert diag_resp.json()["case_id"] == case_id

    # 4. Decide Stage
    decide_resp = client.post(f"/api/recovery-cases/{case_id}/decide")
    assert decide_resp.status_code == 200, f"POST decide failed: {decide_resp.text}"
    assert decide_resp.json()["policy_approved"] is True

    # 5. Execute Stage
    exec_resp = client.post(f"/api/recovery-cases/{case_id}/execute", json={"action_type": "smart_retry"})
    assert exec_resp.status_code == 200, f"POST execute failed: {exec_resp.text}"
    assert exec_resp.json()["case_id"] == case_id

    # 6. Full Autonomous Recover Stage
    rec_resp = client.post(f"/api/recovery-cases/{case_id}/recover")
    assert rec_resp.status_code == 200, f"POST recover failed: {rec_resp.text}"
    assert rec_resp.json()["case_id"] == case_id
    assert rec_resp.json()["lifecycle_stage_completed"] == "6_MEASURE"


def test_simulate_failure_and_full_lifecycle_step_by_step(client: TestClient):
    """
    Step-by-step verification of the 6-stage lifecycle via REST API:
    1. simulate-failure -> HTTP 201 + returns case_id
    2. GET /api/recovery-cases/{case_id} -> HTTP 200 + matched case_id
    3. POST /api/recovery-cases/{case_id}/diagnose -> HTTP 200 + matched case_id
    4. POST /api/recovery-cases/{case_id}/decide -> HTTP 200 + policy_approved
    5. POST /api/recovery-cases/{case_id}/execute -> HTTP 200 + action executed
    6. POST /api/recovery-cases/{case_id}/recover -> HTTP 200 + 6_MEASURE stage completed
    7. GET /api/recovery-cases/{txn_id} -> HTTP 200 + retrieve case by transaction_id
    """
    # 1. Ingest simulated payment failure
    sim_resp = client.post(
        "/api/transactions/simulate-failure",
        json={
            "amount": 8999.0,
            "payment_method": "upi",
            "transaction_type": "one_time",
            "failure_code": "BAD_REQUEST_GATEWAY_TIMEOUT",
            "is_degradation_incident": False,
        },
    )
    assert sim_resp.status_code == 201
    sim_data = sim_resp.json()
    case_id = sim_data["id"]
    txn_id = sim_data["transaction_id"]
    assert case_id.startswith("case_")
    assert txn_id.startswith("txn_")

    # 2. Retrieve RecoveryCase by case_id
    get_resp = client.get(f"/api/recovery-cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == case_id
    assert get_resp.json()["transaction_id"] == txn_id

    # 3. Retrieve RecoveryCase by transaction_id
    get_by_txn = client.get(f"/api/recovery-cases/{txn_id}")
    assert get_by_txn.status_code == 200
    assert get_by_txn.json()["id"] == case_id

    # 4. Diagnose Case (Stage 2)
    diag_resp = client.post(f"/api/recovery-cases/{case_id}/diagnose")
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    assert diag_data["case_id"] == case_id
    assert diag_data["failure_code"] == "BAD_REQUEST_GATEWAY_TIMEOUT"

    # 5. Decide Strategy (Stage 3)
    decide_resp = client.post(f"/api/recovery-cases/{case_id}/decide")
    assert decide_resp.status_code == 200
    decide_data = decide_resp.json()
    assert decide_data["case_id"] == case_id
    assert decide_data["policy_approved"] is True
    assert decide_data["recommended_action"] is not None

    # 6. Execute Bounded Recovery Action (Stage 4)
    exec_resp = client.post(
        f"/api/recovery-cases/{case_id}/execute",
        json={"action_type": decide_data["recommended_action"]},
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["case_id"] == case_id
    assert exec_data["status"] in ["completed", "failed", "blocked_by_policy"]

    # 7. Execute Full Autonomous Recovery (Stage 1-6)
    recover_resp = client.post(f"/api/recovery-cases/{case_id}/recover")
    assert recover_resp.status_code == 200
    recover_data = recover_resp.json()
    assert recover_data["case_id"] == case_id
    assert recover_data["lifecycle_stage_completed"] == "6_MEASURE"
    assert "6_MEASURE" in recover_data["stages_executed"]
    assert len(recover_data["audit_log_ids"]) >= 1


def test_recovery_case_lookup_with_whitespace_and_invalid_id(client: TestClient):
    """Test whitespace stripping and 404 handling for invalid case IDs."""
    # Invalid case id returns 404
    non_existent = "case_nonexistent_999999"
    resp = client.get(f"/api/recovery-cases/{non_existent}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

    # Create a real case
    sim_resp = client.post(
        "/api/transactions/simulate-failure",
        json={
            "amount": 1200.0,
            "payment_method": "card",
            "transaction_type": "checkout",
            "failure_code": "NETWORK_ERROR",
        },
    )
    assert sim_resp.status_code == 201
    case_id = sim_resp.json()["id"]

    # Trailing/leading whitespace handled cleanly
    resp_ws = client.get(f"/api/recovery-cases/%20{case_id}%20")
    assert resp_ws.status_code == 200
    assert resp_ws.json()["id"] == case_id


def test_terminal_recovery_endpoints_are_idempotent(client: TestClient):
    """Repeated execute/recover calls return the original result without a new action."""
    sim_resp = client.post(
        "/api/transactions/simulate-failure",
        json={
            "amount": 3750.0,
            "payment_method": "upi",
            "transaction_type": "one_time",
            "failure_code": "BAD_REQUEST_GATEWAY_TIMEOUT",
        },
    )
    assert sim_resp.status_code == 201
    case_id = sim_resp.json()["id"]

    decision_resp = client.post(f"/api/recovery-cases/{case_id}/decide")
    assert decision_resp.status_code == 200
    action_type = decision_resp.json()["recommended_action"]

    first_execute = client.post(
        f"/api/recovery-cases/{case_id}/execute", json={"action_type": action_type}
    )
    assert first_execute.status_code == 200
    assert first_execute.json()["status"] == "completed"

    replay_execute = client.post(
        f"/api/recovery-cases/{case_id}/execute", json={"action_type": action_type}
    )
    assert replay_execute.status_code == 200
    assert replay_execute.json()["action_id"] == first_execute.json()["action_id"]

    first_recover = client.post(f"/api/recovery-cases/{case_id}/recover")
    replay_recover = client.post(f"/api/recovery-cases/{case_id}/recover")
    assert first_recover.status_code == replay_recover.status_code == 200
    assert first_recover.json()["action_status"] == replay_recover.json()["action_status"] == "completed"
    assert replay_recover.json() == first_recover.json()

    case_resp = client.get(f"/api/recovery-cases/{case_id}")
    assert case_resp.status_code == 200
    assert len(case_resp.json()["actions"]) == 1
