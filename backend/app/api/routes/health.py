"""System health and diagnostic endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.database import check_db_connection

router = APIRouter(tags=["Health"])


class DatabaseHealth(BaseModel):
    status: str
    dialect: str = "unknown"
    mode: str = "unknown"
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall health status")
    app: str = Field(default=settings.APP_NAME, description="Application name")
    version: str = Field(default=settings.VERSION, description="Application version")
    environment: str = Field(default=settings.APP_ENV, description="Deployment environment")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Current UTC timestamp",
    )
    database: DatabaseHealth = Field(description="Database connectivity status")
    razorpay_mode: str = Field(default=settings.RAZORPAY_MODE, description="Payment integration mode")
    llm_provider: str = Field(default=settings.LLM_PROVIDER, description="Configured LLM provider")


@router.get("/health", response_model=HealthResponse, summary="System Health Check")
def get_system_health() -> HealthResponse:
    """
    Returns system status, active database connectivity, payment mode, and runtime parameters.
    Used for uptime probes, deployment checks, and frontend readiness verification.
    """
    db_info = check_db_connection()
    return HealthResponse(
        status="ok" if db_info.get("status") == "connected" else "degraded",
        app=settings.APP_NAME,
        version=settings.VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=DatabaseHealth(**db_info),
        razorpay_mode=settings.RAZORPAY_MODE,
        llm_provider=settings.LLM_PROVIDER,
    )
