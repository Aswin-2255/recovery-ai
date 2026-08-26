"""Route modules package."""
from app.api.routes.health import router as health_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.recovery_cases import router as recovery_cases_router
from app.api.routes.policies import router as policies_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.webhooks import router as webhooks_router

__all__ = [
    "health_router",
    "transactions_router",
    "recovery_cases_router",
    "policies_router",
    "analytics_router",
    "audit_logs_router",
    "webhooks_router",
]
