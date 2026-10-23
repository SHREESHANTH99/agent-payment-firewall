"""Unit tests for PayPal OAuth and Payouts integration using respx for HTTP mocking."""
import time
import pytest
import respx
import httpx

from app.paypal.auth import clear_token_cache, get_access_token
from app.paypal.exceptions import PayPalAPIError, PayPalAuthError
from app.paypal.payouts import create_payout, get_payout_status


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the in-memory token cache before and after every test."""
    clear_token_cache()
    yield
    clear_token_cache()


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_success():
    """Verify successful OAuth token retrieval."""
    route = respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={
            "access_token": "mock_access_token_abc123",
            "token_type": "Bearer",
            "app_id": "APP-SANDBOX-TEST",
            "expires_in": 3600,
        },
    )

    token = await get_access_token()
    assert token == "mock_access_token_abc123"
    assert route.called
    assert route.call_count == 1

    # Verify basic auth and data sent
    request = route.calls.last.request
    assert b"grant_type=client_credentials" in request.content


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_in_memory_caching():
    """Verify that cached token is reused until 60 seconds before expiry."""
    route = respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={
            "access_token": "cached_token_xyz789",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    token1 = await get_access_token()
    token2 = await get_access_token()
    token3 = await get_access_token()

    assert token1 == "cached_token_xyz789"
    assert token2 == "cached_token_xyz789"
    assert token3 == "cached_token_xyz789"
    # Ensure HTTP call was only made once
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_cache_expiration(monkeypatch):
    """Verify that token is refreshed when within 60 seconds of expiry."""
    route = respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={
            "access_token": "token_generation_1",
            "token_type": "Bearer",
            "expires_in": 120,
        },
    )

    # Initial token acquisition
    token1 = await get_access_token()
    assert token1 == "token_generation_1"
    assert route.call_count == 1

    # Update route response for next fetch
    route.respond(
        status_code=200,
        json={
            "access_token": "token_generation_2",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    # Simulate passage of time past (expires_in - 60) seconds (e.g. 70 seconds)
    original_time = time.time
    simulated_now = original_time() + 70
    monkeypatch.setattr(time, "time", lambda: simulated_now)

    token2 = await get_access_token()
    assert token2 == "token_generation_2"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_failure_extracts_debug_id():
    """Verify that PayPalAuthError is raised on non-2xx with PayPal-Debug-Id."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=401,
        headers={"Paypal-Debug-Id": "auth-debug-xyz-987"},
        json={
            "error": "invalid_client",
            "error_description": "Client Authentication failed",
        },
    )

    with pytest.raises(PayPalAuthError) as exc_info:
        await get_access_token()

    err = exc_info.value
    assert err.status_code == 401
    assert err.debug_id == "auth-debug-xyz-987"
    assert "auth-debug-xyz-987" in str(err)
    assert err.error_name == "invalid_client"


@pytest.mark.asyncio
@respx.mock
async def test_create_payout_success():
    """Verify create_payout issues proper request and parses batch response."""
    # Mock Auth
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token_123", "token_type": "Bearer", "expires_in": 3600},
    )

    # Mock Payouts POST
    payout_route = respx.post("https://api-m.sandbox.paypal.com/v1/payments/payouts").respond(
        status_code=201,
        json={
            "batch_header": {
                "payout_batch_id": "BATCH-987654321",
                "batch_status": "PENDING",
                "time_created": "2026-10-23T16:00:00Z",
                "sender_batch_header": {
                    "sender_batch_id": "idempotency-key-001",
                },
            },
            "links": [{"href": "https://api-m.sandbox.paypal.com/v1/payments/payouts/BATCH-987654321", "rel": "self"}],
        },
    )

    response = await create_payout(
        idempotency_key="idempotency-key-001",
        receiver="recipient@example.com",
        amount=1.50,
        currency="USD",
        note="Test payout note",
    )

    assert response.batch_id == "BATCH-987654321"
    assert response.batch_status == "PENDING"

    # Verify tuple unpacking support
    batch_id, batch_status = response
    assert batch_id == "BATCH-987654321"
    assert batch_status == "PENDING"

    # Verify HTTP request details
    req = payout_route.calls.last.request
    assert req.headers["PayPal-Request-Id"] == "idempotency-key-001"
    assert req.headers["Authorization"] == "Bearer valid_token_123"

    import json
    body = json.loads(req.content)
    assert body["sender_batch_header"]["sender_batch_id"] == "idempotency-key-001"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["recipient_type"] == "EMAIL"
    assert item["receiver"] == "recipient@example.com"
    assert item["amount"]["value"] == "1.50"
    assert item["amount"]["currency"] == "USD"
    assert item["note"] == "Test payout note"


@pytest.mark.asyncio
@respx.mock
async def test_create_payout_failure_extracts_debug_id():
    """Verify that create_payout raises PayPalAPIError with debug_id on failure."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token_123", "token_type": "Bearer", "expires_in": 3600},
    )

    respx.post("https://api-m.sandbox.paypal.com/v1/payments/payouts").respond(
        status_code=400,
        headers={"paypal-debug-id": "payout-fail-debug-123"},
        json={
            "name": "INSUFFICIENT_FUNDS",
            "message": "The sender has insufficient funds",
            "debug_id": "payout-fail-debug-123",
        },
    )

    with pytest.raises(PayPalAPIError) as exc_info:
        await create_payout(
            idempotency_key="key-fail-1",
            receiver="test@example.com",
            amount=1000.0,
            currency="USD",
        )

    err = exc_info.value
    assert err.status_code == 400
    assert err.debug_id == "payout-fail-debug-123"
    assert "payout-fail-debug-123" in str(err)
    assert err.error_name == "INSUFFICIENT_FUNDS"


@pytest.mark.asyncio
@respx.mock
async def test_get_payout_status_success():
    """Verify fetching payout status for an existing batch."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token_123", "token_type": "Bearer", "expires_in": 3600},
    )

    respx.get("https://api-m.sandbox.paypal.com/v1/payments/payouts/BATCH-111222").respond(
        status_code=200,
        json={
            "batch_header": {
                "payout_batch_id": "BATCH-111222",
                "batch_status": "SUCCESS",
                "time_created": "2026-10-23T16:00:00Z",
                "time_completed": "2026-10-23T16:02:00Z",
                "sender_batch_header": {
                    "sender_batch_id": "sender-batch-abc",
                },
            },
            "items": [
                {
                    "payout_item_id": "ITEM-99",
                    "transaction_status": "SUCCESS",
                    "payout_item": {
                        "receiver": "sb-receiver@example.com",
                        "amount": {"value": "1.00", "currency": "USD"},
                    },
                }
            ],
        },
    )

    status_details = await get_payout_status("BATCH-111222")
    assert status_details.batch_id == "BATCH-111222"
    assert status_details.batch_status == "SUCCESS"
    assert status_details.sender_batch_id == "sender-batch-abc"
    assert len(status_details.items) == 1

    # Verify tuple unpacking
    batch_id, batch_status = status_details
    assert batch_id == "BATCH-111222"
    assert batch_status == "SUCCESS"


@pytest.mark.asyncio
@respx.mock
async def test_get_payout_status_failure_extracts_debug_id():
    """Verify get_payout_status raises on 404 with debug_id."""
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").respond(
        status_code=200,
        json={"access_token": "valid_token_123", "token_type": "Bearer", "expires_in": 3600},
    )

    respx.get("https://api-m.sandbox.paypal.com/v1/payments/payouts/NON_EXISTENT_BATCH").respond(
        status_code=404,
        headers={"paypal-debug-id": "status-404-debug-id"},
        json={
            "name": "RESOURCE_NOT_FOUND",
            "message": "Specified batch does not exist.",
        },
    )

    with pytest.raises(PayPalAPIError) as exc_info:
        await get_payout_status("NON_EXISTENT_BATCH")

    err = exc_info.value
    assert err.status_code == 404
    assert err.debug_id == "status-404-debug-id"
    assert "status-404-debug-id" in str(err)
