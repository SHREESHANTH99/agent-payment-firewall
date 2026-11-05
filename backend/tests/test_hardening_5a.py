"""Tests for Phase 5A hardening:
1. Sandbox guard
2. Startup validation
3. Log redaction filter and X-Request-ID
4. Rate limiting and body size limit
5. Security headers and documentation endpoints guard
"""
import logging
import pytest
import httpx
from app.main import app, request_id_ctx
from app.core.config import settings
from app.core.logging import RedactionFilter
from app.paypal.constants import (
    PAYPAL_SANDBOX_BASE_URL,
    PAYPAL_OAUTH_URL,
    PAYPAL_PAYOUTS_URL,
    PAYPAL_VERIFY_SIGNATURE_URL,
)


@pytest.mark.asyncio
async def test_sandbox_constants():
    """Verify PayPal URLs are strictly fixed to sandbox host."""
    assert "sandbox.paypal.com" in PAYPAL_SANDBOX_BASE_URL
    assert "sandbox.paypal.com" in PAYPAL_OAUTH_URL
    assert "sandbox.paypal.com" in PAYPAL_PAYOUTS_URL
    assert "sandbox.paypal.com" in PAYPAL_VERIFY_SIGNATURE_URL
    assert "api-m.paypal.com" not in PAYPAL_OAUTH_URL.replace("sandbox.paypal.com", "")


@pytest.mark.asyncio
async def test_security_headers_and_request_id():
    """Verify security headers and X-Request-ID return on every response."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Client sends custom X-Request-ID
        res = await client.get("/health", headers={"X-Request-ID": "custom-trace-12345"})
        assert res.status_code == 200
        assert res.headers["X-Request-ID"] == "custom-trace-12345"
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in res.headers

        # Auto-generated when omitted
        res2 = await client.get("/health")
        assert res2.status_code == 200
        assert res2.headers["X-Request-ID"].startswith("req_")


@pytest.mark.asyncio
async def test_log_redaction_filter():
    """Verify secrets and keys are scrubbed by RedactionFilter."""
    filt = RedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Agent key X-Agent-Key: super-secret-agent-key used with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert "super-secret-agent-key" not in record.msg
    assert "Bearer [REDACTED]" in record.msg or "[REDACTED]" in record.msg


@pytest.mark.asyncio
async def test_body_size_limit():
    """Verify payload exceeding MAX_REQUEST_BODY_BYTES returns 413 with consistent error shape."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        large_body = "x" * (settings.MAX_REQUEST_BODY_BYTES + 1024)
        res = await client.post(
            "/intents",
            content=large_body,
            headers={"Content-Length": str(len(large_body)), "Content-Type": "application/json"},
        )
        assert res.status_code == 413
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "REQUEST_ENTITY_TOO_LARGE"
        assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_consistent_error_shape_on_404():
    """Verify 404 responses conform to {error: {code, message, request_id}}."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/non-existent-endpoint-xyz")
        assert res.status_code == 404
        data = res.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "request_id" in data["error"]
