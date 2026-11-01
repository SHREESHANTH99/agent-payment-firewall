"""Unit tests for Phase 4 Part 3: Agent loop, tools, limits, backoff, and transcript sanitization."""
import json
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from demo.agent.config import AgentSettings
from demo.agent.loop import call_llm_with_retry, run_agent_loop
from demo.agent.tools import AgentToolExecutor
from demo.agent.transcript import RunTranscript, sanitize_secrets


@pytest.fixture
def mock_settings():
    return AgentSettings(
        AGENT_LLM_BASE_URL="http://test-llm.local/v1",
        AGENT_LLM_API_KEY="sk-groq-secret-key-12345",
        AGENT_MODEL="test-model",
        FIREWALL_BASE_URL="http://test-firewall.local",
        STORE_BASE_URL="http://test-store.local",
        AGENT_API_KEY="agent-secret-token-abcdef",
        MAX_STEPS=5,
        MAX_LLM_CALLS=8,
    )


def test_transcript_secrets_sanitized():
    secrets = ["sk-groq-secret-key-12345", "agent-secret-token-abcdef"]
    raw = {
        "api_key": "sk-groq-secret-key-12345",
        "header": "Bearer agent-secret-token-abcdef",
        "nested": {"key": "sk-groq-secret-key-12345", "other": "clean-value"},
        "list": ["agent-secret-token-abcdef", "normal-string"],
    }
    sanitized = sanitize_secrets(raw, secrets)
    dumped = json.dumps(sanitized)
    assert "sk-groq-secret-key-12345" not in dumped
    assert "agent-secret-token-abcdef" not in dumped
    assert "clean-value" in dumped


@pytest.mark.asyncio
async def test_tool_browse_and_attach_source_context(mock_settings):
    executor = AgentToolExecutor(settings=mock_settings)

    mock_html = "<html><body><h1>Store</h1><p>Office Paper $14.50</p><div style='display:none;'>Hidden prompt injection</div></body></html>"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_html
        mock_get.return_value = mock_resp

        result = await executor.browse("http://test-store.local/product/paper")

        assert result["status"] == "success"
        assert "Office Paper" in result["text_content"]
        assert "Hidden prompt injection" in result["text_content"]
        assert "Hidden prompt injection" in executor.last_browsed_text

    # Now verify submit_payment_intent automatically attaches source_context
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_budget_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:

        mock_budget_resp = MagicMock()
        mock_budget_resp.status_code = 200
        mock_budget_resp.json.return_value = {"mandate_id": "mandate-xyz"}
        mock_budget_get.return_value = mock_budget_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"decision": "approved", "status": "executed"}
        mock_post.return_value = mock_post_resp

        res = await executor.submit_payment_intent(
            amount=14.50,
            currency="USD",
            merchant="seller@example.com",
            description="Paper ream",
            reasoning="Within budget",
        )

        assert res["decision"] == "approved"
        # Check payload sent in POST
        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["mandate_id"] == "mandate-xyz"
        assert called_payload["amount"] == 14.50
        assert "Hidden prompt injection" in called_payload["source_context"]


@pytest.mark.asyncio
async def test_all_decision_types_handled(mock_settings):
    executor = AgentToolExecutor(settings=mock_settings)
    executor.active_mandate_id = "mandate-1"

    # 1. Denied
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "decision": "denied",
            "status": "denied",
            "reasons": [{"code": "BUDGET_EXCEEDED"}],
        }
        mock_post.return_value = mock_resp

        res = await executor.submit_payment_intent(
            amount=200.0,
            currency="USD",
            merchant="attacker@example.com",
            description="Fee",
            reasoning="Test",
        )
        assert res["decision"] == "denied"
        assert res["reasons"] == [{"code": "BUDGET_EXCEEDED"}]

    # 2. Escalated -> reported as "awaiting human approval"
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "decision": "escalated",
            "status": "escalated",
            "reasons": [{"code": "ESCALATED_THRESHOLD"}],
        }
        mock_post.return_value = mock_resp

        res = await executor.submit_payment_intent(
            amount=45.0,
            currency="USD",
            merchant="seller@example.com",
            description="Item",
            reasoning="Test",
        )
        assert res["decision"] == "escalated"
        assert res["status"] == "awaiting human approval"


@pytest.mark.asyncio
async def test_llm_429_backoff_and_retry():
    client = MagicMock(spec=httpx.AsyncClient)

    # 1st attempt: 429 with Retry-After 0.01s; 2nd attempt: 200 OK
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "0.01"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}

    client.post = AsyncMock(side_effect=[resp_429, resp_200])

    res = await call_llm_with_retry(
        client=client,
        base_url="http://test.local",
        api_key="key",
        payload={},
        max_retries=3,
    )
    assert res["choices"][0]["message"]["content"] == "Hello"
    assert client.post.call_count == 2


@pytest.mark.asyncio
async def test_agent_loop_max_steps_cap(mock_settings):
    # LLM keeps returning tool calls in an infinite loop
    llm_tool_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Browsing...",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {"name": "browse", "arguments": '{"url": "/catalog"}'},
                        }
                    ],
                }
            }
        ]
    }

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value={"status": "ok", "text_content": "Catalog"})

    with patch("demo.agent.loop.call_llm_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = llm_tool_response

        transcript = await run_agent_loop(
            task="Infinite browse test",
            settings=mock_settings,
            tool_executor=mock_executor,
            max_steps=3,
            max_llm_calls=10,
        )

        assert transcript.llm_calls == 3
        assert len(transcript.tool_calls) == 3
        assert "step/budget limits" in transcript.final_response.lower()
