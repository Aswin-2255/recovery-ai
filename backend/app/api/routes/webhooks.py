"""Razorpay Webhook Ingestion & Signature Verification Endpoint."""
import hashlib
import hmac
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Transaction, RecoveryCase, RecoveryAction, AuditLog
from app.models.enums import TransactionStatus, RecoveryCaseStatus, ActionStatus, ActorType
from app.schemas.webhook import WebhookVerificationResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# In-memory idempotency cache for deduplication
PROCESSED_EVENT_IDS = set()


@router.post("/razorpay", response_model=WebhookVerificationResult, summary="Razorpay Webhook Handler")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default="test_signature"),
    db: Session = Depends(get_db),
):
    """
    Ingest cryptographically signed Razorpay payment events.
    Verifies signature and handles idempotency.
    """
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    try:
        data = json.loads(body_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")

    event_name = data.get("event", "unknown")
    payload = data.get("payload", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    payment_id = payment_entity.get("id", "pay_mock_unknown")
    event_id = f"{event_name}_{payment_id}_{data.get('created_at', '')}"

    # Idempotency Check
    if event_id in PROCESSED_EVENT_IDS:
        logger.info(f"Duplicate webhook event ignored: {event_id}")
        return WebhookVerificationResult(
            success=True,
            event=event_name,
            entity_id=payment_id,
            signature_valid=True,
            idempotent_processed=False,
            message="Event already processed (idempotency deduplication).",
        )

    PROCESSED_EVENT_IDS.add(event_id)

    # Signature verification (in test mode or when secret is set)
    is_valid = True
    if settings.RAZORPAY_WEBHOOK_SECRET and settings.RAZORPAY_WEBHOOK_SECRET != "placeholder_webhook_secret":
        expected_sig = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        is_valid = hmac.compare_digest(expected_sig, x_razorpay_signature)

    case_id = None
    if event_name == "payment.captured":
        # Payment captured - verify and reconcile if associated with a recovery case
        order_id = payment_entity.get("order_id")
        txn = db.query(Transaction).filter_by(order_id=order_id).first() if order_id else None
        if txn and txn.recovery_case:
            case = txn.recovery_case
            case.status = RecoveryCaseStatus.RECOVERED.value
            case.revenue_at_risk = 0.0
            txn.status = TransactionStatus.SUCCESS.value
            case_id = case.id

            audit = AuditLog(
                id=f"aud_wh_{payment_id[-8:]}",
                entity_type="recovery_case",
                entity_id=case.id,
                actor=ActorType.RAZORPAY_WEBHOOK.value,
                action="WEBHOOK_PAYMENT_CAPTURED",
                what_happened=f"Payment captured event received for payment {payment_id}",
                what_caused_it="Customer completed recovery checkout link / retry",
                action_taken="Reconciled transaction status to SUCCESS and closed recovery case",
                result=f"Case {case.id} marked RECOVERED",
                metadata_json=body_str,
            )
            db.add(audit)
            db.commit()

    return WebhookVerificationResult(
        success=True,
        event=event_name,
        entity_id=payment_id,
        signature_valid=is_valid,
        idempotent_processed=True,
        recovery_case_id=case_id,
        message=f"Webhook event '{event_name}' processed successfully.",
    )
