"""FastAPI main application entrypoint."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.database import check_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("recoverai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION} [{settings.APP_ENV}]")
    db_status = check_db_connection()
    logger.info(f"Database status: {db_status}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Autonomous, policy-bounded revenue recovery platform for Razorpay Buildathon.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health_router)


@app.get("/", summary="API Root")
def get_root():
    """Returns basic API service metadata and documentation links."""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "tagline": "Detect lost revenue. Recover it safely. Prove the impact.",
        "docs": "/docs",
        "health": "/health",
        "environment": settings.APP_ENV,
    }
