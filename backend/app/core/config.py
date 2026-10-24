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
