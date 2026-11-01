"""Unit tests for Phase 4 Part 1: GET /agent/mandate and EXECUTION_MODE dry_run."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.main import app
from app.models.models import Mandate, MandateStatus, PaymentIntent, PaymentIntentStatus
from app.services.execution import execute_intent


@pytest.fixture(autouse=True)
def setup_agent_keys(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_API_KEYS", {"test-secret-key-1": "demo-agent"})


@pytest.mark.asyncio
async def test_get_agent_mandate_missing_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/agent/mandate")
        assert resp.status_code == 401
        assert "Missing X-Agent-Key header" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_agent_mandate_invalid_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/agent/mandate", headers={"X-Agent-Key": "wrong-key"})
        assert resp.status_code == 401
        assert "Invalid X-Agent-Key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_agent_mandate_not_found(monkeypatch):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/agent/mandate", headers={"X-Agent-Key": "test-secret-key-1"})
            assert resp.status_code == 404
            assert "No active mandate found" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_agent_mandate_expired(monkeypatch):
    mock_db = AsyncMock()
    past_date = datetime.now(timezone.utc) - timedelta(days=1)
    mock_mandate = Mandate(
        mandate_id="mandate-test-1",
        agent_id="demo-agent",
        budget_total=10000,
        per_transaction_cap=5000,
        escalation_threshold=4000,
        allowed_currencies=["USD"],
        allowlist_merchants=["seller@example.com"],
        valid_from=datetime.now(timezone.utc) - timedelta(days=2),
        valid_until=past_date,
        period="lifetime",
        status=MandateStatus.ACTIVE.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_mandate
    mock_db.execute.return_value = mock_result

    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/agent/mandate", headers={"X-Agent-Key": "test-secret-key-1"})
            assert resp.status_code == 404
            assert "expired" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_agent_mandate_success(monkeypatch):
    mock_db = AsyncMock()
    future_date = datetime.now(timezone.utc) + timedelta(days=7)
    mock_mandate = Mandate(
        mandate_id="mandate-test-active",
        agent_id="demo-agent",
        budget_total=10000,
        per_transaction_cap=5000,
        escalation_threshold=4000,
        allowed_currencies=["USD"],
        allowlist_merchants=["seller@example.com", "seller2@example.com"],
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        valid_until=future_date,
        period="lifetime",
        status=MandateStatus.ACTIVE.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_mandate
    mock_db.execute.return_value = mock_result

    # Mock budget balances
    with patch("app.api.agent.budget_service.get_balances", new_callable=AsyncMock) as mock_get_balances:
        mock_get_balances.return_value = {"spent": 2000, "reserved": 1000}

        from app.core.database import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/agent/mandate", headers={"X-Agent-Key": "test-secret-key-1"})
                assert resp.status_code == 200
                data = resp.json()
                assert data["mandate_id"] == "mandate-test-active"
                # 10000 - 2000 - 1000 = 7000 cents -> 70.00
                assert data["remaining"] == "70.00"
                assert data["per_transaction_cap"] == "50.00"
                assert data["escalation_threshold"] == "40.00"
                assert data["allowed_currencies"] == ["USD"]
                assert "seller@example.com" in data["allowlist_merchants"]
                assert "seller2@example.com" in data["allowlist_merchants"]
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_dry_run_execution(monkeypatch):
    monkeypatch.setattr(settings, "EXECUTION_MODE", "dry_run")

    mock_session = AsyncMock()
    mock_intent = PaymentIntent(
        id="intent-test-dry-run-123",
        mandate_id="mandate-test-active",
        idempotency_key="idemp-key-123",
        amount=2500,
        currency="USD",
        merchant="seller@example.com",
        description="Office supplies",
        status=PaymentIntentStatus.APPROVED,
    )

    with patch("app.services.execution.budget_service.commit", new_callable=AsyncMock) as mock_commit, \
         patch("app.services.execution.append_event", new_callable=AsyncMock) as mock_append:

        executed_intent = await execute_intent(mock_intent, mock_session)

        assert executed_intent.status == PaymentIntentStatus.EXECUTED
        assert executed_intent.paypal_ref == "dry-run-intent-test-dry-run-123"
        mock_commit.assert_awaited_once_with("intent-test-dry-run-123")
        mock_append.assert_awaited_once()
        event_call = mock_append.call_args[1]
        assert event_call["event"] == "intent.executed"
        assert event_call["payload"]["dry_run"] is True
