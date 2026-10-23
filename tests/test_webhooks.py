"""Tests for PayPal webhook verification, deduplication, and handling."""
import json
from typing import Any
import pytest
import respx
import httpx
from sqlalchemy import delete, select
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.models import WebhookEvent
from app.paypal.auth import clear_token_cache

MOCK_HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-12345",
    "PAYPAL-TRANSMISSION-ID": "tx-id-9999",
    "PAYPAL-TRANSMISSION-SIG": "mock_signature_base64_string",
    "PAYPAL-TRANSMISSION-TIME": "2026-10-23T16:00:00Z",
}

MOCK_PAYOUT_EVENT = {
    "id": "WH-TEST-EVENT-001",
    "event_version": "1.0",
    "create_time": "2026-10-23T16:00:00Z",
    "resource_type": "payouts_item",
    "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
    "summary": "Payout item succeeded",
    "resource": {
        "payout_item_id": "ITEM-111",
        "payout_batch_id": "BATCH-222",
        "sender_batch_id": "SENDER-BATCH-333",
        "transaction_status": "SUCCESS",
    },
}

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest.fixture(autouse=True)
def setup_webhook_settings(monkeypatch):
    """Ensure PAYPAL_WEBHOOK_ID is set for tests and cache is cleared."""
    clear_token_cache()
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "TEST_WEBHOOK_ID_123")
    yield
    clear_token_cache()


@pytest.fixture
async def db_session():
    """Provide a real database session and clean up webhook_events table."""
    async with TestSessionLocal() as session:
        await session.execute(delete(WebhookEvent))
        await session.commit()
        yield session
        await session.execute(delete(WebhookEvent))
        await session.commit()
    await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession):
    """Create test client with database dependency override."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_webhook_valid_signature_success(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that a valid webhook returns 200, stores the event, and marks processed=True."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token", "token_type": "Bearer", "expires_in": 3600},
    )
    respx.post("https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature").respond(
        status_code=200,
        json={"verification_status": "SUCCESS"},
    )

    body_bytes = json.dumps(MOCK_PAYOUT_EVENT).encode("utf-8")
    response = await client.post(
        "/webhooks/paypal",
        headers=MOCK_HEADERS,
        content=body_bytes,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify event stored and processed in database
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == "WH-TEST-EVENT-001")
    result = await db_session.execute(stmt)
    event = result.scalar_one_or_none()

    assert event is not None
    assert event.event_type == "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"
    assert event.processed is True
    assert event.resource["payout_batch_id"] == "BATCH-222"


@pytest.mark.asyncio
@respx.mock
async def test_webhook_verification_status_failure(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that verification_status FAILURE returns 400 and stores nothing."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token", "token_type": "Bearer", "expires_in": 3600},
    )
    respx.post("https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature").respond(
        status_code=200,
        json={"verification_status": "FAILURE"},
    )

    body_bytes = json.dumps(MOCK_PAYOUT_EVENT).encode("utf-8")
    response = await client.post(
        "/webhooks/paypal",
        headers=MOCK_HEADERS,
        content=body_bytes,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid signature"

    # Verify nothing was stored
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == "WH-TEST-EVENT-001")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_webhook_missing_header_returns_400(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that a missing PAYPAL-* header returns 400 and stores nothing."""
    incomplete_headers = dict(MOCK_HEADERS)
    del incomplete_headers["PAYPAL-TRANSMISSION-SIG"]

    body_bytes = json.dumps(MOCK_PAYOUT_EVENT).encode("utf-8")
    response = await client.post(
        "/webhooks/paypal",
        headers=incomplete_headers,
        content=body_bytes,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid signature"

    # Verify nothing stored
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == "WH-TEST-EVENT-001")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_webhook_empty_webhook_id_returns_400(client: httpx.AsyncClient, monkeypatch):
    """Verify that an empty PAYPAL_WEBHOOK_ID returns 400."""
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "")

    body_bytes = json.dumps(MOCK_PAYOUT_EVENT).encode("utf-8")
    response = await client.post(
        "/webhooks/paypal",
        headers=MOCK_HEADERS,
        content=body_bytes,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid signature"


@pytest.mark.asyncio
@respx.mock
async def test_webhook_duplicate_event_id(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that duplicate webhook event returns 200 duplicate and only stores one row."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token", "token_type": "Bearer", "expires_in": 3600},
    )
    respx.post("https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature").respond(
        status_code=200,
        json={"verification_status": "SUCCESS"},
    )

    body_bytes = json.dumps(MOCK_PAYOUT_EVENT).encode("utf-8")

    # First delivery
    resp1 = await client.post("/webhooks/paypal", headers=MOCK_HEADERS, content=body_bytes)
    assert resp1.status_code == 200
    assert resp1.json() == {"status": "ok"}

    # Duplicate delivery
    resp2 = await client.post("/webhooks/paypal", headers=MOCK_HEADERS, content=body_bytes)
    assert resp2.status_code == 200
    assert resp2.json() == {"status": "duplicate"}

    # Ensure exactly 1 row exists
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == "WH-TEST-EVENT-001")
    result = await db_session.execute(stmt)
    events = result.scalars().all()
    assert len(events) == 1


@pytest.mark.asyncio
@respx.mock
async def test_webhook_paypal_verify_500_returns_400(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that a 500 error from PayPal verification endpoint returns 400."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token", "token_type": "Bearer", "expires_in": 3600},
    )
    respx.post("https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature").respond(
        status_code=500,
        text="Internal Server Error",
    )

    body_bytes = json.dumps(MOCK_PAYOUT_EVENT).encode("utf-8")
    response = await client.post(
        "/webhooks/paypal",
        headers=MOCK_HEADERS,
        content=body_bytes,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid signature"

    # Verify nothing stored
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == "WH-TEST-EVENT-001")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
@respx.mock
async def test_webhook_unknown_event_type_stored_and_acknowledged(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify that unknown event types are stored with processed=False and return 200 ok."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token", "token_type": "Bearer", "expires_in": 3600},
    )
    respx.post("https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature").respond(
        status_code=200,
        json={"verification_status": "SUCCESS"},
    )

    unknown_event = {
        "id": "WH-TEST-UNKNOWN-999",
        "event_version": "1.0",
        "create_time": "2026-10-23T16:00:00Z",
        "resource_type": "dispute",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "summary": "Customer opened a dispute",
        "resource": {"dispute_id": "DISPUTE-999"},
    }

    body_bytes = json.dumps(unknown_event).encode("utf-8")
    response = await client.post(
        "/webhooks/paypal",
        headers=MOCK_HEADERS,
        content=body_bytes,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify event was stored with processed=False
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == "WH-TEST-UNKNOWN-999")
    result = await db_session.execute(stmt)
    event = result.scalar_one_or_none()

    assert event is not None
    assert event.event_type == "CUSTOMER.DISPUTE.CREATED"
    assert event.processed is False
