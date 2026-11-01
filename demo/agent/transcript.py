"""Transcript logging and sanitization for agent execution runs."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Optional


def sanitize_secrets(obj: Any, secrets_to_mask: Optional[list[str]] = None) -> Any:
    """Recursively mask API keys, tokens, and sensitive secrets from transcript objects."""
    secrets = [s for s in (secrets_to_mask or []) if s and len(s) > 4]

    if isinstance(obj, str):
        val = obj
        for secret in secrets:
            val = val.replace(secret, "[REDACTED_SECRET]")
        # General pattern redactions
        val = re.sub(r'([A-Za-z0-9_-]{20,})', lambda m: m.group(0) if not any(s in m.group(0) for s in secrets) else '[REDACTED_KEY]', val)
        return val

    elif isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ["key", "token", "secret", "password", "authorization"]):
                if isinstance(v, str):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = sanitize_secrets(v, secrets)
            else:
                sanitized[k] = sanitize_secrets(v, secrets)
        return sanitized

    elif isinstance(obj, list):
        return [sanitize_secrets(item, secrets) for item in obj]

    return obj


class RunTranscript:
    """Collects step-by-step agent interactions, tool calls, decisions, and timings."""

    def __init__(
        self,
        task: str,
        variant: str,
        mode: str,
        model: str,
        secrets_to_mask: Optional[list[str]] = None,
    ):
        self.task = task
        self.variant = variant
        self.mode = mode
        self.model = model
        self.secrets_to_mask = secrets_to_mask or []
        
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.duration_ms: int = 0
        self.llm_calls: int = 0
        
        self.messages: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.firewall_decisions: list[dict[str, Any]] = []
        self.final_response: str = ""
        self.error: Optional[str] = None

    def record_llm_call(self):
        self.llm_calls += 1

    def add_message(self, role: str, content: Any, tool_calls: Optional[list] = None):
        entry = {"role": role, "content": content}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        self.messages.append(entry)

    def record_tool_execution(
        self,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int = 0,
    ):
        self.tool_calls.append({
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "arguments": arguments,
            "result": result,
            "duration_ms": duration_ms,
        })
        if tool_name == "submit_payment_intent":
            self.firewall_decisions.append({
                "request": arguments,
                "result": result,
            })

    def finish(self, final_response: str = "", error: Optional[str] = None):
        self.end_time = datetime.now(timezone.utc)
        self.duration_ms = int((self.end_time - self.start_time).total_seconds() * 1000)
        self.final_response = final_response
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        raw = {
            "task": self.task,
            "variant": self.variant,
            "mode": self.mode,
            "model": self.model,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "llm_calls": self.llm_calls,
            "tool_calls_count": len(self.tool_calls),
            "tool_calls": self.tool_calls,
            "firewall_decisions": self.firewall_decisions,
            "final_response": self.final_response,
            "error": self.error,
            "messages": self.messages,
        }
        return sanitize_secrets(raw, self.secrets_to_mask)

    def save(self, filepath: str) -> str:
        """Save sanitized transcript to JSON file."""
        data = self.to_dict()
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(p)
