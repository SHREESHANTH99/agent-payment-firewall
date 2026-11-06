"""Tests for hardening fixes: trusted proxy IP derivation, exemptions, and CSP /docs compatibility."""
import pytest
from unittest.mock import MagicMock
from fastapi import Request
from app.core.config import settings
from app.core.rate_limit import get_client_ip, is_rate_limit_exempt
from app.main import app
from httpx import AsyncClient, ASGITransport


def test_get_client_ip_trusted_proxy():
    """When TRUSTED_PROXY_COUNT is configured, client IP must be parsed from X-Forwarded-For."""
    orig_trusted = settings.TRUSTED_PROXY_COUNT
    try:
        settings.TRUSTED_PROXY_COUNT = 1
        # Mock request with X-Forwarded-For
        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.195, 10.0.0.1")],
            "client": ("10.0.0.1", 12345),
        }
        req = Request(scope)
        # With TRUSTED_PROXY_COUNT=1, rightmost proxy is 10.0.0.1
        ip = get_client_ip(req)
        assert ip == "10.0.0.1"

        settings.TRUSTED_PROXY_COUNT = 2
        # With TRUSTED_PROXY_COUNT=2, client IP before the last proxy is 203.0.113.195
        ip = get_client_ip(req)
        assert ip == "203.0.113.195"
    finally:
        settings.TRUSTED_PROXY_COUNT = orig_trusted


def test_get_client_ip_no_proxy():
    """When TRUSTED_PROXY_COUNT=0, use request.client.host directly."""
    orig_trusted = settings.TRUSTED_PROXY_COUNT
    try:
        settings.TRUSTED_PROXY_COUNT = 0
        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.195")],
            "client": ("192.168.1.50", 12345),
        }
        req = Request(scope)
        assert get_client_ip(req) == "192.168.1.50"
    finally:
        settings.TRUSTED_PROXY_COUNT = orig_trusted


def test_rate_limit_exemptions():
    """Health probes and PayPal webhooks must be exempt from per-IP rate limiting."""
    assert is_rate_limit_exempt("/health") is True
    assert is_rate_limit_exempt("/ready") is True
    assert is_rate_limit_exempt("/webhooks/paypal") is True
    assert is_rate_limit_exempt("/api/v1/webhooks/paypal") is True
    assert is_rate_limit_exempt("/intents") is False
    assert is_rate_limit_exempt("/mandates") is False


@pytest.mark.asyncio
async def test_csp_header_allows_docs_when_enabled():
    """CSP must allow cdn.jsdelivr.net scripts/styles when ENABLE_DOCS=True on /docs."""
    orig_docs = settings.ENABLE_DOCS
    try:
        settings.ENABLE_DOCS = True
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/docs")
            csp = res.headers.get("content-security-policy", "")
            assert "https://cdn.jsdelivr.net" in csp
    finally:
        settings.ENABLE_DOCS = orig_docs
