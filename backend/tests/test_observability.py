"""Tests for Prometheus metrics endpoint, request-id propagation, and readiness checks."""
import pytest
import httpx
from app.main import app
from app.core.config import settings
from app.core.metrics import export_metrics, INTENT_DECISIONS_TOTAL


@pytest.mark.asyncio
async def test_metrics_endpoint_unauthorized():
    """Verify GET /metrics requires authentication (401 without token)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_metrics_endpoint_authorized(monkeypatch):
    """Verify GET /metrics returns prometheus text format with valid Bearer token."""
    monkeypatch.setattr(settings, "OPERATOR_TOKEN", "valid-test-operator-token-12345")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/metrics",
            headers={"Authorization": "Bearer valid-test-operator-token-12345"},
        )
        assert res.status_code == 200
        assert "apf_intent_decisions_total" in res.text
        assert "apf_pipeline_latency_seconds" in res.text
        assert "text/plain" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_metrics_counter_increments():
    """Verify Prometheus counter increments properly."""
    INTENT_DECISIONS_TOTAL.labels(decision="approved", stopping_layer="none").inc()
    data, _ = export_metrics()
    assert b'apf_intent_decisions_total{decision="approved",stopping_layer="none"}' in data


@pytest.mark.asyncio
async def test_request_id_propagation():
    """Verify custom X-Request-ID propagates into response headers and generated if absent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Custom request id
        r1 = await client.get("/health", headers={"X-Request-ID": "custom-trace-uuid"})
        assert r1.status_code == 200
        assert r1.headers["X-Request-ID"] == "custom-trace-uuid"

        # 2. Generated request id
        r2 = await client.get("/health")
        assert r2.status_code == 200
        assert r2.headers["X-Request-ID"].startswith("req_")


@pytest.mark.asyncio
async def test_ready_check_failure_returns_503(monkeypatch):
    """Verify GET /ready returns 503 if redis ping fails."""
    from unittest.mock import AsyncMock
    from app.services.budget import budget_service

    mock_redis = AsyncMock()
    mock_redis.ping.return_value = False
    monkeypatch.setattr(budget_service, "get_redis", AsyncMock(return_value=mock_redis))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["redis"] == "unhealthy"
