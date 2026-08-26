"""Database engine, session management, and connection utilities."""
import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings, BASE_DIR

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy ORM models
Base = declarative_base()

def _normalize_sqlite_url(db_url: str) -> str:
    """Ensure relative SQLite file paths resolve consistently to BASE_DIR."""
    if not db_url.startswith("sqlite:///"):
        return db_url
    path_part = db_url[len("sqlite:///"):]
    if path_part in (":memory:", ""):
        return db_url
    p = Path(path_part)
    if not p.is_absolute():
        resolved_path = (BASE_DIR / p).resolve()
        return f"sqlite:///{resolved_path}"
    return db_url


def _create_database_engine():
    """Create SQLAlchemy engine with automatic fallback for seamless local developer onboarding."""
    raw_db_url = settings.DATABASE_URL
    is_sqlite = raw_db_url.startswith("sqlite")
    db_url = _normalize_sqlite_url(raw_db_url) if is_sqlite else raw_db_url
    
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    extra_engine_args = {}
    if is_sqlite and (":memory:" in db_url or db_url == "sqlite://"):
        from sqlalchemy.pool import StaticPool
        extra_engine_args["poolclass"] = StaticPool
    
    try:
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
            **extra_engine_args,
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
            fallback_db_path = BASE_DIR / "recoverai_local.db"
            fallback_url = f"sqlite:///{fallback_db_path.resolve()}"
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
    except Exception:
        db.rollback()
        raise
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
