"""Transactions REST API endpoints."""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Transaction, Merchant, Customer
from app.models.enums import TransactionStatus, FailureCategory
from app.schemas.transaction import TransactionRead, SimulateFailureRequest
from app.schemas.recovery_case import RecoveryCaseRead
from app.services.recovery_lifecycle_service import recovery_lifecycle_service
from app.services.synthetic_generator import FAILURE_CATALOG

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.get("", response_model=List[TransactionRead], summary="List Transactions")
def list_transactions(
    status: Optional[str] = Query(None, description="Filter by status: success, failed, abandoned, pending"),
    payment_method: Optional[str] = Query(None, description="Filter by method: upi, card, netbanking, wallet, emi"),
    is_incident: Optional[bool] = Query(None, description="Filter by degradation incident flag"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List transactions with optional filtering and pagination."""
    query = db.query(Transaction)
    if status:
        query = query.filter(Transaction.status == status)
    if payment_method:
        query = query.filter(Transaction.payment_method == payment_method)
    if is_incident is not None:
        query = query.filter(Transaction.is_degradation_incident == is_incident)

    return query.order_by(Transaction.timestamp.desc()).offset(offset).limit(limit).all()


@router.get("/{transaction_id}", response_model=TransactionRead, summary="Get Transaction Details")
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a single transaction by ID."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Transaction '{transaction_id}' not found.")
    return txn


@router.post("/simulate-failure", response_model=RecoveryCaseRead, status_code=status.HTTP_201_CREATED, summary="Simulate Payment Failure & Detect Risk")
def simulate_payment_failure(
    payload: SimulateFailureRequest,
    db: Session = Depends(get_db),
):
    """
    Ingest or simulate a payment failure event.
    Automatically triggers Stage 1 [Detect] of the RecoverAI lifecycle.
    """
    # Get or default merchant
    merchant = db.query(Merchant).first()
    if not merchant:
        merchant = Merchant(name="Apex Retail Technologies", email="ops@apexretail.in")
        db.add(merchant)
        db.commit()
        db.refresh(merchant)

    # Get or default customer
    customer = db.query(Customer).filter_by(merchant_id=merchant.id).first()
    if not customer:
        customer = Customer(
            merchant_id=merchant.id,
            name="Demo Customer",
            email="demo.customer@example.com",
            trust_score=0.85,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

    f_def = FAILURE_CATALOG.get(payload.failure_code)
    f_cat = f_def.category.value if f_def else FailureCategory.TEMPORARY.value
    f_reason = f_def.reason if f_def else "Simulated payment failure"

    txn = Transaction(
        id=f"txn_{uuid.uuid4().hex[:14]}",
        merchant_id=payload.merchant_id or merchant.id,
        customer_id=payload.customer_id or customer.id,
        amount=payload.amount,
        currency="INR",
        payment_method=payload.payment_method.value,
        transaction_type=payload.transaction_type.value,
        status=TransactionStatus.FAILED.value,
        failure_category=f_cat,
        failure_code=payload.failure_code,
        failure_reason=f_reason,
        retry_count=0,
        max_retries_allowed=3,
        is_synthetic=True,
        is_degradation_incident=payload.is_degradation_incident,
        timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Trigger Stage 1: Detect
    case = recovery_lifecycle_service.detect_revenue_at_risk(db=db, transaction=txn)
    return case
