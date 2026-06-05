"""
Ignite Compensation Engine — Configuration
India market only. All monetary values in INR (₹).
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://ignite_user:password@localhost:5432/ignite_engine"
    DATABASE_URL_SYNC: str = "postgresql://ignite_user:password@localhost:5432/ignite_engine"

    # ── JWT Auth ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE-THIS-IN-PRODUCTION-USE-STRONG-RANDOM-KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── External integrations ─────────────────────────────────────────────
    ECOMMERCE_API: str = "https://mock-ecom.example.com/api"
    ECOMMERCE_API_KEY: str = "mock-key"
    CRM_API: str = "https://mock-crm.example.com/api"
    CRM_API_KEY: str = "mock-key"

    # ── India compliance (all INR) ─────────────────────────────────────────
    TDS_RATE: float = 0.05                    # Section 194H — 5%
    TDS_THRESHOLD_INR: int = 15_000           # ₹15,000 per FY before TDS kicks in
    GST_REGISTRATION_THRESHOLD_INR: int = 20_00_000  # ₹20L turnover
    INR_ROUNDING: int = 500                   # Round commissions to nearest ₹500

    # ── Plan constants (defaults; overridden per cycle by rank_config) ─────
    CV_PER_STEP: int = 1800
    FIRST_STEP_HALF_RATE: bool = True         # First 2 lifetime steps at 50% rate
    COIN_LIFETIME_CAP: int = 12              # Green coins max per BA lifetime
    YELLOW_COIN_STEP_INTERVAL: int = 6        # 1 yellow coin every 6 cumulative steps
    FLUSH_RATIO: float = 3.0                  # Strong leg flushed at flush_ratio × weak leg

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Ignite Compensation Engine"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
