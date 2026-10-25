"""Unit tests for Phase 3B Dashboard Backend: WebSocket tickets, list/detail APIs, stats, and CORS."""
from datetime import datetime, timezone
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.models import AuditLog, Mandate, MandatePeriod, MandateStatus, PaymentIntent, PaymentIntentStatus, WebhookEvent

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

OPERATOR_TOKEN = "test-operator-dashboard-backend"


@pytest.fixture(autouse=True)
def setup_test_settings(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_TOKEN", OPERATOR_TOKEN)
    yield


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        await session.execute(delete(AuditLog))
        await session.execute(delete(WebhookEvent))
        await session.execute(delete(PaymentIntent))
        await session.execute(delete(Mandate))
        await session.commit()
        yield session
        await session.execute(delete(AuditLog))
        await session.execute(delete(WebhookEvent))
        await session.execute(delete(PaymentIntent))
        await session.execute(delete(Mandate))
        await session.commit()
    await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def operator_headers():
    return {"Authorization": f"Bearer {OPERATOR_TOKEN}"}


def _make_mandate(mid: str, agent_id: str = "agent-1", status: MandateStatus = MandateStatus.ACTIVE):
    now = datetime.now(timezone.utc)
    return Mandate(
        mandate_id=mid,
        agent_id=agent_id,
        budget_total=10000,
        per_transaction_cap=5000,
        allowlist_merchants=["merchant@test.com", "vendor@test.com"],
        allowed_currencies=["USD"],
        period="lifetime",
        valid_from=now,
        valid_until=now,
        status=status,
    )


@pytest.mark.asyncio
async def test_ws_ticket_creation_and_expiry(client, operator_headers):
    """POST /ws/ticket returns a random ticket with expiry and stores in Redis with 60s TTL."""
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.close = AsyncMock()

    with patch("app.api.websocket._get_redis", return_value=mock_redis):
        resp = await client.post("/ws/ticket", headers=operator_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "ticket" in data
        assert len(data["ticket"]) == 64
        assert "expires_at" in data

        key = f"apf:ws:ticket:{data['ticket']}"
        mock_redis.set.assert_called_once_with(key, "1", ex=60)


@pytest.mark.asyncio
async def test_ws_ticket_requires_operator_auth(client):
    """POST /ws/ticket requires operator bearer token."""
    resp = await client.post("/ws/ticket")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cors_headers(client):
    """CORS middleware allows DASHBOARD_ORIGIN with Authorization and blocks unknown origins."""
    resp_allowed = await client.options(
        "/intents",
        headers={
            "Origin": settings.DASHBOARD_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert resp_allowed.headers.get("access-control-allow-origin") == settings.DASHBOARD_ORIGIN

    resp_blocked = await client.options(
        "/intents",
        headers={
            "Origin": "http://evil-attacker.site",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_blocked.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_get_intents_pagination_and_filter(client, db_session, operator_headers):
    """GET /intents returns paginated results with total count and filter support."""
    m1 = _make_mandate("mandate-dash-1")
    m2 = _make_mandate("mandate-dash-2")
    db_session.add_all([m1, m2])
    await db_session.commit()

    i1 = PaymentIntent(
        mandate_id=m1.mandate_id,
        idempotency_key="key-dash-1",
        amount=1500,
        currency="USD",
        merchant="merchant@test.com",
        status=PaymentIntentStatus.APPROVED,
        decision_reasons=[],
    )
    i2 = PaymentIntent(
        mandate_id=m2.mandate_id,
        idempotency_key="key-dash-2",
        amount=3000,
        currency="USD",
        merchant="merchant@test.com",
        status=PaymentIntentStatus.ESCALATED,
        decision_reasons=[{"code": "THRESHOLD", "message": "High value"}],
    )
    db_session.add_all([i1, i2])
    await db_session.commit()

    resp = await client.get("/intents?page=1&page_size=10", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 10

    resp_filtered = await client.get("/intents?status=escalated", headers=operator_headers)
    assert resp_filtered.status_code == 200
    filtered_data = resp_filtered.json()
    assert filtered_data["total"] == 1
    for item in filtered_data["items"]:
        assert item["status"] == "escalated"


@pytest.mark.asyncio
async def test_get_intent_detail_includes_audit_events(client, db_session, operator_headers):
    """GET /intents/{id} includes risk_details and linked audit events."""
    m = _make_mandate("mandate-detail-parent")
    db_session.add(m)
    await db_session.commit()

    intent = PaymentIntent(
        mandate_id=m.mandate_id,
        idempotency_key="key-detail-1",
        amount=2500,
        currency="USD",
        merchant="store@detail.com",
        status=PaymentIntentStatus.DENIED,
        decision_reasons=[{"code": "RISK", "message": "blocked"}],
        risk_details={"canary": {"tripped": True}},
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    audit = AuditLog(
        intent_id=intent.id,
        event="intent.denied",
        payload={"reason": "risk policy"},
        prev_hash="0" * 64,
        hash="a" * 64,
    )
    db_session.add(audit)
    await db_session.commit()

    resp = await client.get(f"/intents/{intent.id}", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == intent.id
    assert data["risk_details"]["canary"]["tripped"] is True
    assert len(data["audit_events"]) == 1
    assert data["audit_events"][0]["event"] == "intent.denied"


@pytest.mark.asyncio
async def test_stats_endpoint(client, db_session, operator_headers):
    """GET /intents/stats returns aggregated metrics across mandates and intents."""
    m_active = _make_mandate("m-stat-active", status=MandateStatus.ACTIVE)
    m_frozen = _make_mandate("m-stat-frozen", status=MandateStatus.FROZEN)
    db_session.add_all([m_active, m_frozen])
    await db_session.commit()

    with patch("app.services.budget.budget_service.get_balances", return_value={"spent": 2000, "reserved": 1000}):
        resp = await client.get("/intents/stats", headers=operator_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "by_status" in data
        assert "total_spent_cents" in data
        assert "total_reserved_cents" in data
        assert "total_remaining_cents" in data
        assert "escalations_pending" in data
        assert "frozen_mandates" in data
        assert data["frozen_mandates"] == 1
        assert "last_24h_decisions" in data


@pytest.mark.asyncio
async def test_audit_pagination_returns_total(client, db_session, operator_headers):
    """GET /audit returns paginated structure with total count."""
    audit = AuditLog(
        intent_id=None,
        event="system.init",
        payload={"info": "started"},
        prev_hash="0" * 64,
        hash="b" * 64,
    )
    db_session.add(audit)
    await db_session.commit()

    resp = await client.get("/audit?limit=10&offset=0", headers=operator_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 1
