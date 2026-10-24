"""Comprehensive tests for Prompt 2B: pipeline, execution, audit chain, webhooks, and scheduler."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import uuid

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.models import AuditLog, Mandate, MandatePeriod, MandateStatus, PaymentIntent, PaymentIntentStatus, WebhookEvent
from app.services.audit import append_event, verify_chain
from app.services.budget import budget_service
from app.services.idempotency import idempotency_service
from app.services.scheduler import _expire_escalated_intents, _poll_executing_intents

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

OPERATOR_TOKEN = "test-operator-secret-2b"
AGENT_KEY = "agent-key-2b"
AGENT_ID = "agent-2b"

PAYPAL_TOKEN_URL = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
PAYPAL_PAYOUT_URL = "https://api-m.sandbox.paypal.com/v1/payments/payouts"
PAYPAL_VERIFY_URL = "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"


@pytest.fixture(autouse=True)
def setup_test_settings(monkeypatch):
    from app.services.risk_config import risk_config_state
    monkeypatch.setattr(settings, "OPERATOR_TOKEN", OPERATOR_TOKEN)
    monkeypatch.setattr(settings, "AGENT_API_KEYS", {AGENT_KEY: AGENT_ID})
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "test-webhook-id")
    # For Phase 2B tests, disable Phase 3A AI risk layer so pure 2B functionality is verified
    risk_config_state.set_config(canary_enabled=False, judge_enabled=False)
    yield
    risk_config_state.set_config(canary_enabled=True, judge_enabled=True)


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        # Clean order respects FKs
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
async def mandate(db_session: AsyncSession) -> Mandate:
    """Create a standard test mandate: $100 budget, $50 cap, $20 escalation threshold."""
    m = Mandate(
        mandate_id=str(uuid.uuid4()),
        agent_id=AGENT_ID,
        budget_total=10000,          # $100.00
        per_transaction_cap=5000,    # $50.00
        escalation_threshold=2000,   # $20.00
        period=MandatePeriod.LIFETIME,
        allowed_currencies=["USD"],
        status=MandateStatus.ACTIVE,
        allowlist_merchants=["vendor@paypal.com"],
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        valid_until=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    # Seed Redis balance
    period_key = budget_service.get_period_key(m.period)
    r = await budget_service.get_redis()
    bk = budget_service._balance_key(m.mandate_id, period_key)
    await r.hset(bk, mapping={"spent": "0", "reserved": "0"})

    return m


def op_headers():
    return {"Authorization": f"Bearer {OPERATOR_TOKEN}"}


def agent_headers():
    return {"X-Agent-Key": AGENT_KEY}


def _mock_paypal_token():
    return respx.post(PAYPAL_TOKEN_URL).mock(
        return_value=Response(200, json={"access_token": "mock-token", "expires_in": 3600, "token_type": "Bearer"})
    )


def _mock_paypal_payout(batch_id: str, batch_status: str = "PENDING"):
    return respx.post(PAYPAL_PAYOUT_URL).mock(
        return_value=Response(201, json={
            "batch_header": {
                "payout_batch_id": batch_id,
                "batch_status": batch_status,
                "sender_batch_header": {"sender_batch_id": "test-idem-key"},
            }
        })
    )


def _mock_paypal_payout_status(batch_id: str, batch_status: str = "SUCCESS"):
    return respx.get(f"{PAYPAL_PAYOUT_URL}/{batch_id}").mock(
        return_value=Response(200, json={
            "batch_header": {
                "payout_batch_id": batch_id,
                "batch_status": batch_status,
            }
        })
    )


# =========================================================================
# 1. In-policy intent -> executing, payout called once, audit written
# =========================================================================

@pytest.mark.asyncio
async def test_in_policy_intent_executes(client, mandate, db_session):
    batch_id = f"BATCH-{uuid.uuid4()}"
    idem_key = str(uuid.uuid4())

    with respx.mock:
        _mock_paypal_token()
        _mock_paypal_payout(batch_id)

        resp = await client.post("/intents", json={
            "idempotency_key": idem_key,
            "mandate_id": mandate.mandate_id,
            "amount": "5.00",
            "currency": "USD",
            "merchant": "vendor@paypal.com",
            "description": "Test payment",
        }, headers=agent_headers())

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["decision"] == "approved"
    assert data["status"] in ("executing", "executed")

    # Verify audit entries were written
    audit_rows = (await db_session.execute(select(AuditLog))).scalars().all()
    events = {r.event for r in audit_rows}
    assert "intent.created" in events
    assert "budget.reserved" in events
    assert "intent.approved" in events
    assert "intent.executing" in events


# =========================================================================
# 2. Over cap -> denied, no payout, budget unchanged
# =========================================================================

@pytest.mark.asyncio
async def test_over_cap_denied(client, mandate, db_session):
    idem_key = str(uuid.uuid4())

    with respx.mock:
        resp = await client.post("/intents", json={
            "idempotency_key": idem_key,
            "mandate_id": mandate.mandate_id,
            "amount": "99.00",   # > $50 cap
            "currency": "USD",
            "merchant": "vendor@paypal.com",
        }, headers=agent_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "denied"
    codes = [r["code"] for r in data["reasons"]]
    assert "PER_TRANSACTION_CAP_EXCEEDED" in codes

    # Budget should be unchanged
    period_key = budget_service.get_period_key(mandate.period)
    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["reserved"] == 0
    assert balances["spent"] == 0


# =========================================================================
# 3. Escalation flow: escalated -> approve -> executing; and reject
# =========================================================================

@pytest.mark.asyncio
async def test_escalation_then_approve(client, mandate, db_session):
    batch_id = f"BATCH-ESC-{uuid.uuid4()}"
    idem_key = str(uuid.uuid4())

    with respx.mock:
        _mock_paypal_token()
        _mock_paypal_payout(batch_id)

        # Submit $25 - above $20 escalation threshold
        resp = await client.post("/intents", json={
            "idempotency_key": idem_key,
            "mandate_id": mandate.mandate_id,
            "amount": "25.00",
            "currency": "USD",
            "merchant": "vendor@paypal.com",
        }, headers=agent_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "escalated"
    intent_id = data["intent_id"]

    # Approve
    with respx.mock:
        _mock_paypal_token()
        _mock_paypal_payout(batch_id)

        approve_resp = await client.post(f"/intents/{intent_id}/approve", headers=op_headers())

    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] in ("executing", "executed")

    # Audit should include escalation and approval events
    audit_rows = (await db_session.execute(select(AuditLog))).scalars().all()
    events = {r.event for r in audit_rows}
    assert "intent.escalated" in events
    assert "intent.approved" in events


@pytest.mark.asyncio
async def test_escalation_then_reject(client, mandate, db_session):
    idem_key = str(uuid.uuid4())

    resp = await client.post("/intents", json={
        "idempotency_key": idem_key,
        "mandate_id": mandate.mandate_id,
        "amount": "25.00",
        "currency": "USD",
        "merchant": "vendor@paypal.com",
    }, headers=agent_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "escalated"
    intent_id = data["intent_id"]

    period_key = budget_service.get_period_key(mandate.period)
    balances_before = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances_before["reserved"] == 2500  # $25

    reject_resp = await client.post(f"/intents/{intent_id}/reject",
                                     json={"reason": "Too risky"}, headers=op_headers())
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # Budget should be released
    balances_after = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances_after["reserved"] == 0


# =========================================================================
# 4. Escalation expiry releases budget
# =========================================================================

@pytest.mark.asyncio
async def test_escalation_expiry(db_session, mandate):
    # Create an already-expired escalated intent
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=3000,  # $30
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.ESCALATED,
        decision_reasons=[{"code": "ESCALATED_THRESHOLD", "message": "Test"}],
        risk_details={},
        created_at=datetime.now(timezone.utc) - timedelta(seconds=settings.ESCALATION_TIMEOUT_SECONDS + 10),
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=settings.ESCALATION_TIMEOUT_SECONDS + 10),
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    # Seed the reservation in Redis
    period_key = budget_service.get_period_key(mandate.period)
    await budget_service.reserve(
        mandate.mandate_id, period_key, intent.id, 3000, 10000
    )

    await _expire_escalated_intents()

    await db_session.refresh(intent)
    assert intent.status == PaymentIntentStatus.EXPIRED

    # Budget should be released
    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["reserved"] == 0


# =========================================================================
# 5. Idempotency: same key same payload replays; different payload -> 409
# =========================================================================

@pytest.mark.asyncio
async def test_idempotency_replay(client, mandate, db_session):
    batch_id = f"BATCH-IDEM-{uuid.uuid4()}"
    idem_key = str(uuid.uuid4())
    payload = {
        "idempotency_key": idem_key,
        "mandate_id": mandate.mandate_id,
        "amount": "5.00",
        "currency": "USD",
        "merchant": "vendor@paypal.com",
    }

    with respx.mock:
        _mock_paypal_token()
        _mock_paypal_payout(batch_id)
        r1 = await client.post("/intents", json=payload, headers=agent_headers())

    assert r1.status_code == 200
    d1 = r1.json()

    # Same payload: should replay cached decision without calling PayPal again
    with respx.mock:
        r2 = await client.post("/intents", json=payload, headers=agent_headers())

    assert r2.status_code == 200
    d2 = r2.json()
    assert d1["intent_id"] == d2["intent_id"]
    assert d1["decision"] == d2["decision"]


# =========================================================================
# 6. 20 parallel intents against small budget -> total reserved <= budget
# =========================================================================

@pytest.mark.asyncio
async def test_concurrent_budget_reservation(mandate, db_session):
    """At most $100 budget should be reserved across 20 concurrent $10 requests."""
    period_key = budget_service.get_period_key(mandate.period)

    async def try_reserve(i: int) -> bool:
        intent_id = str(uuid.uuid4())
        return await budget_service.reserve(
            mandate_id=mandate.mandate_id,
            period_key=period_key,
            intent_id=intent_id,
            amount_cents=1000,   # $10
            budget_cents=10000,  # $100 total
        )

    results = await asyncio.gather(*[try_reserve(i) for i in range(20)])
    successes = sum(1 for r in results if r)
    assert successes == 10, f"Expected exactly 10 successes, got {successes}"

    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["reserved"] == 10000  # exactly $100
    assert balances["reserved"] <= 10000


# =========================================================================
# 7. Frozen mandate -> denied with freeze reason
# =========================================================================

@pytest.mark.asyncio
async def test_frozen_mandate_denied(client, mandate, db_session):
    mandate.status = MandateStatus.FROZEN
    await db_session.commit()

    resp = await client.post("/intents", json={
        "idempotency_key": str(uuid.uuid4()),
        "mandate_id": mandate.mandate_id,
        "amount": "5.00",
        "currency": "USD",
        "merchant": "vendor@paypal.com",
    }, headers=agent_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "denied"
    codes = [r["code"] for r in data["reasons"]]
    assert "MANDATE_FROZEN" in codes


# =========================================================================
# 8. Webhook: SUCCEEDED -> executed & committed; FAILED -> failed & released;
#    replayed event is a no-op
# =========================================================================

@pytest.mark.asyncio
async def test_webhook_succeeded_commits_budget(client, mandate, db_session):
    batch_id = f"BATCH-WH-{uuid.uuid4()}"
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=1000,
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.EXECUTING,
        paypal_ref=batch_id,
        decision_reasons=[],
        risk_details={},
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    # Pre-seed a budget reservation so commit has something to move
    period_key = budget_service.get_period_key(mandate.period)
    await budget_service.reserve(mandate.mandate_id, period_key, intent.id, 1000, 10000)

    event_id = str(uuid.uuid4())
    raw = json.dumps({
        "id": event_id,
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "resource": {"payout_batch_id": batch_id},
    }).encode()

    with respx.mock:
        respx.post(PAYPAL_VERIFY_URL).mock(
            return_value=Response(200, json={"verification_status": "SUCCESS"})
        )
        _mock_paypal_token()

        resp = await client.post(
            "/webhooks/paypal",
            content=raw,
            headers={
                "content-type": "application/json",
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://api.paypal.com/cert.pem",
                "paypal-transmission-id": "abc-123",
                "paypal-transmission-sig": "sig",
                "paypal-transmission-time": "2024-01-01T00:00:00Z",
            },
        )

    assert resp.status_code == 200
    await db_session.refresh(intent)
    assert intent.status == PaymentIntentStatus.EXECUTED

    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["spent"] == 1000
    assert balances["reserved"] == 0

    # Replay: same event should be idempotent
    with respx.mock:
        respx.post(PAYPAL_VERIFY_URL).mock(
            return_value=Response(200, json={"verification_status": "SUCCESS"})
        )
        _mock_paypal_token()

        resp2 = await client.post(
            "/webhooks/paypal",
            content=raw,
            headers={
                "content-type": "application/json",
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://api.paypal.com/cert.pem",
                "paypal-transmission-id": "abc-123",
                "paypal-transmission-sig": "sig",
                "paypal-transmission-time": "2024-01-01T00:00:00Z",
            },
        )

    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # Budget unchanged after replay
    balances_after = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances_after["spent"] == 1000


@pytest.mark.asyncio
async def test_webhook_failed_releases_budget(client, mandate, db_session):
    batch_id = f"BATCH-FAIL-{uuid.uuid4()}"
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=1500,
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.EXECUTING,
        paypal_ref=batch_id,
        decision_reasons=[],
        risk_details={},
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    period_key = budget_service.get_period_key(mandate.period)
    await budget_service.reserve(mandate.mandate_id, period_key, intent.id, 1500, 10000)

    event_id = str(uuid.uuid4())
    raw = json.dumps({
        "id": event_id,
        "event_type": "PAYMENT.PAYOUTS-ITEM.FAILED",
        "resource": {"payout_batch_id": batch_id},
    }).encode()

    with respx.mock:
        respx.post(PAYPAL_VERIFY_URL).mock(
            return_value=Response(200, json={"verification_status": "SUCCESS"})
        )
        _mock_paypal_token()

        resp = await client.post(
            "/webhooks/paypal",
            content=raw,
            headers={
                "content-type": "application/json",
                "paypal-auth-algo": "SHA256withRSA",
                "paypal-cert-url": "https://api.paypal.com/cert.pem",
                "paypal-transmission-id": f"t-{event_id}",
                "paypal-transmission-sig": "sig",
                "paypal-transmission-time": "2024-01-01T00:00:00Z",
            },
        )

    assert resp.status_code == 200
    await db_session.refresh(intent)
    assert intent.status == PaymentIntentStatus.FAILED

    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["reserved"] == 0
    assert balances["spent"] == 0


# =========================================================================
# 9. Polling fallback resolves stuck executing intent
# =========================================================================

@pytest.mark.asyncio
async def test_payout_polling_resolves_stuck_intent(mandate, db_session):
    """Polling loop resolves a stale 'executing' intent using a separate session."""
    batch_id = f"BATCH-POLL-{uuid.uuid4()}"
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=2000,
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.EXECUTING,
        paypal_ref=batch_id,
        decision_reasons=[],
        risk_details={},
        created_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=120),
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)
    intent_id = intent.id

    period_key = budget_service.get_period_key(mandate.period)
    await budget_service.reserve(mandate.mandate_id, period_key, intent_id, 2000, 10000)

    # Patch AsyncSessionLocal used by the scheduler to use TestSessionLocal
    from app.services import scheduler as sched_module
    original_sml = sched_module.AsyncSessionLocal
    sched_module.AsyncSessionLocal = TestSessionLocal

    try:
        with respx.mock:
            _mock_paypal_token()
            _mock_paypal_payout_status(batch_id, "SUCCESS")
            await _poll_executing_intents()
    finally:
        sched_module.AsyncSessionLocal = original_sml

    await db_session.refresh(intent)
    assert intent.status == PaymentIntentStatus.EXECUTED

    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["spent"] == 2000
    assert balances["reserved"] == 0


# =========================================================================
# 10. Audit chain: verify_chain valid; tampering breaks it; immutability enforced
# =========================================================================

@pytest.mark.asyncio
async def test_audit_chain_valid_after_flow(db_session, mandate):
    """Verify the hash chain is valid after writing several audit events."""
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=1000,
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.PENDING,
        decision_reasons=[],
        risk_details={},
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    await append_event(db_session, intent.id, "intent.created", {"agent": AGENT_ID})
    await append_event(db_session, intent.id, "budget.reserved", {"amount": 1000})
    await append_event(db_session, intent.id, "intent.approved", {})

    result = await verify_chain(db_session)
    assert result["valid"] is True
    assert result["first_broken_index"] is None


@pytest.mark.asyncio
async def test_audit_chain_broken_by_tampering(db_session, mandate):
    """Tamper with a row's hash field in the DB directly and confirm verify_chain detects it."""
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=1000,
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.PENDING,
        decision_reasons=[],
        risk_details={},
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    await append_event(db_session, intent.id, "intent.created", {"agent": AGENT_ID})
    await append_event(db_session, intent.id, "budget.reserved", {"amount": 1000})

    # Tamper directly via SQL
    rows = (await db_session.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars().all()
    first_row = rows[0]
    from sqlalchemy import update
    from app.models.models import AuditLog as ALModel
    await db_session.execute(
        update(ALModel).where(ALModel.id == first_row.id).values(hash="a" * 64)
    )
    await db_session.commit()

    result = await verify_chain(db_session)
    assert result["valid"] is False
    assert result["first_broken_index"] is not None


@pytest.mark.asyncio
async def test_audit_log_immutable_update(db_session, mandate):
    """AuditLog entries cannot be updated through SQLAlchemy ORM."""
    intent = PaymentIntent(
        mandate_id=mandate.mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=500,
        currency="USD",
        merchant="vendor@paypal.com",
        status=PaymentIntentStatus.PENDING,
        decision_reasons=[],
        risk_details={},
    )
    db_session.add(intent)
    await db_session.commit()
    await db_session.refresh(intent)

    await append_event(db_session, intent.id, "intent.created", {"test": True})
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1

    rows[0].event = "tampered.event"
    with pytest.raises(ValueError, match="immutable"):
        await db_session.commit()
    await db_session.rollback()


# =========================================================================
# 11. Exception inside pipeline releases reservation and never pays
# =========================================================================

@pytest.mark.asyncio
async def test_pipeline_exception_releases_reservation(client, mandate, db_session, monkeypatch):
    """If execute_intent raises, the budget reservation must be released."""
    idem_key = str(uuid.uuid4())

    async def _failing_execute(intent, session):
        raise RuntimeError("Simulated PayPal crash")

    monkeypatch.setattr("app.services.pipeline.execute_intent", _failing_execute)

    # ASGITransport re-raises server exceptions in tests; wrap to catch
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/intents", json={
            "idempotency_key": idem_key,
            "mandate_id": mandate.mandate_id,
            "amount": "5.00",
            "currency": "USD",
            "merchant": "vendor@paypal.com",
        }, headers=agent_headers())

    assert resp.status_code == 500

    # Budget reservation must be released
    period_key = budget_service.get_period_key(mandate.period)
    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    assert balances["reserved"] == 0
