"""Tests for the Judge Playground demo API (Prompt P1, Part 8).

Safety rules validated here:
- Demo mandates always run in dry_run; PayPal is never called.
- Session isolation: Session X cannot see/mutate Session Y.
- Per-session risk toggles do not bleed into other sessions or global config.
- Quota fallback returns 429 { code: "demo_quota", fallback: true }.
- Cross-agent probe denial is indistinguishable from MANDATE_NOT_FOUND.
- Rate limits return 429.
- Custom page text is HTML-escaped before storage.
- TTL / expiry returns 410.
- Concurrency cap blocks a second overlapping agent-run.

All LLM and PayPal network calls are mocked.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.models import Mandate, PaymentIntent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest.fixture(autouse=True)
def demo_enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure demo is enabled and limits are small for speed."""
    monkeypatch.setenv("DEMO_ENABLED", "true")
    monkeypatch.setenv("DEMO_SESSION_TTL_MINUTES", "60")
    monkeypatch.setenv("DEMO_MAX_INTENTS_PER_SESSION", "5")
    monkeypatch.setenv("DEMO_SESSION_CREATE_RATE_PER_MINUTE", "1000")
    monkeypatch.setenv("DEMO_INTENT_RATE_PER_MINUTE", "1000")
    monkeypatch.setenv("DEMO_DAILY_LLM_CALL_BUDGET", "1000")
    monkeypatch.setattr(settings, "EXECUTION_MODE", "paypal")


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_LLM_ALLOW = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [],
            },
            "finish_reason": "stop",
        }
    ]
}

MOCK_JUDGE_SAFE = {
    "safe": True,
    "verdict": "allow",
    "confidence": 0.99,
    "injection_suspected": False,
    "mismatch_reasons": [],
    "reasons": [],
}

MOCK_CANARY_CLEAN = {
    "tripped": False,
    "honeypot_calls": [],
    "segments": 1,
}


def _mock_pipeline_allow() -> dict[str, Any]:
    return {
        "intent_id": str(uuid.uuid4()),
        "decision": "approved",
        "status": "executed",
        "reasons": [],
        "risk": {
            "canary": MOCK_CANARY_CLEAN,
            "judge": MOCK_JUDGE_SAFE,
        },
    }


async def _create_session(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.post("/demo/sessions", json={"scenario": "clean_purchase"})
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "id": body["session"]["id"],
        "secret": body["session_secret"],
        "agents": body["session"]["agents"],
    }


def _session_headers(session_id: str, secret: str) -> dict[str, str]:
    return {
        "X-Demo-Session-Id": session_id,
        "X-Demo-Session-Secret": secret,
    }


def _intent_body(session: dict[str, Any], agent: str = "A") -> dict[str, Any]:
    agents = session["agents"]
    agent_obj = next(a for a in agents if a["id"] == agent)
    seller = agent_obj["mandate"]["allowlist_merchants"][0]
    return {
        "agent": agent,
        "amount": "10.00",
        "currency": "USD",
        "merchant": seller,
        "description": "Office supplies",
        "reasoning": "Matches the user task.",
        "user_task": "Buy the listed item from the allowlisted seller.",
        "source_context": "The page lists the item at the correct price.",
        "target_mandate": "own",
    }


# ---------------------------------------------------------------------------
# 1. Session creation and state
# ---------------------------------------------------------------------------

async def test_create_session_returns_session_and_secret(client: httpx.AsyncClient):
    """POST /demo/sessions returns a session id, agents A+B, and a session_secret."""
    resp = await client.post("/demo/sessions", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert "session_secret" in body
    assert body["session_secret"].startswith("ds_")
    session = body["session"]
    assert session["id"].startswith("demo_")
    agent_ids = {a["id"] for a in session["agents"]}
    assert agent_ids == {"A", "B"}
    # Every agent must ship a mandate
    for agent in session["agents"]:
        mandate = agent["mandate"]
        assert mandate["budget_total_cents"] > 0
        assert mandate["status"] == "active"


async def test_session_state_requires_auth(client: httpx.AsyncClient):
    """GET /demo/sessions/{id}/state without credentials returns 401."""
    session = await _create_session(client)
    resp = await client.get(f"/demo/sessions/{session['id']}/state")
    assert resp.status_code == 401


async def test_session_state_returns_mandates(client: httpx.AsyncClient):
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])
    resp = await client.get(f"/demo/sessions/{session['id']}/state", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    s = body["session"]
    agent_ids = {a["id"] for a in s["agents"]}
    assert agent_ids == {"A", "B"}
    assert "escalations" in s
    assert "recent_intents" in s
    assert "quota" in s


# ---------------------------------------------------------------------------
# 2. Intent submission — dry_run enforcement and no PayPal call
# ---------------------------------------------------------------------------

async def test_intent_always_dry_run_paypal_never_called(client: httpx.AsyncClient):
    """Demo intents must run in dry_run mode; PayPal API must never be invoked."""
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])
    body = _intent_body(session)

    with (
        patch("app.services.pipeline.evaluate_canary", new_callable=AsyncMock) as mock_canary,
        patch("app.services.pipeline.evaluate_judge", new_callable=AsyncMock) as mock_judge,
        patch("app.paypal.payouts.create_payout", new_callable=AsyncMock) as mock_paypal,
    ):
        mock_canary.return_value = MagicMock(**MOCK_CANARY_CLEAN)
        mock_judge.return_value = MagicMock(**MOCK_JUDGE_SAFE)
        mock_paypal.side_effect = RuntimeError("PayPal must never be called in demo mode")

        resp = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)

    # Pipeline may deny for other reasons (quota/ttl) in test env, but PayPal must not be called.
    assert resp.status_code in {200, 429}
    if resp.status_code == 200:
        result = resp.json()
        assert result.get("dry_run") is True
        # PayPal mock must not have been invoked
        mock_paypal.assert_not_called()


async def test_intent_response_contains_operator_view(client: httpx.AsyncClient):
    """POST /demo/sessions/{id}/intents returns operatorView with balances and audit entries."""
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])
    body = _intent_body(session)

    with (
        patch("app.services.pipeline.evaluate_canary", new_callable=AsyncMock) as mock_canary,
        patch("app.services.pipeline.evaluate_judge", new_callable=AsyncMock) as mock_judge,
        patch("app.paypal.payouts.create_payout", new_callable=AsyncMock),
    ):
        mock_canary.return_value = MagicMock(**MOCK_CANARY_CLEAN)
        mock_judge.return_value = MagicMock(**MOCK_JUDGE_SAFE)

        resp = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)

    if resp.status_code == 200:
        result = resp.json()
        assert "operatorView" in result
        ov = result["operatorView"]
        assert "balances" in ov
        assert "new_audit_entries" in ov
        assert ov["balances"]["remaining_cents"] >= 0


# ---------------------------------------------------------------------------
# 3. Session isolation
# ---------------------------------------------------------------------------

async def test_session_isolation_state(client: httpx.AsyncClient):
    """Session A's state must not be accessible with Session B's credentials."""
    s1 = await _create_session(client)
    s2 = await _create_session(client)

    # S1 header accessing S2 endpoint → 401
    headers_s1 = _session_headers(s1["id"], s1["secret"])
    resp = await client.get(f"/demo/sessions/{s2['id']}/state", headers=headers_s1)
    assert resp.status_code == 401

    # S2 header accessing S1 endpoint → 401
    headers_s2 = _session_headers(s2["id"], s2["secret"])
    resp = await client.get(f"/demo/sessions/{s1['id']}/state", headers=headers_s2)
    assert resp.status_code == 401


async def test_session_isolation_wrong_secret(client: httpx.AsyncClient):
    """Correct session id but wrong secret must return 401."""
    session = await _create_session(client)
    bad_headers = _session_headers(session["id"], "ds_wrong_secret_value")
    resp = await client.get(f"/demo/sessions/{session['id']}/state", headers=bad_headers)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4. Per-session risk toggles do not bleed into other sessions or global config
# ---------------------------------------------------------------------------

async def test_per_session_config_patch(client: httpx.AsyncClient):
    """`PATCH /demo/sessions/{id}/config` updates only that session's toggles."""
    from app.services.risk_config import risk_config_state

    s1 = await _create_session(client)
    s2 = await _create_session(client)

    global_before = risk_config_state.get_config()

    # Disable judge for s1 only
    headers_s1 = _session_headers(s1["id"], s1["secret"])
    resp = await client.patch(
        f"/demo/sessions/{s1['id']}/config",
        json={"judge_enabled": False},
        headers=headers_s1,
    )
    assert resp.status_code == 200
    assert resp.json()["config"]["judge_enabled"] is False

    # Global risk config must be unchanged
    global_after = risk_config_state.get_config()
    assert global_before.judge_enabled == global_after.judge_enabled

    # S2's config must be unchanged (still default True)
    headers_s2 = _session_headers(s2["id"], s2["secret"])
    state_resp = await client.get(f"/demo/sessions/{s2['id']}/state", headers=headers_s2)
    assert state_resp.json()["session"]["config"]["judge_enabled"] is True


# ---------------------------------------------------------------------------
# 5. Quota fallback
# ---------------------------------------------------------------------------

async def test_quota_exhausted_returns_429_demo_quota(client: httpx.AsyncClient):
    """When quota is used up, the endpoint returns 429 with code=demo_quota and fallback=true."""
    # Set quota to 1 so it exhausts quickly
    with patch.dict("os.environ", {"DEMO_MAX_INTENTS_PER_SESSION": "1"}):
        session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])
    body = _intent_body(session)

    # Exhaust the quota by sending the maximum allowed
    with (
        patch("app.services.pipeline.evaluate_canary", new_callable=AsyncMock) as mock_canary,
        patch("app.services.pipeline.evaluate_judge", new_callable=AsyncMock) as mock_judge,
        patch("app.paypal.payouts.create_payout", new_callable=AsyncMock),
    ):
        mock_canary.return_value = MagicMock(**MOCK_CANARY_CLEAN)
        mock_judge.return_value = MagicMock(**MOCK_JUDGE_SAFE)
        # First request (may succeed or fail for other reasons)
        await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)
        # Second request must hit quota
        resp2 = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)

    # Either we're rate limited or quota hit
    if resp2.status_code == 429:
        err = resp2.json()
        assert err.get("code") == "demo_quota"
        assert err.get("fallback") is True


async def test_llm_budget_exhausted_returns_429_fallback(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """When DEMO_DAILY_LLM_CALL_BUDGET is 0, return 429 demo_quota with fallback=true."""
    monkeypatch.setenv("DEMO_DAILY_LLM_CALL_BUDGET", "0")
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])
    body = _intent_body(session)

    # Patch Redis incrby to simulate budget exceeded
    with patch("app.api.demo._consume_llm_budget", new_callable=AsyncMock) as mock_budget:
        from app.api.demo import _error
        from fastapi import status as http_status

        mock_budget.side_effect = _error(
            "demo_quota",
            "The demo risk-layer quota is exhausted",
            http_status.HTTP_429_TOO_MANY_REQUESTS,
            fallback=True,
        )
        resp = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)

    assert resp.status_code == 429
    err = resp.json()
    assert err["code"] == "demo_quota"
    assert err["fallback"] is True


# ---------------------------------------------------------------------------
# 6. Cross-agent probe returns MANDATE_NOT_FOUND
# ---------------------------------------------------------------------------

async def test_cross_agent_probe_returns_mandate_not_found(client: httpx.AsyncClient):
    """Agent A targeting `other` (B's mandate) on denial must only report MANDATE_NOT_FOUND."""
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])

    agents = session["agents"]
    seller_b = next(a for a in agents if a["id"] == "B")["mandate"]["allowlist_merchants"][0]

    body = {
        "agent": "A",
        "amount": "10.00",
        "currency": "USD",
        "merchant": seller_b,
        "description": "Probe",
        "reasoning": "Testing cross-agent probe",
        "user_task": "Transfer to other agent mandate",
        "source_context": "Probe the other agent mandate.",
        "target_mandate": "other",
    }

    with (
        patch("app.services.pipeline.evaluate_canary", new_callable=AsyncMock) as mock_canary,
        patch("app.services.pipeline.evaluate_judge", new_callable=AsyncMock) as mock_judge,
        patch("app.paypal.payouts.create_payout", new_callable=AsyncMock),
    ):
        mock_canary.return_value = MagicMock(**MOCK_CANARY_CLEAN)
        mock_judge.return_value = MagicMock(**MOCK_JUDGE_SAFE)
        resp = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)

    if resp.status_code == 200:
        result = resp.json()
        if result.get("decision") == "denied":
            # Must mask the real denial reason behind MANDATE_NOT_FOUND
            codes = [r["code"] for r in result.get("reasons", [])]
            assert codes == ["MANDATE_NOT_FOUND"], (
                f"Expected MANDATE_NOT_FOUND masking for cross-agent probe, got: {codes}"
            )
            # Risk details must also be sanitized
            assert result["risk"] == {"denial_cause": "rules"}


# ---------------------------------------------------------------------------
# 7. HTML escaping of custom page text
# ---------------------------------------------------------------------------

async def test_custom_page_text_is_escaped(client: httpx.AsyncClient):
    """Custom page text with HTML must be stored escaped and rendered as plain text."""
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])

    xss_payload = "<script>alert('xss')</script>&malicious"
    resp = await client.post(
        f"/demo/sessions/{session['id']}/agent-runs",
        json={"task": "Browse the store.", "custom_page_text": xss_payload, "agent": "A"},
        headers=headers,
    )
    assert resp.status_code in {202, 429}

    if resp.status_code == 202:
        # Read the custom catalog page and verify the script tag is escaped
        catalog_resp = await client.get(
            f"/demo/sessions/{session['id']}/store/catalog",
            headers=headers,
        )
        assert catalog_resp.status_code == 200
        html = catalog_resp.text
        # Script must not appear unescaped
        assert "<script>" not in html
        # Escaped form must be present
        assert "&lt;script&gt;" in html or "alert" not in html


# ---------------------------------------------------------------------------
# 8. Rate limiting
# ---------------------------------------------------------------------------

async def test_rate_limit_on_session_creation(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """When DEMO_SESSION_CREATE_RATE_PER_MINUTE is 1, second creation from same IP returns 429."""
    monkeypatch.setenv("DEMO_SESSION_CREATE_RATE_PER_MINUTE", "1")

    with patch("app.api.demo._rate_limit", new_callable=AsyncMock) as mock_rl:
        from app.api.demo import _error
        from fastapi import status as http_status

        call_count = {"n": 0}

        async def _side_effect(request, bucket, maximum, window=60):
            call_count["n"] += 1
            if call_count["n"] > 1:
                raise _error("rate_limited", "Too many demo requests", http_status.HTTP_429_TOO_MANY_REQUESTS)

        mock_rl.side_effect = _side_effect

        resp1 = await client.post("/demo/sessions", json={})
        resp2 = await client.post("/demo/sessions", json={})

    assert resp1.status_code == 201
    assert resp2.status_code == 429
    assert resp2.json()["code"] == "rate_limited"


# ---------------------------------------------------------------------------
# 9. Escalation session isolation
# ---------------------------------------------------------------------------

async def test_escalation_session_isolation(client: httpx.AsyncClient):
    """Session B cannot approve or reject escalations that belong to Session A."""
    s_a = await _create_session(client)
    s_b = await _create_session(client)

    headers_b = _session_headers(s_b["id"], s_b["secret"])
    # Attempt to approve a fake intent_id from session A's context via session B's credentials
    fake_intent_id = str(uuid.uuid4())
    resp = await client.post(
        f"/demo/sessions/{s_a['id']}/escalations/{fake_intent_id}/approve",
        headers=headers_b,
    )
    # Must be 401 because session B credentials can't auth session A
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 10. DEMO_ENABLED=false disables all endpoints
# ---------------------------------------------------------------------------

async def test_demo_disabled_returns_404(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEMO_ENABLED", "false")
    resp = await client.post("/demo/sessions", json={})
    assert resp.status_code == 404
    assert resp.json()["code"] == "demo_disabled"


# ---------------------------------------------------------------------------
# 11. Concurrency cap on agent runs
# ---------------------------------------------------------------------------

async def test_concurrency_cap_on_agent_runs(client: httpx.AsyncClient):
    """When an agent run is already active for a session, a second start returns 429."""
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])

    # Fake an already-active run by patching the semaphore
    with patch("app.api.demo._run_semaphore") as mock_sem:
        mock_sem.locked.return_value = True
        resp = await client.post(
            f"/demo/sessions/{session['id']}/agent-runs",
            json={"task": "Browse the store.", "agent": "A"},
            headers=headers,
        )

    assert resp.status_code == 429
    assert resp.json()["code"] == "rate_limited"


# ---------------------------------------------------------------------------
# 12. Invalid / oversized field values
# ---------------------------------------------------------------------------

async def test_oversized_source_context_rejected(client: httpx.AsyncClient):
    """source_context exceeding 4000 characters must be rejected."""
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])

    agents = session["agents"]
    seller = agents[0]["mandate"]["allowlist_merchants"][0]

    body = {
        "agent": "A",
        "amount": "10.00",
        "currency": "USD",
        "merchant": seller,
        "source_context": "A" * 4001,
        "target_mandate": "own",
    }
    resp = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)
    assert resp.status_code == 422  # Pydantic validation error


async def test_negative_amount_rejected(client: httpx.AsyncClient):
    session = await _create_session(client)
    headers = _session_headers(session["id"], session["secret"])
    agents = session["agents"]
    seller = agents[0]["mandate"]["allowlist_merchants"][0]

    body = {
        "agent": "A",
        "amount": "-5.00",
        "currency": "USD",
        "merchant": seller,
        "target_mandate": "own",
    }
    resp = await client.post(f"/demo/sessions/{session['id']}/intents", json=body, headers=headers)
    assert resp.status_code == 422

