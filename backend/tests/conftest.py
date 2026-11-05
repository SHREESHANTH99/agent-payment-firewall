"""Test process isolation: never inherit developer credentials or execution mode."""
import os

# Loaded by pytest before test modules import application settings. Environment values
# take precedence over Settings.env_file, keeping a local .env out of test behavior.
os.environ.update({
    "EXECUTION_MODE": "paypal",
    "PAYPAL_MODE": "sandbox",
    "PAYPAL_CLIENT_ID": "test-client-id",
    "PAYPAL_CLIENT_SECRET": "test-client-secret",
    "PAYPAL_WEBHOOK_ID": "test-webhook-id",
    "OPERATOR_TOKEN": "test-operator-token",
    "AGENT_API_KEYS": "{}",
    "LLM_API_KEY": "",
    "LLM_FALLBACK_API_KEY": "",
})

import pytest
import pytest_asyncio
from app.core.database import engine, Base

@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_test_db():
    """Ensure database schema is created before tests run."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
