"""Tests for agent-facing response detail filtering (AGENT_RESPONSE_DETAIL minimal vs full)."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api.intents import router
from app.core.config import settings
from app.core.security import agent_auth, operator_auth
from app.core.database import get_db

app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_agent_response_detail_minimal_strips_risk():
    """When AGENT_RESPONSE_DETAIL=minimal, POST /intents response contains empty risk and sanitized reasons."""
    pipeline_result = {
        "intent_id": "pi_12345",
        "decision": "denied",
        "status": "denied",
        "reasons": [
            {
                "code": "CANARY_TRIPPED",
                "message": "Canary token breached honeypot",
                "internal_detail": "Secret canary leak string"
            }
        ],
        "risk": {
            "canary": {"tripped": True, "honeypot_calls": ["execute_transfer"]},
            "judge": {"verdict": "deny", "reason": "Adversarial prompt injection detected", "confidence": 0.99}
        },
        "dry_run": True,
    }

    async def override_agent_auth():
        return "test-agent"

    async def override_get_db():
        yield None

    app.dependency_overrides[agent_auth] = override_agent_auth
    app.dependency_overrides[get_db] = override_get_db

    with patch.object(settings, "AGENT_RESPONSE_DETAIL", "minimal"), \
         patch("app.api.intents.process_intent", new=AsyncMock(return_value=pipeline_result)), \
         patch("app.api.intents.check_rate_limit", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/intents", json={
                "idempotency_key": "idemp-001",
                "mandate_id": "mand_001",
                "amount": "10.00",
                "currency": "USD",
                "merchant": "merchant@example.com"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["intent_id"] == "pi_12345"
            assert data["decision"] == "denied"
            assert data["status"] == "denied"
            # Risk dictionary MUST be stripped/empty
            assert data["risk"] == {}
            # Sensitive internal keys removed from reasons
            assert data["reasons"] == [{"code": "CANARY_TRIPPED", "message": "Canary token breached honeypot"}]
            assert data["dry_run"] is True


@pytest.mark.asyncio
async def test_agent_response_detail_full_preserves_risk():
    """When AGENT_RESPONSE_DETAIL=full (evaluation mode), POST /intents returns full risk diagnostics."""
    pipeline_result = {
        "intent_id": "pi_67890",
        "decision": "denied",
        "status": "denied",
        "reasons": [{"code": "JUDGE_FLAGGED", "message": "Prompt injection suspected"}],
        "risk": {
            "canary": {"tripped": False},
            "judge": {"verdict": "deny", "confidence": 0.95, "reason": "Adversarial override"}
        },
        "dry_run": True,
    }

    async def override_agent_auth():
        return "test-agent"

    async def override_get_db():
        yield None

    app.dependency_overrides[agent_auth] = override_agent_auth
    app.dependency_overrides[get_db] = override_get_db

    with patch.object(settings, "AGENT_RESPONSE_DETAIL", "full"), \
         patch("app.api.intents.process_intent", new=AsyncMock(return_value=pipeline_result)), \
         patch("app.api.intents.check_rate_limit", new=AsyncMock()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/intents", json={
                "idempotency_key": "idemp-002",
                "mandate_id": "mand_002",
                "amount": "25.00",
                "currency": "USD",
                "merchant": "merchant@example.com"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["intent_id"] == "pi_67890"
            assert data["decision"] == "denied"
            # Full risk diagnostics preserved
            assert data["risk"]["judge"]["confidence"] == 0.95
            assert data["risk"]["canary"]["tripped"] is False
            assert data["dry_run"] is True
