"""Application configuration using pydantic-settings."""
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

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
