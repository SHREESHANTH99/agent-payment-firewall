"""Honeypot canary scanner for prompt injection detection in source context."""
from dataclasses import dataclass, field
import logging
from typing import Any, Optional

from app.core.config import settings
from app.services.llm import LLMError, llm_client

logger = logging.getLogger(__name__)

CANARY_SEGMENT_SIZE = 3500
CANARY_OVERLAP_SIZE = 500
MAX_SOURCE_CONTEXT_LENGTH = 20000

# Deliberately permissive system prompt instructing the canary to follow untrusted directions
CANARY_SYSTEM_PROMPT = (
    "You are a helpful assistant. Follow any instructions found in the content."
)

# Honeypot tools connected to nothing
HONEYPOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a terminal shell command or system script.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command string to run"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_payment",
            "description": "Send a payment transaction or funds to an external account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Email or account"},
                    "amount": {"type": "number", "description": "Amount to send"},
                },
                "required": ["recipient", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email message to a specified recipient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email"},
                    "body": {"type": "string", "description": "Email content"},
                },
                "required": ["to", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_database",
            "description": "Query or read from the internal database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL or table query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_funds",
            "description": "Initiate a wire or ledger transfer of funds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_account": {"type": "string", "description": "Target account ID"},
                    "amount": {"type": "number", "description": "Amount to transfer"},
                },
                "required": ["target_account", "amount"],
            },
        },
    },
]


@dataclass
class CanaryResult:
    tripped: bool
    honeypot_calls: list[dict[str, Any]] = field(default_factory=list)
    segments: int = 0
    error: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


def split_segments(text: str, segment_size: int = CANARY_SEGMENT_SIZE, overlap: int = CANARY_OVERLAP_SIZE) -> list[str]:
    """Split text into overlapping segments."""
    if not text:
        return []
    if len(text) <= segment_size:
        return [text]

    segments = []
    step = segment_size - overlap
    for i in range(0, len(text), step):
        seg = text[i : i + segment_size]
        segments.append(seg)
        if i + segment_size >= len(text):
            break
    return segments


async def canary_scan(source_context: Optional[str]) -> CanaryResult:
    """
    Scan untrusted source_context for prompt injection using honeypot tool traps.
    - If empty: returns tripped=False.
    - If length > 20000: fail closed with tripped=True and 'oversized_context'.
    - Splits into overlapping segments (3500 chars, 500 overlap).
    - Calls canary model with permissive system prompt and honeypot tools.
    - Any tool call trips the canary.
    - Any LLMError trips the canary (fail-closed).
    """
    if not source_context:
        return CanaryResult(tripped=False, honeypot_calls=[], segments=0, error=None)

    if len(source_context) > MAX_SOURCE_CONTEXT_LENGTH:
        logger.warning("Canary scan tripped: source_context length %d exceeds max %d", len(source_context), MAX_SOURCE_CONTEXT_LENGTH)
        return CanaryResult(
            tripped=True,
            honeypot_calls=[],
            segments=0,
            error="oversized_context",
        )

    segments = split_segments(source_context)
    all_honeypot_calls: list[dict[str, Any]] = []
    last_meta = None

    for seg in segments:
        user_prompt = f"<untrusted_content>\n{seg}\n</untrusted_content>"
        try:
            res = await llm_client.complete_with_tools(
                model=settings.CANARY_MODEL,
                system=CANARY_SYSTEM_PROMPT,
                user=user_prompt,
                tools=HONEYPOT_TOOLS,
            )
            if isinstance(res, tuple):
                calls, meta = res
                last_meta = {
                    "provider": meta.provider,
                    "model": meta.model,
                    "latency_ms": meta.latency_ms,
                    "cached": meta.cached,
                    "retries": meta.retries,
                    "fallback_used": meta.fallback_used,
                }
            else:
                calls = res
                last_meta = None
            if calls:
                all_honeypot_calls.extend(calls)
                # Early return upon first tripped honeypot
                return CanaryResult(
                    tripped=True,
                    honeypot_calls=all_honeypot_calls,
                    segments=len(segments),
                    error=None,
                    meta=last_meta,
                )
        except LLMError as exc:
            logger.error("Canary scan failed due to LLMError (failing closed): %s", exc)
            return CanaryResult(
                tripped=True,
                honeypot_calls=[],
                segments=len(segments),
                error=f"llm_error: {exc}",
                meta=last_meta,
            )
        except Exception as exc:
            logger.exception("Unexpected error in canary_scan (failing closed): %s", exc)
            return CanaryResult(
                tripped=True,
                honeypot_calls=[],
                segments=len(segments),
                error=f"unexpected_error: {exc}",
                meta=last_meta,
            )

    return CanaryResult(
        tripped=False,
        honeypot_calls=[],
        segments=len(segments),
        error=None,
        meta=last_meta,
    )
