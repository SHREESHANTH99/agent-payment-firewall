"""Unit tests for resilient LLM client: retries, backoff, Retry-After, fallback, caching."""
import asyncio
import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm import LLMClient, LLMError, InMemoryTTLCache, llm_cache


@pytest.fixture(autouse=True)
def clear_cache():
    llm_cache.clear()
    yield
    llm_cache.clear()


ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient

def make_client_factory(transport):
    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return ORIGINAL_ASYNC_CLIENT(*args, **kwargs)
    return factory


@pytest.mark.asyncio
async def test_llm_retry_then_success():
    """Client retries on 503 and succeeds on 2nd attempt."""
    client = LLMClient(base_url="https://mock-llm.local", api_key="test-key", timeout=5)

    calls = 0

    async def mock_handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "High demand"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"safe": True, "confidence": 0.95, "injection_suspected": False})}}]
        })

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", side_effect=make_client_factory(transport)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            data, meta = await client.complete_json(
                model="gpt-4o-mini",
                system="system prompt",
                user="user query",
            )
            assert data["safe"] is True
            assert calls == 2
            assert meta.retries == 1
            assert meta.provider == "primary"
            assert meta.cached is False


@pytest.mark.asyncio
async def test_llm_retry_after_honored():
    """Client parses Retry-After header and sleeps accordingly."""
    client = LLMClient(base_url="https://mock-llm.local", api_key="test-key", timeout=5)
    calls = 0

    async def mock_handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0.1"}, json={"error": "Rate limit"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"status": "ok"})}}]
        })

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", side_effect=make_client_factory(transport)):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            data, meta = await client.complete_json(model="test-model", system="sys", user="usr")
            assert data["status"] == "ok"
            assert calls == 2
            mock_sleep.assert_called_with(0.1)


@pytest.mark.asyncio
async def test_llm_fallback_used_when_primary_exhausted():
    """Primary fails all retries, client tries fallback provider and succeeds."""
    client = LLMClient(
        base_url="https://primary.local",
        api_key="primary-key",
        timeout=5,
        fallback_base_url="https://fallback.local",
        fallback_api_key="fallback-key",
        fallback_model="fallback-gpt",
    )

    calls = []

    async def mock_handler(request: httpx.Request):
        calls.append(str(request.url))
        if "primary.local" in str(request.url):
            return httpx.Response(500, json={"error": "Primary server error"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"fallback_success": True})}}]
        })

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", side_effect=make_client_factory(transport)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            data, meta = await client.complete_json(model="primary-gpt", system="sys", user="usr")
            assert data["fallback_success"] is True
            assert meta.provider == "fallback"
            assert meta.fallback_used is True
            assert meta.model == "fallback-gpt"
            assert len(calls) == 4  # 1 initial + 2 retries on primary + 1 on fallback


@pytest.mark.asyncio
async def test_llm_both_fail_raises_llm_error():
    """Both primary and fallback fail -> raises LLMError (fails closed)."""
    client = LLMClient(
        base_url="https://primary.local",
        api_key="primary-key",
        timeout=5,
        fallback_base_url="https://fallback.local",
        fallback_api_key="fallback-key",
        fallback_model="fallback-gpt",
    )

    async def mock_handler(request: httpx.Request):
        return httpx.Response(500, json={"error": "Fatal server error"})

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", side_effect=make_client_factory(transport)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMError) as exc_info:
                await client.complete_json(model="primary-gpt", system="sys", user="usr")
            assert "Both primary and fallback LLM failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_cache_hit_avoids_second_call():
    """Second identical call returns cached result without making HTTP request."""
    client = LLMClient(base_url="https://mock-llm.local", api_key="test-key", timeout=5)
    call_count = 0

    async def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"result": "fresh_data"})}}]
        })

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", side_effect=make_client_factory(transport)):
        res1, meta1 = await client.complete_json(model="m1", system="sys1", user="usr1")
        assert res1["result"] == "fresh_data"
        assert meta1.cached is False
        assert call_count == 1

        # Second call with same parameters
        res2, meta2 = await client.complete_json(model="m1", system="sys1", user="usr1")
        assert res2["result"] == "fresh_data"
        assert meta2.cached is True
        assert meta2.provider == "cache"
        assert call_count == 1  # No second HTTP call


@pytest.mark.asyncio
async def test_llm_errors_not_cached():
    """Failed calls are never stored in cache."""
    client = LLMClient(
        base_url="https://mock-llm.local",
        api_key="test-key",
        timeout=5,
        fallback_base_url="",  # Ensure fallback is empty so error propagates directly
        fallback_api_key="",
        fallback_model="",
    )
    call_count = 0

    async def mock_handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return httpx.Response(500, json={"error": "fail"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"result": "eventual_success"})}}]
        })

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", side_effect=make_client_factory(transport)):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMError):
                await client.complete_json(model="m1", system="sys1", user="usr1")

            # Verify cache is empty
            key = client._compute_cache_key("m1", "sys1", "usr1")
            assert llm_cache.get(key) is None

            # Now succeeding call should make requests and store cache
            res, meta = await client.complete_json(model="m1", system="sys1", user="usr1")
            assert res["result"] == "eventual_success"
            assert llm_cache.get(key) is not None
