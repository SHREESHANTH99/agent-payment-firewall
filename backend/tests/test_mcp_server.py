import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.mcp_server import _execute_firewall_intent, MAX_LIMITS


@pytest.mark.asyncio
async def test_mcp_execute_firewall_intent_approved_sanitized():
    """Verify clean response is sanitized and returns only intent_id, decision, status, reason, escalated."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "intent_id": "intent-12345",
            "decision": "approved",
            "status": "executed",
            "reasons": [],
            "risk_details": {
                "canary_tripped": False,
                "canary_calls": [{"name": "fake_tool"}],
                "judge_score": 0.05,
            },
        }
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        result = await _execute_firewall_intent(
            amount_usd=25.0,
            merchant="store@example.com",
            description="Office stationery",
            reasoning="Required by user",
            user_task="Buy office pens",
            source_context="Catalog item #42",
            mandate_id="mnd-001",
        )

        assert result == {
            "intent_id": "intent-12345",
            "decision": "approved",
            "status": "executed",
            "reason": "Payment approved by firewall policy.",
            "escalated": False,
        }
        # Guarantee no risk internals leaked
        assert "risk_details" not in result
        assert "risk_stamp" not in result
        assert "canary" not in result
        assert "judge" not in result


@pytest.mark.asyncio
async def test_mcp_execute_firewall_intent_rejected_parameters():
    """Verify attempt by caller to pass agent_id or dry_run is rejected."""
    # Attempting to supply agent_id
    res1 = await _execute_firewall_intent(
        amount_usd=25.0,
        merchant="store@example.com",
        description="Office stationery",
        reasoning="Required by user",
        user_task="Buy pens",
        source_context="text",
        agent_id="attacker_chosen_agent",
    )
    assert res1["status"] == "error"
    assert res1["error_code"] == "FORBIDDEN_PARAMETER"
    assert "agent_id" in res1["message"]

    # Attempting to supply dry_run
    res2 = await _execute_firewall_intent(
        amount_usd=25.0,
        merchant="store@example.com",
        description="Office stationery",
        reasoning="Required by user",
        user_task="Buy pens",
        source_context="text",
        dry_run=False,
    )
    assert res2["status"] == "error"
    assert res2["error_code"] == "FORBIDDEN_PARAMETER"
    assert "dry_run" in res2["message"]


@pytest.mark.asyncio
async def test_mcp_execute_firewall_intent_input_limits():
    """Verify input length limits are enforced before dispatch."""
    # Oversized reasoning
    res_reasoning = await _execute_firewall_intent(
        amount_usd=25.0,
        merchant="store@example.com",
        description="item",
        reasoning="x" * (MAX_LIMITS["reasoning"] + 1),
        user_task="task",
        source_context="context",
    )
    assert res_reasoning["status"] == "error"
    assert res_reasoning["error_code"] == "VALIDATION_ERROR"
    assert "Reasoning exceeds" in res_reasoning["message"]

    # Oversized user_task
    res_task = await _execute_firewall_intent(
        amount_usd=25.0,
        merchant="store@example.com",
        description="item",
        reasoning="reason",
        user_task="x" * (MAX_LIMITS["user_task"] + 1),
        source_context="context",
    )
    assert res_task["status"] == "error"
    assert "User task exceeds" in res_task["message"]

    # Oversized source_context
    res_context = await _execute_firewall_intent(
        amount_usd=25.0,
        merchant="store@example.com",
        description="item",
        reasoning="reason",
        user_task="task",
        source_context="x" * (MAX_LIMITS["source_context"] + 1),
    )
    assert res_context["status"] == "error"
    assert "Source context exceeds" in res_context["message"]


@pytest.mark.asyncio
async def test_mcp_execute_firewall_intent_error_handling_401_422_429():
    """Verify 401, 422, and 429 errors produce clean, non-leaking messages."""
    for status_code, expected_code in [
        (401, "UNAUTHORIZED"),
        (422, "UNPROCESSABLE_ENTITY"),
        (429, "RATE_LIMITED"),
    ]:
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = "Internal stack or detail"
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            result = await _execute_firewall_intent(
                amount_usd=10.0,
                merchant="seller@example.com",
                description="Item",
                reasoning="Reason",
                user_task="Task",
                source_context="Context",
                mandate_id="mnd-001",
            )

            assert result["status"] == "error"
            assert result["error_code"] == expected_code
            assert "Internal stack" not in result["message"]
