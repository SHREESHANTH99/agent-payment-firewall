"""Application configuration using pydantic-settings."""
import json
from typing import Any, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment or .env file."""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/firewall"
    REDIS_URL: str = "redis://localhost:6379/0"
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_MODE: str = "sandbox"
    PAYPAL_TEST_RECEIVER_EMAIL: str = "sb-receiver@personal.example.com"
    ESCALATION_TIMEOUT_SECONDS: int = 600
    OPERATOR_TOKEN: str = "dev-operator-secret-token"
    AGENT_API_KEYS: dict[str, str] = {}

    # LLM & AI Risk Layer Configuration
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    CANARY_MODEL: str = "gpt-4o-mini"
    JUDGE_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 15
    JUDGE_FAIL_MODE: str = "escalate"  # escalate | deny
    CANARY_ENABLED: bool = True
    JUDGE_ENABLED: bool = True
    LLM_CACHE_ENABLED: bool = True
    LLM_CACHE_TTL_SECONDS: int = 600
    LLM_CACHE_MAX_ENTRIES: int = 500
    LLM_FALLBACK_BASE_URL: str = ""
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_MODEL: str = ""
    DASHBOARD_ORIGIN: str = "http://localhost:3000"

    @field_validator("AGENT_API_KEYS", mode="before")
    @classmethod
    def parse_agent_api_keys(cls, v: Any) -> dict[str, str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return {}
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return {str(k): str(val) for k, val in parsed.items()}
            except Exception:
                return {}
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        return {}

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
