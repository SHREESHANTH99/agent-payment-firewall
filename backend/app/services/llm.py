"""OpenAI-compatible LLM client supporting structured JSON completion and tool calling."""
import json
import logging
from typing import Any, Optional, Union

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for all LLM client failures (timeout, HTTP error, malformed output)."""
    pass


class LLMClient:
    """Async OpenAI-compatible chat-completions client."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        schema: Optional[type[BaseModel]] = None,
    ) -> dict[str, Any]:
        """
        Request completion forced to produce valid JSON output conforming to schema.
        Temperature is 0. Keys and full prompts are never logged.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("LLM call timed out after %ds", self.timeout)
            raise LLMError(f"LLM request timed out: {exc}") from exc
        except Exception as exc:
            logger.warning("LLM HTTP network error: %s", type(exc).__name__)
            raise LLMError(f"LLM network error: {exc}") from exc

        if resp.status_code != 200:
            logger.warning("LLM API returned status %d", resp.status_code)
            raise LLMError(f"LLM API returned error code {resp.status_code}: {resp.text[:200]}")

        try:
            res_json = resp.json()
            content = res_json["choices"][0]["message"]["content"]
            parsed = self._extract_json(content)
        except Exception as exc:
            logger.warning("Malformed LLM completion response")
            raise LLMError(f"Malformed LLM response: {exc}") from exc

        if schema is not None:
            try:
                validated = schema.model_validate(parsed)
                return validated.model_dump()
            except Exception as exc:
                logger.warning("LLM response failed schema validation")
                raise LLMError(f"LLM response failed schema validation: {exc}") from exc

        return parsed

    async def complete_with_tools(
        self,
        model: str,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Request completion with specified tool definitions.
        Returns list of tool calls requested by the model: [{"name": str, "arguments": dict}].
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "tools": tools,
            "tool_choice": "auto",
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("LLM tool call timed out after %ds", self.timeout)
            raise LLMError(f"LLM tool request timed out: {exc}") from exc
        except Exception as exc:
            logger.warning("LLM HTTP network error: %s", type(exc).__name__)
            raise LLMError(f"LLM tool network error: {exc}") from exc

        if resp.status_code != 200:
            logger.warning("LLM API returned status %d for tool call", resp.status_code)
            raise LLMError(f"LLM API returned error code {resp.status_code}: {resp.text[:200]}")

        try:
            res_json = resp.json()
            message = res_json["choices"][0]["message"]
            raw_tool_calls = message.get("tool_calls") or []

            extracted: list[dict[str, Any]] = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {"raw": raw_args}
                else:
                    args = raw_args
                extracted.append({"name": name, "arguments": args})

            return extracted
        except Exception as exc:
            logger.warning("Malformed tool call response from LLM")
            raise LLMError(f"Malformed tool call response: {exc}") from exc

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract and parse JSON from content string, handling optional code blocks."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # Direct parse
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # Substring extraction
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])

        raise ValueError(f"No JSON object could be decoded from: {cleaned[:100]}...")


llm_client = LLMClient()
