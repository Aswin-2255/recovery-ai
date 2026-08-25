"""Enumeration definitions for RecoverAI database models and lifecycle states."""
import enum


class PaymentMethod(str, enum.Enum):
    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"


class TransactionType(str, enum.Enum):
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"
    INVOICE = "invoice"
    CHECKOUT = "checkout"


class TransactionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"
    PENDING = "pending"


class FailureCategory(str, enum.Enum):
    NONE = "none"
    TEMPORARY = "temporary"
    PERMANENT = "permanent"
    ABANDONMENT = "abandonment"
    SYSTEMIC_DEGRADATION = "systemic_degradation"


class CasePriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecoveryClassification(str, enum.Enum):
    RECOVERABLE = "recoverable"
    UNCERTAIN = "uncertain"
    UNLIKELY_TO_RECOVER = "unlikely_to_recover"


class RecoveryCaseStatus(str, enum.Enum):
    OPEN = "open"
    DIAGNOSED = "diagnosed"
    IN_PROGRESS = "in_progress"
    RECOVERED = "recovered"
    UNRECOVERABLE = "unrecoverable"
    ESCALATED = "escalated"
    STOPPED = "stopped"


class ActionType(str, enum.Enum):
    SMART_RETRY = "smart_retry"
    PAYMENT_LINK = "payment_link"
    FALLBACK_METHOD = "fallback_payment_method"
    CUSTOMER_REMINDER = "customer_reminder"
    MANUAL_ESCALATION = "manual_escalation"


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED_BY_POLICY = "blocked_by_policy"


class AgentDecisionType(str, enum.Enum):
    RECOMMEND_ACTION = "recommend_action"
    ESCALATE = "escalate"
    STOP = "stop"


class ActorType(str, enum.Enum):
    SYSTEM = "system"
    AI_AGENT = "ai_agent"
    POLICY_ENGINE = "policy_engine"
    MERCHANT = "merchant"
    SIMULATOR = "simulator"
    RAZORPAY_WEBHOOK = "razorpay_webhook"
