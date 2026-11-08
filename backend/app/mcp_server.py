"""FastMCP Server for Agent Payment Firewall.

Exposes `submit_payment_intent` as a hardened MCP tool so autonomous agents
(Claude Desktop, Cursor, LangChain, etc.) can discover and submit payment
requests through the Spendlatch deterministic firewall.

Security invariants:
1. Identity is derived strictly from server-configured credentials (MCP_AGENT_API_KEY).
   Callers cannot specify or spoof `agent_id`.
2. `dry_run` is server-controlled via MCP_DRY_RUN (defaults to True; hosted demo forces True).
   Callers cannot override dry_run to live financial movement.
3. Callers receive only generic sanitized responses ({intent_id, decision, status, reason, escalated}).
   Risk internals (canary honeypot calls, judge scores, prompt versions) are never leaked.
4. Input lengths strictly enforce API constraints before dispatch.
5. Timeouts are set to 90 seconds, with clear error handling for 401, 422, and 429.
"""

from typing import Any, Dict, Optional
import os
import sys

# FastMCP initialization
try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore

mcp = FastMCP("Spendlatch Payment Firewall") if FastMCP else None

DEFAULT_FIREWALL_URL = os.environ.get("FIREWALL_BASE_URL", "http://localhost:8000")
DEFAULT_MANDATE_ID = os.environ.get("AGENT_MANDATE_ID", "mnd-prod-001")

# Field limit constants aligned with backend API specifications
MAX_LIMITS = {
    "merchant": 255,
    "description": 2000,
    "reasoning": 4000,
    "user_task": 2000,
    "source_context": 50000,
}


def _get_server_dry_run() -> bool:
    """Read server-controlled dry_run policy. Hosted demo strictly forces True."""
    val = os.environ.get("MCP_DRY_RUN", "true").strip().lower()
    return val in {"1", "true", "yes", "on"}


async def _execute_firewall_intent(
    amount_usd: float,
    merchant: str,
    description: str,
    reasoning: str,
    user_task: str,
    source_context: str,
    mandate_id: Optional[str] = None,
    firewall_url: Optional[str] = None,
    agent_api_key: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Internal helper to validate and dispatch payment intent via HTTP to Spendlatch firewall."""
    # Reject forbidden caller-controlled security overrides
    if "agent_id" in kwargs:
        return {
            "status": "error",
            "error_code": "FORBIDDEN_PARAMETER",
            "message": "Callers cannot supply 'agent_id'; agent identity is derived from server credentials.",
        }
    if "dry_run" in kwargs:
        return {
            "status": "error",
            "error_code": "FORBIDDEN_PARAMETER",
            "message": "Callers cannot override 'dry_run'; dry_run is controlled by server environment policy.",
        }

    # Validate inputs against API boundary constraints
    if not merchant or len(merchant) > MAX_LIMITS["merchant"]:
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": f"Merchant identifier is required and must not exceed {MAX_LIMITS['merchant']} characters.",
        }
    if description and len(description) > MAX_LIMITS["description"]:
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": f"Description exceeds maximum length of {MAX_LIMITS['description']} characters.",
        }
    if reasoning and len(reasoning) > MAX_LIMITS["reasoning"]:
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": f"Reasoning exceeds maximum length of {MAX_LIMITS['reasoning']} characters.",
        }
    if user_task and len(user_task) > MAX_LIMITS["user_task"]:
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": f"User task exceeds maximum length of {MAX_LIMITS['user_task']} characters.",
        }
    if source_context and len(source_context) > MAX_LIMITS["source_context"]:
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": f"Source context exceeds maximum length of {MAX_LIMITS['source_context']} characters.",
        }

    if amount_usd <= 0:
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "Amount must be a positive number.",
        }

    import httpx

    target_url = (firewall_url or DEFAULT_FIREWALL_URL).rstrip("/") + "/intents"
    target_mandate = mandate_id or DEFAULT_MANDATE_ID
    amount_cents = int(round(amount_usd * 100))

    # Resolve server authentication credentials
    token = (
        agent_api_key
        or os.environ.get("MCP_AGENT_API_KEY")
        or os.environ.get("AGENT_TOKEN")
        or os.environ.get("AGENT_API_KEY")
    )
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Agent-Key"] = token

    dry_run = _get_server_dry_run()

    payload = {
        "mandate_id": target_mandate,
        "amount": amount_cents,
        "currency": "USD",
        "merchant": merchant,
        "description": description or "",
        "reasoning": reasoning or "",
        "user_task": user_task or "",
        "source_context": source_context or "",
        "idempotency_key": f"mcp-{int(amount_cents)}-{os.urandom(8).hex()}",
        "dry_run": dry_run,
    }

    try:
        # Enforce 90-second timeout for full LLM Judge evaluation cycles
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(target_url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                decision = data.get("decision", "unknown")
                intent_status = data.get("status", decision)
                escalated = decision == "escalated" or intent_status == "escalated"

                # Extract sanitized generic reason
                raw_reasons = data.get("reasons") or data.get("decision_reasons") or []
                generic_reason = "Payment approved by firewall policy."
                if decision != "approved":
                    if raw_reasons:
                        first = raw_reasons[0]
                        generic_reason = first.get("message") if isinstance(first, dict) else str(first)
                    else:
                        generic_reason = "Payment halted or held for human review by firewall policy."

                # Invariant: Never return risk_details, canary calls, or judge internals to the caller agent
                return {
                    "intent_id": data.get("intent_id") or data.get("id"),
                    "decision": decision,
                    "status": intent_status,
                    "reason": generic_reason,
                    "escalated": escalated,
                }
            elif resp.status_code == 401:
                return {
                    "status": "error",
                    "error_code": "UNAUTHORIZED",
                    "message": "Authentication failed: invalid or missing MCP_AGENT_API_KEY.",
                }
            elif resp.status_code == 422:
                return {
                    "status": "error",
                    "error_code": "UNPROCESSABLE_ENTITY",
                    "message": "Payment request failed schema validation on the firewall.",
                }
            elif resp.status_code == 429:
                return {
                    "status": "error",
                    "error_code": "RATE_LIMITED",
                    "message": "Rate limit exceeded or demo quota exhausted on the firewall.",
                }
            else:
                return {
                    "status": "error",
                    "error_code": f"HTTP_{resp.status_code}",
                    "message": "The payment firewall returned an unexpected error.",
                }
    except httpx.TimeoutException:
        return {
            "status": "error",
            "error_code": "TIMEOUT",
            "message": "The payment firewall evaluation timed out after 90 seconds.",
        }
    except Exception:
        # Never leak raw stack traces or internal server error text
        return {
            "status": "error",
            "error_code": "CONNECTION_ERROR",
            "message": "Failed to connect to the Spendlatch payment firewall.",
        }


if mcp is not None:
    @mcp.tool()
    async def submit_payment_intent(
        amount_usd: float,
        merchant: str,
        description: str,
        reasoning: str,
        user_task: str,
        source_context: str,
        mandate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a payment intent to the Spendlatch Payment Firewall for evaluation.

        Args:
            amount_usd: Amount in USD dollars (e.g. 25.50).
            merchant: Recipient or merchant email/identifier (e.g. seller@store.com).
            description: Concise purchase title or item name (max 2000 chars).
            reasoning: Why the agent decided this payment is necessary (max 4000 chars).
            user_task: The original goal given to the agent by the human user (max 2000 chars).
            source_context: Raw untrusted page text or external context read by the agent (max 50000 chars).
            mandate_id: Optional mandate ID under which payment should be evaluated.

        Returns:
            Dict containing sanitized decision ('approved', 'denied', or 'escalated'),
            associated intent ID, status, generic reason, and escalation boolean.
            Internal risk heuristics are strictly kept private from caller agents.
        """
        return await _execute_firewall_intent(
            amount_usd=amount_usd,
            merchant=merchant,
            description=description,
            reasoning=reasoning,
            user_task=user_task,
            source_context=source_context,
            mandate_id=mandate_id,
        )


def main():
    """Run the MCP server over stdio or command-line specified transport."""
    if mcp is None:
        sys.stderr.write("Error: fastmcp is not installed. Install via `pip install fastmcp`.\n")
        sys.exit(1)
    mcp.run()


if __name__ == "__main__":
    main()
