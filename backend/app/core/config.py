"""Application settings and environment configuration."""
import os
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate root directory containing .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env" if (ROOT_DIR / ".env").exists() else BASE_DIR / ".env"


class Settings(BaseSettings):
    """Central application settings parsed from environment variables."""

    # App Identity
    APP_NAME: str = "RecoverAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    VERSION: str = "0.1.0"

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/recoverai"
    DATABASE_FALLBACK_SQLITE: bool = True

    # Razorpay (Test Mode)
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_key"
    RAZORPAY_KEY_SECRET: str = "placeholder_secret_key"
    RAZORPAY_WEBHOOK_SECRET: str = "placeholder_webhook_secret"
    RAZORPAY_MODE: str = "test"

    # AI / LLM Configuration
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: str = "mock_key"
    LLM_MODEL: str = "gemini-1.5-pro"
    LLM_TEMPERATURE: float = 0.2

    # Policy Engine Defaults
    MAX_RECOVERY_RETRIES: int = 3
    MIN_RECOVERY_CONFIDENCE: float = 0.60
    AUTO_RECOVERY_THRESHOLD_INR: float = 50000.0

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
