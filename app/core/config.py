"""
Application Configuration
Secure enterprise laptop asset management system
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from pathlib import Path
import secrets
import os

# Get the directory where config.py is located
CONFIG_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CONFIG_DIR.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Trace - Enterprise Asset Management"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Agent Authentication
    AGENT_TOKEN_EXPIRE_DAYS: int = 365
    AGENT_SECRET_KEY: str = secrets.token_urlsafe(32)
    
    # Database - supports DATABASE_URL, Vercel POSTGRES_URL, and Neon
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/trace_db"
    POSTGRES_URL: Optional[str] = None  # Vercel Postgres
    NEON_DATABASE_URL: Optional[str] = None  # Neon Postgres
    DATABASE_ECHO: bool = False
    
    @model_validator(mode='after')
    def configure_database_url(self):
        """Use cloud database URL if available (Neon or Vercel Postgres)"""
        # Priority: NEON_DATABASE_URL > POSTGRES_URL > DATABASE_URL
        url = self.NEON_DATABASE_URL or self.POSTGRES_URL
        if url:
            # Convert postgres:// to postgresql+asyncpg://
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            # Add SSL mode for Neon (required)
            if "neon.tech" in url and "sslmode" not in url:
                url = url + ("&" if "?" in url else "?") + "sslmode=require"
            self.DATABASE_URL = url
        return self
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://trace.yourdomain.com"]
    
    # Encryption
    ENCRYPTION_KEY: str = secrets.token_urlsafe(32)
    
    # Geofencing
    DEFAULT_GEOFENCE_RADIUS_METERS: int = 1000
    
    # Data Retention (days)
    LOCATION_DATA_RETENTION_DAYS: int = 90
    AUDIT_LOG_RETENTION_DAYS: int = 365
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    AGENT_PING_INTERVAL_SECONDS: int = 300  # 5 minutes
    
    # Privacy
    GDPR_ENABLED: bool = True
    CONSENT_REQUIRED: bool = True
    
    # Initial Super Admin
    FIRST_SUPERUSER: Optional[str] = None
    FIRST_SUPERUSER_PASSWORD: Optional[str] = None
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle both JSON array and comma-separated formats
            if v.startswith("["):
                import json
                return json.loads(v)
            return [origin.strip() for origin in v.split(",")]
        return v
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
