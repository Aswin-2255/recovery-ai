"""Analytics and Metrics REST API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import OverviewMetrics, BreakdownMetrics, IncidentStatusRead
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview", response_model=OverviewMetrics, summary="Get Overview Metrics")
def get_overview_metrics(db: Session = Depends(get_db)):
    """Retrieve top-level KPI metrics computed directly from transaction records."""
    return analytics_service.get_overview_metrics(db=db)


@router.get("/breakdown", response_model=BreakdownMetrics, summary="Get Method and Failure Breakdown")
def get_breakdown_metrics(db: Session = Depends(get_db)):
    """Retrieve breakdowns by payment method, failure codes, and classifications."""
    return analytics_service.get_breakdown_metrics(db=db)


@router.get("/incidents", response_model=IncidentStatusRead, summary="Get Active Incident & Degradation Status")
def get_incident_status(db: Session = Depends(get_db)):
    """Retrieve current gateway degradation and systemic failure incident telemetry."""
    return analytics_service.get_incident_status(db=db)
