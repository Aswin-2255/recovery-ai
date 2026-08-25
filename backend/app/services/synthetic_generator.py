"""Reproducible Synthetic Payment Data Generator for RecoverAI.

Generates realistic merchants, customers, payments, failures, checkout abandonments,
subscription recurring charges, retry chains, and payment gateway degradation incidents.
Deterministic when initialized with a fixed random seed.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import random
from typing import List, Tuple, Dict, Any, Optional
import uuid

from app.models.enums import (
    PaymentMethod,
    TransactionType,
    TransactionStatus,
    FailureCategory,
    CasePriority,
    RecoveryClassification,
    RecoveryCaseStatus,
    ActorType,
)
from app.models.merchant import Merchant
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.recovery_case import RecoveryCase
from app.models.audit_log import AuditLog


@dataclass
class FailureCodeDefinition:
    code: str
    category: FailureCategory
    reason: str
    base_recoverability: float  # Baseline probability of recovery (0.0 - 1.0)
    classification: RecoveryClassification


FAILURE_CATALOG: Dict[str, FailureCodeDefinition] = {
    # Temporary / Transient Failures (High to Medium Recoverability)
    "BAD_REQUEST_GATEWAY_TIMEOUT": FailureCodeDefinition(
        code="BAD_REQUEST_GATEWAY_TIMEOUT",
        category=FailureCategory.TEMPORARY,
        reason="Bank gateway timed out during processing (NPCI / Switch timeout)",
        base_recoverability=0.85,
        classification=RecoveryClassification.RECOVERABLE,
    ),
    "NETWORK_ERROR": FailureCodeDefinition(
        code="NETWORK_ERROR",
        category=FailureCategory.TEMPORARY,
        reason="Transient socket connection drop between acquirer and issuing bank",
        base_recoverability=0.82,
        classification=RecoveryClassification.RECOVERABLE,
    ),
    "BANK_SYSTEM_BUSY": FailureCodeDefinition(
        code="BANK_SYSTEM_BUSY",
        category=FailureCategory.TEMPORARY,
        reason="Issuing bank core banking switch reported transient server congestion",
        base_recoverability=0.78,
        classification=RecoveryClassification.RECOVERABLE,
    ),
    "OTP_TIMEOUT": FailureCodeDefinition(
        code="OTP_TIMEOUT",
        category=FailureCategory.TEMPORARY,
        reason="Customer 2FA OTP expired before submission",
        base_recoverability=0.72,
        classification=RecoveryClassification.RECOVERABLE,
    ),

    # Permanent / Hard Failures (Low Recoverability)
    "INSUFFICIENT_FUNDS": FailureCodeDefinition(
        code="INSUFFICIENT_FUNDS",
        category=FailureCategory.PERMANENT,
        reason="Customer account has insufficient funds to fulfill debit request",
        base_recoverability=0.35,
        classification=RecoveryClassification.UNCERTAIN,
    ),
    "INVALID_CARD_NUMBER": FailureCodeDefinition(
        code="INVALID_CARD_NUMBER",
        category=FailureCategory.PERMANENT,
        reason="Card number checksum validation failed (Luhn check invalid)",
        base_recoverability=0.10,
        classification=RecoveryClassification.UNLIKELY_TO_RECOVER,
    ),
    "EXPIRED_CARD": FailureCodeDefinition(
        code="EXPIRED_CARD",
        category=FailureCategory.PERMANENT,
        reason="Card expiration date is in the past",
        base_recoverability=0.15,
        classification=RecoveryClassification.UNLIKELY_TO_RECOVER,
    ),
    "DO_NOT_HONOR": FailureCodeDefinition(
        code="DO_NOT_HONOR",
        category=FailureCategory.PERMANENT,
        reason="Issuing bank declined the transaction with generic do-not-honor policy",
        base_recoverability=0.25,
        classification=RecoveryClassification.UNCERTAIN,
    ),
    "ACCOUNT_BLOCKED": FailureCodeDefinition(
        code="ACCOUNT_BLOCKED",
        category=FailureCategory.PERMANENT,
        reason="Account or card is restricted/frozen by issuing financial institution",
        base_recoverability=0.05,
        classification=RecoveryClassification.UNLIKELY_TO_RECOVER,
    ),

    # Checkout Abandonment
    "CHECKOUT_DROPOFF_AT_PAYMENT_SELECT": FailureCodeDefinition(
        code="CHECKOUT_DROPOFF_AT_PAYMENT_SELECT",
        category=FailureCategory.ABANDONMENT,
        reason="Customer initiated checkout but abandoned before choosing a payment instrument",
        base_recoverability=0.55,
        classification=RecoveryClassification.UNCERTAIN,
    ),
    "USER_CANCELLED": FailureCodeDefinition(
        code="USER_CANCELLED",
        category=FailureCategory.ABANDONMENT,
        reason="Customer explicitly dismissed or cancelled the payment checkout dialog",
        base_recoverability=0.48,
        classification=RecoveryClassification.UNCERTAIN,
    ),

    # Subscription Recurring Failures
    "MANDATE_INSUFFICIENT_FUNDS": FailureCodeDefinition(
        code="MANDATE_INSUFFICIENT_FUNDS",
        category=FailureCategory.PERMANENT,
        reason="Auto-debit recurring mandate presentation failed due to insufficient customer balance",
        base_recoverability=0.60,
        classification=RecoveryClassification.RECOVERABLE,
    ),
    "RECURRING_AUTH_FAILED": FailureCodeDefinition(
        code="RECURRING_AUTH_FAILED",
        category=FailureCategory.TEMPORARY,
        reason="Customer bank failed recurring token authentication challenge",
        base_recoverability=0.68,
        classification=RecoveryClassification.RECOVERABLE,
    ),
}


class SyntheticPaymentGenerator:
    """Deterministic generator for synthetic financial data."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def set_seed(self, seed: int):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_merchant(self, name: str = "Apex Retail Technologies", email: str = "ops@apexretail.in") -> Merchant:
        """Create a default primary merchant entity."""
        return Merchant(
            id="mcht_apex_prod01",
            name=name,
            email=email,
            api_key=f"key_live_apex_{self.seed:04d}",
            webhook_endpoint="https://api.apexretail.in/webhooks/razorpay",
            auto_recovery_enabled=True,
            created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )

    def generate_customers(self, merchant_id: str, count: int = 50) -> List[Customer]:
        """Generate a realistic distribution of customers with varied historical trust and spend."""
        first_names = ["Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Neha", "Aditya", "Sneha", "Rahul", "Kavya", "Siddharth", "Pooja", "Arjun", "Divya", "Karan", "Tanvi", "Varun", "Meera", "Manish", "Ishaan"]
        last_names = ["Sharma", "Verma", "Patel", "Mehta", "Iyer", "Nair", "Reddy", "Gupta", "Singh", "Joshi", "Bose", "Deshmukh", "Choudhury", "Bhat", "Kapoor", "Agarwal", "Saxena", "Menon", "Pillai", "Shah"]

        customers: List[Customer] = []
        for i in range(count):
            fn = self.rng.choice(first_names)
            ln = self.rng.choice(last_names)
            name = f"{fn} {ln}"
            email = f"{fn.lower()}.{ln.lower()}{self.rng.randint(10, 999)}@example.com"
            phone = f"+9198{self.rng.randint(10000000, 99999999)}"

            # Archetype: VIP (15%), Regular (60%), New (15%), High-Risk (10%)
            archetype_roll = self.rng.random()
            if archetype_roll < 0.15:
                # VIP
                successes = self.rng.randint(15, 60)
                failures = self.rng.randint(0, 2)
                spend = round(self.rng.uniform(25000, 250000), 2)
                trust = round(self.rng.uniform(0.92, 0.99), 2)
            elif archetype_roll < 0.75:
                # Regular
                successes = self.rng.randint(3, 18)
                failures = self.rng.randint(0, 3)
                spend = round(self.rng.uniform(2500, 35000), 2)
                trust = round(self.rng.uniform(0.75, 0.90), 2)
            elif archetype_roll < 0.90:
                # New customer
                successes = self.rng.randint(0, 1)
                failures = 0
                spend = round(self.rng.uniform(0, 2000), 2)
                trust = 0.60
            else:
                # High friction / declining
                successes = self.rng.randint(1, 4)
                failures = self.rng.randint(3, 8)
                spend = round(self.rng.uniform(500, 5000), 2)
                trust = round(self.rng.uniform(0.20, 0.45), 2)

            cust = Customer(
                id=f"cust_{i+1:04d}_{fn.lower()[:3]}",
                merchant_id=merchant_id,
                name=name,
                email=email,
                phone=phone,
                historical_success_count=successes,
                historical_failure_count=failures,
                total_spend_inr=spend,
                trust_score=trust,
                created_at=datetime(2026, 1, 15, tzinfo=timezone.utc) + timedelta(days=self.rng.randint(0, 180)),
            )
            customers.append(cust)

        return customers

    def _sample_amount(self, txn_type: TransactionType) -> float:
        """Sample realistic INR transaction amounts based on type."""
        if txn_type == TransactionType.SUBSCRIPTION:
            # SaaS / OTT tiers: 299, 499, 999, 1499, 2999, 4999
            tiers = [299.0, 499.0, 799.0, 999.0, 1499.0, 1999.0, 2999.0, 4999.0]
            return float(self.rng.choice(tiers))
        elif txn_type == TransactionType.INVOICE:
            # B2B Invoices: 8,000 - 95,000
            return round(self.rng.uniform(8000, 95000), 2)
        elif txn_type == TransactionType.CHECKOUT:
            # E-commerce checkout
            return round(self.rng.lognormvariate(7.2, 0.8), 2)  # Mean around 1500-3500
        else:
            # One-time payments: 199 to 45,000
            roll = self.rng.random()
            if roll < 0.60:
                return round(self.rng.uniform(199, 2499), 2)
            elif roll < 0.90:
                return round(self.rng.uniform(2500, 15000), 2)
            else:
                return round(self.rng.uniform(15000, 65000), 2)

    def _sample_payment_method(self) -> str:
        """Weighted sample of Indian payment instruments."""
        methods = [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING, PaymentMethod.WALLET, PaymentMethod.EMI]
        weights = [0.55, 0.25, 0.12, 0.05, 0.03]
        return self.rng.choices(methods, weights=weights, k=1)[0].value

    def generate_dataset(
        self,
        merchant: Merchant,
        customers: List[Customer],
        total_transactions: int = 500,
        start_time: Optional[datetime] = None,
        duration_hours: int = 48,
        include_incident: bool = True,
    ) -> Tuple[List[Transaction], List[RecoveryCase], List[AuditLog]]:
        """
        Generate a complete, coherent dataset of transactions, recovery cases, and audit logs.
        Includes an optional realistic UPI payment degradation incident.
        """
        if start_time is None:
            # Baseline: 2 days ago to now
            start_time = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)

        # Incident window: between hour 26 and hour 30 (e.g. Day 2, 14:00 to 18:00)
        incident_start = start_time + timedelta(hours=26)
        incident_end = start_time + timedelta(hours=30)

        transactions: List[Transaction] = []
        recovery_cases: List[RecoveryCase] = []
        audit_logs: List[AuditLog] = []

        for i in range(total_transactions):
            customer = self.rng.choice(customers)
            # Offset within duration
            offset_seconds = self.rng.randint(0, duration_hours * 3600)
            txn_time = start_time + timedelta(seconds=offset_seconds)

            txn_type_choices = [TransactionType.ONE_TIME, TransactionType.CHECKOUT, TransactionType.SUBSCRIPTION, TransactionType.INVOICE]
            txn_type = self.rng.choices(txn_type_choices, weights=[0.50, 0.30, 0.15, 0.05], k=1)[0]
            amount = self._sample_amount(txn_type)
            method = self._sample_payment_method()

            # Determine if in incident window
            in_incident = include_incident and (incident_start <= txn_time <= incident_end)
            is_incident_affected = False

            # Determine outcome
            if in_incident and method == PaymentMethod.UPI.value:
                # During incident: UPI failure rate spikes to 42%
                failure_prob = 0.42
                is_incident_affected = True
            elif in_incident:
                # Other methods during incident slight collateral degradation (12%)
                failure_prob = 0.12
            else:
                # Baseline failure rates by method
                base_failure_rates = {
                    PaymentMethod.UPI.value: 0.045,
                    PaymentMethod.CARD.value: 0.080,
                    PaymentMethod.NETBANKING.value: 0.095,
                    PaymentMethod.WALLET.value: 0.035,
                    PaymentMethod.EMI.value: 0.070,
                }
                failure_prob = base_failure_rates.get(method, 0.06)

            # Adjust failure prob slightly for low trust customer
            if customer.trust_score < 0.5:
                failure_prob *= 1.4

            roll = self.rng.random()
            if roll > failure_prob:
                # SUCCESS TRANSACTION
                status = TransactionStatus.SUCCESS.value
                failure_cat = FailureCategory.NONE.value
                f_code = None
                f_reason = None
                retries = 0
            else:
                # FAILED OR ABANDONED TRANSACTION
                retries = self.rng.choices([0, 1, 2], weights=[0.70, 0.20, 0.10], k=1)[0]

                if txn_type == TransactionType.CHECKOUT and self.rng.random() < 0.35:
                    # Checkout abandonment
                    status = TransactionStatus.ABANDONED.value
                    f_def = FAILURE_CATALOG["CHECKOUT_DROPOFF_AT_PAYMENT_SELECT"] if self.rng.random() < 0.6 else FAILURE_CATALOG["USER_CANCELLED"]
                elif txn_type == TransactionType.SUBSCRIPTION and self.rng.random() < 0.40:
                    # Subscription mandate failure
                    status = TransactionStatus.FAILED.value
                    f_def = FAILURE_CATALOG["MANDATE_INSUFFICIENT_FUNDS"] if self.rng.random() < 0.7 else FAILURE_CATALOG["RECURRING_AUTH_FAILED"]
                elif is_incident_affected and method == PaymentMethod.UPI.value:
                    # Systemic UPI degradation failure
                    status = TransactionStatus.FAILED.value
                    f_def = FAILURE_CATALOG["BANK_SYSTEM_BUSY"] if self.rng.random() < 0.65 else FAILURE_CATALOG["BAD_REQUEST_GATEWAY_TIMEOUT"]
                else:
                    # Normal failure distribution
                    status = TransactionStatus.FAILED.value
                    general_failure_keys = [
                        "BAD_REQUEST_GATEWAY_TIMEOUT",
                        "NETWORK_ERROR",
                        "OTP_TIMEOUT",
                        "INSUFFICIENT_FUNDS",
                        "INVALID_CARD_NUMBER",
                        "EXPIRED_CARD",
                        "DO_NOT_HONOR",
                    ]
                    weights = [0.25, 0.20, 0.15, 0.20, 0.05, 0.05, 0.10]
                    chosen_key = self.rng.choices(general_failure_keys, weights=weights, k=1)[0]
                    f_def = FAILURE_CATALOG[chosen_key]

                failure_cat = f_def.category.value
                f_code = f_def.code
                f_reason = f_def.reason

            txn_id = f"txn_{i+1:05d}_{self.rng.randint(1000, 9999)}"
            order_id = f"order_{i+1:05d}"

            txn = Transaction(
                id=txn_id,
                merchant_id=merchant.id,
                customer_id=customer.id,
                order_id=order_id,
                amount=amount,
                currency="INR",
                payment_method=method,
                transaction_type=txn_type.value,
                status=status,
                failure_category=failure_cat,
                failure_code=f_code,
                failure_reason=f_reason,
                retry_count=retries,
                max_retries_allowed=3,
                gateway_reference=f"pay_mock_{self.rng.randint(100000, 999999)}" if status == TransactionStatus.SUCCESS.value else None,
                is_synthetic=True,
                is_degradation_incident=is_incident_affected and (status in [TransactionStatus.FAILED.value, TransactionStatus.ABANDONED.value]),
                timestamp=txn_time,
                created_at=txn_time,
            )
            transactions.append(txn)

            # If transaction failed or abandoned, generate RecoveryCase and initial AuditLog
            if status in [TransactionStatus.FAILED.value, TransactionStatus.ABANDONED.value]:
                # Calculate recovery probability baseline
                f_def = FAILURE_CATALOG.get(f_code, FAILURE_CATALOG["NETWORK_ERROR"])
                raw_prob = f_def.base_recoverability * (0.6 + 0.4 * customer.trust_score) - (0.08 * retries)
                recovery_prob = round(max(0.02, min(0.98, raw_prob)), 3)

                # Classify
                if recovery_prob >= 0.70:
                    classification = RecoveryClassification.RECOVERABLE.value
                elif recovery_prob >= 0.40:
                    classification = RecoveryClassification.UNCERTAIN.value
                else:
                    classification = RecoveryClassification.UNLIKELY_TO_RECOVER.value

                # Priority based on amount & recovery probability
                expected_value = amount * recovery_prob
                if expected_value >= 15000 or (amount >= 30000 and recovery_prob >= 0.5):
                    priority = CasePriority.CRITICAL.value
                elif expected_value >= 4000:
                    priority = CasePriority.HIGH.value
                elif expected_value >= 1000:
                    priority = CasePriority.MEDIUM.value
                else:
                    priority = CasePriority.LOW.value

                case_id = f"case_{i+1:05d}_{txn_id[4:9]}"
                recovery_case = RecoveryCase(
                    id=case_id,
                    transaction_id=txn.id,
                    merchant_id=merchant.id,
                    revenue_at_risk=amount,
                    recovery_probability=recovery_prob,
                    priority=priority,
                    classification=classification,
                    status=RecoveryCaseStatus.OPEN.value,
                    reason=f_reason,
                    root_cause_summary=f"Failure code {f_code} via {method.upper()} with customer trust {customer.trust_score:.2f}",
                    created_at=txn_time + timedelta(seconds=2),
                    updated_at=txn_time + timedelta(seconds=2),
                )
                recovery_cases.append(recovery_case)

                # Initial AuditLog for detection
                audit = AuditLog(
                    id=f"aud_{len(audit_logs)+1:06d}",
                    entity_type="recovery_case",
                    entity_id=case_id,
                    actor=ActorType.SYSTEM.value,
                    action="RISK_DETECTED",
                    what_happened=f"Revenue at risk of ₹{amount:,.2f} detected on transaction {txn.id}",
                    what_caused_it=f"Payment failure code: {f_code} ({f_reason})",
                    action_taken="Created recovery case and computed initial recovery probability",
                    result=f"Classification: {classification.upper()} (P={recovery_prob:.2f}), Priority: {priority.upper()}",
                    metadata_json=f'{{"amount": {amount}, "method": "{method}", "probability": {recovery_prob}, "code": "{f_code}"}}',
                    timestamp=txn_time + timedelta(seconds=2),
                )
                audit_logs.append(audit)

        # Sort all by timestamp
        transactions.sort(key=lambda t: t.timestamp)
        recovery_cases.sort(key=lambda c: c.created_at)
        audit_logs.sort(key=lambda a: a.timestamp)

        return transactions, recovery_cases, audit_logs
