"""OpenAI-compatible LLM client supporting resilience, retries, caching, fallback providers, structured JSON, and tool calling."""
import asyncio
from dataclasses import dataclass, field
import hashlib
import json
import logging
import random
import time
from typing import Any, Optional, Union

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for all LLM client failures (timeout, HTTP error, malformed output)."""
    pass


@dataclass
class LLMResponseMeta:
    """Metadata tracking provider, model, latency, and cache hit."""
    provider: str
    model: str
    latency_ms: float
    cached: bool = False
    retries: int = 0
    fallback_used: bool = False


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class InMemoryTTLCache:
    """Thread/asyncio-safe in-memory TTL cache with max entries."""

    def __init__(self, ttl_seconds: int = 600, max_entries: int = 500):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() > entry.expires_at:
            self._cache.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_entries:
            # Purge expired first
            now = time.time()
            expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]
            for k in expired_keys:
                self._cache.pop(k, None)
            # If still full, pop an arbitrary item
            if len(self._cache) >= self.max_entries:
                first_k = next(iter(self._cache))
                self._cache.pop(first_k, None)
        self._cache[key] = CacheEntry(value=value, expires_at=time.time() + self.ttl_seconds)

    def clear(self) -> None:
        self._cache.clear()


llm_cache = InMemoryTTLCache(
    ttl_seconds=getattr(settings, "LLM_CACHE_TTL_SECONDS", 600),
    max_entries=getattr(settings, "LLM_CACHE_MAX_ENTRIES", 500),
)


class LLMClient:
    """Async OpenAI-compatible chat-completions client with retries, fallback, and caching."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        fallback_base_url: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.base_url = (base_url if base_url is not None else settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self.fallback_base_url = (fallback_base_url if fallback_base_url is not None else getattr(settings, "LLM_FALLBACK_BASE_URL", "")).rstrip("/")
        self.fallback_api_key = fallback_api_key if fallback_api_key is not None else getattr(settings, "LLM_FALLBACK_API_KEY", "")
        self.fallback_model = fallback_model if fallback_model is not None else getattr(settings, "LLM_FALLBACK_MODEL", "")

    def _headers(self, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _compute_cache_key(model: str, system: str, user: str, tools: Optional[list] = None) -> str:
        serialized = json.dumps(
            {"model": model, "system": system, "user": user, "tools": tools or []},
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def _post_with_retry(
        self,
        base_url: str,
        api_key: str,
        payload: dict[str, Any],
        max_retries: int = 2,
    ) -> tuple[httpx.Response, int]:
        """Post request with up to max_retries on 429/500/502/503/timeouts honoring Retry-After."""
        url = f"{base_url}/chat/completions"
        headers = self._headers(api_key)
        attempt = 0
        retries_used = 0

        while True:
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                # Check if retryable status
                if resp.status_code in (429, 500, 502, 503):
                    if attempt < max_retries:
                        attempt += 1
                        retries_used += 1
                        # Check Retry-After header
                        retry_after = resp.headers.get("Retry-After")
                        delay = None
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = None
                        if delay is None:
                            # Exponential backoff with jitter: 0.5 * 2^attempt + jitter
                            delay = (0.5 * (2 ** (attempt - 1))) + random.uniform(0.1, 0.4)
                        logger.warning(
                            "LLM call returned %d, retrying attempt %d/%d after %.2fs",
                            resp.status_code,
                            attempt,
                            max_retries,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMError(f"LLM API returned error code {resp.status_code} after retries: {resp.text[:200]}")

                if resp.status_code != 200:
                    raise LLMError(f"LLM API returned error code {resp.status_code}: {resp.text[:200]}")

                return resp, retries_used

            except httpx.TimeoutException as exc:
                if attempt < max_retries:
                    attempt += 1
                    retries_used += 1
                    delay = (0.5 * (2 ** (attempt - 1))) + random.uniform(0.1, 0.4)
                    logger.warning("LLM call timed out, retrying attempt %d/%d after %.2fs", attempt, max_retries, delay)
                    await asyncio.sleep(delay)
                    continue
                logger.warning("LLM call timed out after %ds and %d retries", self.timeout, max_retries)
                raise LLMError(f"LLM request timed out after retries: {exc}") from exc
            except httpx.RequestError as exc:
                if attempt < max_retries:
                    attempt += 1
                    retries_used += 1
                    delay = (0.5 * (2 ** (attempt - 1))) + random.uniform(0.1, 0.4)
                    logger.warning("LLM request network error %s, retrying attempt %d/%d", exc, attempt, max_retries)
                    await asyncio.sleep(delay)
                    continue
                raise LLMError(f"LLM network error after retries: {exc}") from exc

    async def _execute_with_resilience(
        self,
        model: str,
        payload_maker: Any,
        cache_key: Optional[str] = None,
    ) -> tuple[dict[str, Any], LLMResponseMeta]:
        """Execute request checking cache, primary provider retries, then optional fallback."""
        cache_enabled = getattr(settings, "LLM_CACHE_ENABLED", True)
        if cache_enabled and cache_key:
            cached_val = llm_cache.get(cache_key)
            if cached_val is not None:
                meta = LLMResponseMeta(
                    provider="cache",
                    model=model,
                    latency_ms=0.0,
                    cached=True,
                )
                return cached_val, meta

        start_time = time.time()
        primary_err = None
        retries_used = 0

        # 1. Primary Attempt
        try:
            payload = payload_maker(model)
            resp, retries_used = await self._post_with_retry(
                base_url=self.base_url,
                api_key=self.api_key,
                payload=payload,
                max_retries=2,
            )
            res_json = resp.json()
            latency = (time.time() - start_time) * 1000.0
            meta = LLMResponseMeta(
                provider="primary",
                model=model,
                latency_ms=round(latency, 2),
                cached=False,
                retries=retries_used,
                fallback_used=False,
            )
            return res_json, meta
        except Exception as exc:
            primary_err = exc
            logger.warning("Primary LLM provider failed: %s", exc)

        # 2. Fallback Attempt (if configured)
        if self.fallback_base_url and (self.fallback_model or model):
            fallback_model = self.fallback_model or model
            logger.info("Attempting fallback LLM provider (%s, model=%s)", self.fallback_base_url, fallback_model)
            try:
                payload = payload_maker(fallback_model)
                resp, _ = await self._post_with_retry(
                    base_url=self.fallback_base_url,
                    api_key=self.fallback_api_key,
                    payload=payload,
                    max_retries=0,  # Try fallback once
                )
                res_json = resp.json()
                latency = (time.time() - start_time) * 1000.0
                meta = LLMResponseMeta(
                    provider="fallback",
                    model=fallback_model,
                    latency_ms=round(latency, 2),
                    cached=False,
                    retries=retries_used,
                    fallback_used=True,
                )
                return res_json, meta
            except Exception as fb_exc:
                logger.error("Fallback LLM provider also failed: %s", fb_exc)
                raise LLMError(f"Both primary and fallback LLM failed. Primary: {primary_err}; Fallback: {fb_exc}") from fb_exc

        # If no fallback or fallback failed without raising LLMError
        if isinstance(primary_err, LLMError):
            raise primary_err
        raise LLMError(f"LLM request failed: {primary_err}") from primary_err

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        schema: Optional[type[BaseModel]] = None,
    ) -> tuple[dict[str, Any], LLMResponseMeta]:
        """
        Request completion forced to produce valid JSON output conforming to schema.
        Temperature is 0. Keys and full prompts are never logged.
        Returns (parsed_dict, response_meta).
        """
        cache_key = self._compute_cache_key(model, system, user)

        def make_payload(m: str) -> dict[str, Any]:
            return {
                "model": m,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }

        res_json, meta = await self._execute_with_resilience(
            model=model,
            payload_maker=make_payload,
            cache_key=cache_key,
        )

        if meta.cached:
            return res_json, meta

        try:
            content = res_json["choices"][0]["message"]["content"]
            parsed = self._extract_json(content)
        except Exception as exc:
            logger.warning("Malformed LLM completion response")
            raise LLMError(f"Malformed LLM response: {exc}") from exc

        if schema is not None:
            try:
                validated = schema.model_validate(parsed)
                parsed_res = validated.model_dump()
            except Exception as exc:
                logger.warning("LLM response failed schema validation")
                raise LLMError(f"LLM response failed schema validation: {exc}") from exc
        else:
            parsed_res = parsed

        if getattr(settings, "LLM_CACHE_ENABLED", True):
            llm_cache.set(cache_key, parsed_res)

        return parsed_res, meta

    async def complete_with_tools(
        self,
        model: str,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], LLMResponseMeta]:
        """
        Request completion with specified tool definitions.
        Returns (list_of_tool_calls, response_meta).
        """
        cache_key = self._compute_cache_key(model, system, user, tools=tools)

        def make_payload(m: str) -> dict[str, Any]:
            return {
                "model": m,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "tools": tools,
                "tool_choice": "auto",
            }

        res_json, meta = await self._execute_with_resilience(
            model=model,
            payload_maker=make_payload,
            cache_key=cache_key,
        )

        if meta.cached:
            return res_json, meta

        try:
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

            if getattr(settings, "LLM_CACHE_ENABLED", True):
                llm_cache.set(cache_key, extracted)

            return extracted, meta
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
