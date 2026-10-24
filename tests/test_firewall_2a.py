"""Comprehensive tests for Prompt 2A: rules engine, budget service, idempotency, and mandate API."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import uuid

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.models import Mandate, PaymentIntent, PaymentIntentStatus
from app.risk.rules import RuleResult, evaluate_rules, to_cents
from app.services.budget import budget_service
from app.services.idempotency import compute_payload_hash, idempotency_service

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest.fixture(autouse=True)
def setup_test_settings(monkeypatch):
    monkeypatch.setattr(settings, "OPERATOR_TOKEN", "test-operator-secret-token")
    monkeypatch.setattr(settings, "AGENT_API_KEYS", {"valid-agent-key": "agent-007"})
    yield


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        await session.execute(delete(PaymentIntent))
        await session.execute(delete(Mandate))
        await session.commit()
        yield session
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


# =========================================================================
# 1. RULES ENGINE TESTS
# =========================================================================

class DummyMandate:
    def __init__(
        self,
        status="active",
        valid_from=None,
        valid_until=None,
        allowed_currencies=None,
        per_transaction_cap=5000,
        allowlist_merchants=None,
        escalation_threshold=2500,
    ):
        now = datetime.now(timezone.utc)
        self.status = status
        self.valid_from = valid_from or (now - timedelta(days=1))
        self.valid_until = valid_until or (now + timedelta(days=1))
        self.allowed_currencies = allowed_currencies or ["USD"]
        self.per_transaction_cap = per_transaction_cap  # 50.00 USD
        self.allowlist_merchants = allowlist_merchants or ["vendor@paypal.com", "api@service.io"]
        self.escalation_threshold = escalation_threshold  # 25.00 USD


def test_rules_all_pass():
    mandate = DummyMandate()
    intent = {
        "amount": "20.00",
        "currency": "USD",
        "merchant": "vendor@paypal.com",
    }
    result = evaluate_rules(mandate, intent)
    assert result.passed is True
    assert result.escalate is False
    assert len(result.failures) == 0


def test_rules_escalation_flag_not_a_failure():
    mandate = DummyMandate()
    intent = {
        "amount": "30.00",  # > 25.00 threshold, <= 50.00 cap
        "currency": "USD",
        "merchant": "vendor@paypal.com",
    }
    result = evaluate_rules(mandate, intent)
    assert result.passed is True
    assert result.escalate is True
    assert len(result.failures) == 0


def test_rules_multiple_failures_reported_together():
    now = datetime.now(timezone.utc)
    mandate = DummyMandate(
        status="frozen",
        valid_until=now - timedelta(hours=1),
        allowed_currencies=["EUR"],
        per_transaction_cap=1000,  # 10.00
        allowlist_merchants=["allowed@paypal.com"],
    )
    intent = {
        "amount": "99.00",  # exceeds cap
        "currency": "USD",   # not EUR
        "merchant": "unauthorized@evil.com",  # not allowlisted
    }
    result = evaluate_rules(mandate, intent, now=now)
    assert result.passed is False
    codes = [f["code"] for f in result.failures]
    assert "MANDATE_FROZEN" in codes
    assert "MANDATE_VALIDITY_EXPIRED" in codes
    assert "CURRENCY_NOT_ALLOWED" in codes
    assert "PER_TRANSACTION_CAP_EXCEEDED" in codes
    assert "MERCHANT_NOT_ALLOWLISTED" in codes
    assert len(codes) >= 5


def test_rules_revoked_and_expired_status():
    m_revoked = DummyMandate(status="revoked")
    r1 = evaluate_rules(m_revoked, {"amount": 10.0, "currency": "USD", "merchant": "vendor@paypal.com"})
    assert r1.passed is False
    assert any(f["code"] == "MANDATE_REVOKED" for f in r1.failures)

    m_expired = DummyMandate(status="expired")
    r2 = evaluate_rules(m_expired, {"amount": 10.0, "currency": "USD", "merchant": "vendor@paypal.com"})
    assert r2.passed is False
    assert any(f["code"] == "MANDATE_EXPIRED" for f in r2.failures)


def test_rules_amount_zero_or_negative():
    mandate = DummyMandate()
    r_zero = evaluate_rules(mandate, {"amount": "0.00", "currency": "USD", "merchant": "vendor@paypal.com"})
    assert r_zero.passed is False
    assert any(f["code"] == "AMOUNT_NOT_POSITIVE" for f in r_zero.failures)

    r_neg = evaluate_rules(mandate, {"amount": -5.00, "currency": "USD", "merchant": "vendor@paypal.com"})
    assert r_neg.passed is False
    assert any(f["code"] == "AMOUNT_NOT_POSITIVE" for f in r_neg.failures)


def test_rules_more_than_two_decimals_rejected():
    mandate = DummyMandate()
    r = evaluate_rules(mandate, {"amount": "10.005", "currency": "USD", "merchant": "vendor@paypal.com"})
    assert r.passed is False
    assert any(f["code"] == "INVALID_AMOUNT" for f in r.failures)


# =========================================================================
# 2. BUDGET SERVICE & CONCURRENCY TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_budget_reserve_commit_release_flow():
    mandate_id = str(uuid.uuid4())
    period_key = "lifetime"
    intent_id = str(uuid.uuid4())
    amount_cents = 2500  # $25.00
    budget_cents = 10000  # $100.00

    # 1. Reserve
    success = await budget_service.reserve(mandate_id, period_key, intent_id, amount_cents, budget_cents)
    assert success is True

    balances = await budget_service.get_balances(mandate_id, period_key)
    assert balances["reserved"] == 2500
    assert balances["spent"] == 0

    # Idempotent reserve per intent_id
    success_replay = await budget_service.reserve(mandate_id, period_key, intent_id, amount_cents, budget_cents)
    assert success_replay is True
    balances_after_replay = await budget_service.get_balances(mandate_id, period_key)
    assert balances_after_replay["reserved"] == 2500

    # 2. Commit -> moves reserved -> spent
    committed = await budget_service.commit(intent_id)
    assert committed is True

    balances_committed = await budget_service.get_balances(mandate_id, period_key)
    assert balances_committed["reserved"] == 0
    assert balances_committed["spent"] == 2500

    # 3. Release on a committed intent is a safe no-op
    released = await budget_service.release(intent_id)
    assert released is False


@pytest.mark.asyncio
async def test_budget_release_frees_funds_and_double_release_safe():
    mandate_id = str(uuid.uuid4())
    period_key = "lifetime"
    intent_id = str(uuid.uuid4())
    amount_cents = 4000
    budget_cents = 5000

    await budget_service.reserve(mandate_id, period_key, intent_id, amount_cents, budget_cents)
    b1 = await budget_service.get_balances(mandate_id, period_key)
    assert b1["reserved"] == 4000

    # Release frees the reserved funds
    rel1 = await budget_service.release(intent_id)
    assert rel1 is True
    b2 = await budget_service.get_balances(mandate_id, period_key)
    assert b2["reserved"] == 0

    # Double release is safe
    rel2 = await budget_service.release(intent_id)
    assert rel2 is False
    b3 = await budget_service.get_balances(mandate_id, period_key)
    assert b3["reserved"] == 0


@pytest.mark.asyncio
async def test_budget_concurrency_20_parallel_reserves():
    """
    20 parallel reserve() calls of 10.00 (1000 cents) against a 100.00 (10000 cents) budget
    via asyncio.gather -> exactly 10 succeed, balances consistent.
    """
    mandate_id = str(uuid.uuid4())
    period_key = "lifetime"
    amount_cents = 1000  # $10.00
    budget_cents = 10000  # $100.00

    async def _call_reserve(idx: int):
        intent_id = f"intent-concurrent-{mandate_id}-{idx}"
        return await budget_service.reserve(mandate_id, period_key, intent_id, amount_cents, budget_cents)

    results = await asyncio.gather(*[_call_reserve(i) for i in range(20)])
    succeeded = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)

    assert succeeded == 10
    assert failed == 10

    balances = await budget_service.get_balances(mandate_id, period_key)
    assert balances["reserved"] == 10000
    assert balances["spent"] == 0


@pytest.mark.asyncio
async def test_budget_period_keys():
    dt = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    assert budget_service.get_period_key("lifetime", dt) == "lifetime"
    assert budget_service.get_period_key("daily", dt) == "2026-10-24"
    # 2026-10-24 is Saturday, Week 43 of 2026
    year, week, _ = dt.isocalendar()
    assert budget_service.get_period_key("weekly", dt) == f"{year}-W{week:02d}"


@pytest.mark.asyncio
async def test_budget_rebuild_from_db(db_session: AsyncSession):
    mandate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Insert mandate
    mandate = Mandate(
        mandate_id=mandate_id,
        agent_id="agent-rebuild",
        budget_total=50000,
        per_transaction_cap=10000,
        allowlist_merchants=["recipient@test.com"],
        allowed_currencies=["USD"],
        period="lifetime",
        valid_from=now,
        valid_until=now + timedelta(days=30),
        status="active",
        created_at=now,
    )
    db_session.add(mandate)

    # Insert executed intent (should contribute to spent)
    intent_executed = PaymentIntent(
        id=str(uuid.uuid4()),
        mandate_id=mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=5000,  # $50.00
        currency="USD",
        merchant="recipient@test.com",
        status=PaymentIntentStatus.EXECUTED,
        created_at=now,
    )
    # Insert escalated intent (should contribute to reserved)
    intent_escalated = PaymentIntent(
        id=str(uuid.uuid4()),
        mandate_id=mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=2000,  # $20.00
        currency="USD",
        merchant="recipient@test.com",
        status=PaymentIntentStatus.ESCALATED,
        created_at=now,
    )
    # Insert denied intent (should NOT contribute)
    intent_denied = PaymentIntent(
        id=str(uuid.uuid4()),
        mandate_id=mandate_id,
        idempotency_key=str(uuid.uuid4()),
        amount=1000,
        currency="USD",
        merchant="recipient@test.com",
        status=PaymentIntentStatus.DENIED,
        created_at=now,
    )

    db_session.add_all([intent_executed, intent_escalated, intent_denied])
    await db_session.commit()

    # Rebuild from database
    await budget_service.rebuild_from_db(db_session)

    balances = await budget_service.get_balances(mandate_id, "lifetime")
    assert balances["spent"] == 5000
    assert balances["reserved"] == 2000


# =========================================================================
# 3. IDEMPOTENCY TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_idempotency_replay_conflict_expiry():
    key = str(uuid.uuid4())
    payload_a = {"amount": "10.00", "merchant": "a@test.com"}
    payload_b = {"amount": "20.00", "merchant": "b@test.com"}
    hash_a = compute_payload_hash(payload_a)
    hash_b = compute_payload_hash(payload_b)

    # 1. First claim succeeds
    claim1 = await idempotency_service.check_and_claim(key, hash_a, ttl_seconds=2)
    assert claim1 is None

    # Store response
    mock_resp = {"intent_id": "int-123", "status": "approved"}
    await idempotency_service.store_response(key, mock_resp, ttl_seconds=2)

    # 2. Replay with identical payload returns stored response
    replay = await idempotency_service.check_and_claim(key, hash_a, ttl_seconds=2)
    assert replay == mock_resp

    # 3. Conflict with different payload raises HTTP 409
    with pytest.raises(httpx.HTTPStatusError if False else Exception) as exc_info:
        await idempotency_service.check_and_claim(key, hash_b, ttl_seconds=2)
    assert "409" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 409

    # 4. TTL expiry allows new claim after expiration
    await asyncio.sleep(2.2)
    new_claim = await idempotency_service.check_and_claim(key, hash_b, ttl_seconds=10)
    assert new_claim is None


# =========================================================================
# 4. MANDATE API & AUTH TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_mandate_api_auth_required(client: httpx.AsyncClient):
    # No auth -> 401
    resp_no_auth = await client.get("/mandates")
    assert resp_no_auth.status_code == 401

    # Agent key cannot call operator routes -> 401
    resp_agent = await client.get("/mandates", headers={"X-Agent-Key": "valid-agent-key"})
    assert resp_agent.status_code == 401

    # Valid operator token -> 200
    headers = {"Authorization": "Bearer test-operator-secret-token"}
    resp_op = await client.get("/mandates", headers=headers)
    assert resp_op.status_code == 200


@pytest.mark.asyncio
async def test_mandate_crud_freeze_revoke_flow(client: httpx.AsyncClient):
    headers = {"Authorization": "Bearer test-operator-secret-token"}

    # 1. Create Mandate
    payload = {
        "agent_id": "agent-007",
        "budget_total": "150.00",
        "per_transaction_cap": "50.00",
        "allowlist_merchants": ["api@vendor.com", "billing@service.com"],
        "allowed_currencies": ["USD"],
        "period": "lifetime",
        "escalation_threshold": "25.00",
    }
    create_resp = await client.post("/mandates", headers=headers, json=payload)
    assert create_resp.status_code == 201
    data = create_resp.json()
    mandate_id = data["mandate_id"]
    assert data["budget_total"] == "150.00"
    assert data["budget_total_cents"] == 15000
    assert data["remaining"] == "150.00"
    assert data["status"] == "active"

    # 2. Get Mandate
    get_resp = await client.get(f"/mandates/{mandate_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["mandate_id"] == mandate_id

    # 3. Patch Mandate
    patch_resp = await client.patch(
        f"/mandates/{mandate_id}",
        headers=headers,
        json={"per_transaction_cap": "60.00"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["per_transaction_cap"] == "60.00"
    assert patch_resp.json()["per_transaction_cap_cents"] == 6000

    # 4. Freeze Mandate
    freeze_resp = await client.post(f"/mandates/{mandate_id}/freeze", headers=headers)
    assert freeze_resp.status_code == 200
    assert freeze_resp.json()["status"] == "frozen"

    # 5. Unfreeze Mandate
    unfreeze_resp = await client.post(f"/mandates/{mandate_id}/unfreeze", headers=headers)
    assert unfreeze_resp.status_code == 200
    assert unfreeze_resp.json()["status"] == "active"

    # 6. Revoke Mandate
    revoke_resp = await client.post(f"/mandates/{mandate_id}/revoke", headers=headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"
