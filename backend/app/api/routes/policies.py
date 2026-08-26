"""Policy Engine and Guardrails REST API endpoints."""
from fastapi import APIRouter
from app.schemas.policy import PolicyConfigRead, PolicyEvaluationRequest, PolicyEvaluationResult
from app.services.policy_engine import policy_engine

router = APIRouter(prefix="/api/policies", tags=["Policy Engine"])


@router.get("", response_model=PolicyConfigRead, summary="Get Policy Guardrails Configuration")
def get_policy_config():
    """Retrieve active policy constraints, thresholds, and hard stopping rules."""
    summary = policy_engine.get_config_summary()
    return PolicyConfigRead(**summary)


@router.post("/evaluate", response_model=PolicyEvaluationResult, summary="Evaluate Action Feasibility Against Guardrails")
def evaluate_policy_guardrail(payload: PolicyEvaluationRequest):
    """
    Test whether a proposed recovery intervention complies with all policy rules
    without executing it.
    """
    decision = policy_engine.evaluate(
        action_type=payload.action_type,
        confidence=payload.confidence,
        retry_count=payload.retry_count,
        amount_inr=payload.amount,
        failure_code=payload.failure_code,
        customer_trust_score=payload.customer_trust_score,
    )
    return PolicyEvaluationResult(
        approved=decision.approved,
        rejection_reason=decision.rejection_reason,
        suggested_alternative=decision.suggested_alternative,
        rules_checked=decision.rules_checked,
        confidence_passed=decision.confidence_passed,
        retry_limit_passed=decision.retry_limit_passed,
        amount_threshold_passed=decision.amount_threshold_passed,
        action_applicability_passed=decision.action_applicability_passed,
    )
