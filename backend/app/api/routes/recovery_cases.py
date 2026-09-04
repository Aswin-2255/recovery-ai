"""Recovery Cases REST API endpoints."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import RecoveryCase, Transaction
from app.schemas.recovery_case import (
    RecoveryCaseRead,
    RecoveryCaseDetail,
    DiagnoseResponse,
    DecideResponse,
)
from app.schemas.recovery_action import (
    ExecuteActionRequest,
    ExecuteActionResult,
    FullRecoveryWorkflowResult,
)
from app.services.recovery_knowledge_service import recovery_knowledge_service
from app.services.recovery_lifecycle_service import recovery_lifecycle_service

router = APIRouter(prefix="/api/recovery-cases", tags=["Recovery Cases"])


@router.get("", response_model=List[RecoveryCaseRead], summary="List Recovery Cases")
def list_recovery_cases(
    status: Optional[str] = Query(None, description="Filter by status: open, diagnosed, in_progress, recovered, unrecoverable, stopped"),
    classification: Optional[str] = Query(None, description="Filter by classification: recoverable, uncertain, unlikely_to_recover"),
    priority: Optional[str] = Query(None, description="Filter by priority: critical, high, medium, low"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List recovery cases with optional filtering and pagination."""
    query = db.query(RecoveryCase)
    if status:
        query = query.filter(RecoveryCase.status == status)
    if classification:
        query = query.filter(RecoveryCase.classification == classification)
    if priority:
        query = query.filter(RecoveryCase.priority == priority)

    return query.order_by(RecoveryCase.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{case_id}", response_model=RecoveryCaseDetail, summary="Get Recovery Case Details with Timeline")
def get_recovery_case(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve full details of a recovery case including child actions and decisions."""
    clean_id = case_id.strip()
    case = db.query(RecoveryCase).filter(
        (RecoveryCase.id == clean_id) | (RecoveryCase.transaction_id == clean_id)
    ).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"RecoveryCase '{case_id}' not found.")

    txn = db.query(Transaction).filter_by(id=case.transaction_id).first()
    if txn:
        knowledge_items = recovery_knowledge_service.retrieve(
            failure_code=txn.failure_code,
            payment_method=txn.payment_method,
            amount=txn.amount,
            retry_count=txn.retry_count,
            diagnosis=case.root_cause_summary,
        )
        case.retrieved_knowledge = [
            item.model_dump() if hasattr(item, "model_dump") else item.__dict__
            for item in knowledge_items
        ]
    else:
        case.retrieved_knowledge = []

    return case


@router.post("/{case_id}/diagnose", response_model=DiagnoseResponse, summary="Execute Stage 2: Root Cause Diagnosis")
def diagnose_case(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Run Root Cause Analysis on the specified recovery case."""
    try:
        updated_case = recovery_lifecycle_service.diagnose_case(db=db, case_id=case_id)
        txn = db.query(Transaction).filter_by(id=updated_case.transaction_id).first()
        return DiagnoseResponse(
            case_id=updated_case.id,
            root_cause_summary=updated_case.root_cause_summary or "",
            failure_category=txn.failure_category if txn else "none",
            failure_code=txn.failure_code if txn else None,
            systemic_degradation_detected=txn.is_degradation_incident if txn else False,
            is_transient=(txn.failure_category == "temporary") if txn else False,
            diagnosed_at=datetime.now(timezone.utc),
	    retrieved_knowledge=[
                item.model_dump() if hasattr(item, "model_dump") else item.__dict__
                for item in getattr(updated_case, "retrieved_knowledge", [])
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{case_id}/decide", response_model=DecideResponse, summary="Execute Stage 3: Agent Strategy Decision")
def decide_recovery_strategy(
    case_id: str,
    db: Session = Depends(get_db),
):
    """AI Agent selects optimal bounded intervention strategy."""
    try:
        decision = recovery_lifecycle_service.decide_recovery_strategy(db=db, case_id=case_id)
        return DecideResponse(
            case_id=decision.recovery_case_id,
            decision=decision.decision,
            recommended_action=decision.recommended_action,
            confidence=decision.confidence,
            reasoning_summary=decision.reasoning_summary,
            policy_approved=decision.policy_approved,
            policy_rejection_reason=decision.policy_rejection_reason,
            decided_at=decision.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{case_id}/execute", response_model=ExecuteActionResult, summary="Execute Stage 4-6: Policy Guardrails & Action")
def execute_recovery_action(
    case_id: str,
    payload: ExecuteActionRequest,
    db: Session = Depends(get_db),
):
    """
    Validate proposed action against Policy Guardrails and execute via simulator/gateway.
    """
    try:
        action = recovery_lifecycle_service.execute_recovery_action(
            db=db,
            case_id=case_id,
            action_type=payload.action_type,
            force_mode=payload.force_mode or "simulator",
        )
        return ExecuteActionResult(
            action_id=action.id,
            case_id=action.recovery_case_id,
            action_type=action.action_type,
            status=action.status,
            policy_approved=(action.status != "blocked_by_policy"),
            policy_rejection_reason=action.result if action.status == "blocked_by_policy" else None,
            amount_recovered=action.amount_recovered,
            result_message=action.result or "Action executed",
            executed_at=action.executed_at or datetime.now(timezone.utc),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{case_id}/recover", response_model=FullRecoveryWorkflowResult, summary="Execute Full 6-Stage Autonomous Lifecycle")
def run_full_recovery_workflow(
    case_id: str,
    db: Session = Depends(get_db),
):
    """
    Runs the complete 6-Stage Lifecycle on a case:
    [Detect] ➔ [Diagnose] ➔ [Decide] ➔ [Execute] ➔ [Verify] ➔ [Measure]
    """
    try:
        result = recovery_lifecycle_service.run_full_lifecycle(db=db, case_id=case_id)
        return FullRecoveryWorkflowResult(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
