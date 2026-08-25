"""Database engine, session management, and connection utilities."""
import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy ORM models
Base = declarative_base()

def _create_database_engine():
    """Create SQLAlchemy engine with automatic fallback for seamless local developer onboarding."""
    db_url = settings.DATABASE_URL
    is_sqlite = db_url.startswith("sqlite")
    
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    
    try:
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )
        # Test connection immediately
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Connected to primary database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        return engine, "postgresql" if not is_sqlite else "sqlite"
    except Exception as e:
        if settings.DATABASE_FALLBACK_SQLITE and not is_sqlite:
            logger.warning(
                f"Could not connect to primary PostgreSQL database ({e}). "
                f"Falling back to local SQLite database for development."
            )
            fallback_url = "sqlite:///./recoverai_local.db"
            fallback_engine = create_engine(
                fallback_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            return fallback_engine, "sqlite_fallback"
        raise e


engine, active_db_type = _create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """Utility to test database connectivity status and dialect."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "dialect": engine.dialect.name,
            "mode": active_db_type,
        }
    except Exception as exc:
        return {
            "status": "disconnected",
            "error": str(exc),
            "mode": active_db_type,
        }
