"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama3-70b-8192"
    groq_timeout: float = 30.0
    groq_max_retries: int = 3

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://market_agent:changeme@localhost:5432/market_agent"

    # ── SMTP ──────────────────────────────────────────────────────────────────
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_tls: bool = False   # set True for STARTTLS (e.g. Gmail port 587)
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    # ── Watchlist ─────────────────────────────────────────────────────────────
    watchlist: Annotated[list[str], Field(default_factory=lambda: ["SPY", "QQQ", "IWM", "VTI", "XLK", "XLF", "XLE"])]

    @field_validator("watchlist", mode="before")
    @classmethod
    def parse_watchlist(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [t.strip().upper() for t in v.split(",") if t.strip()]
        return v  # type: ignore[return-value]

    # ── Timezone ──────────────────────────────────────────────────────────────
    timezone: str = "America/New_York"


# Module-level singleton — re-use everywhere with `from market_agent.config import settings`
settings = Settings()
