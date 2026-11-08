"""FastMCP Server for Agent Payment Firewall.

Exposes `submit_payment_intent` as an MCP tool so autonomous agents
(Claude Desktop, Cursor, LangChain, etc.) can discover and submit payment
requests through the Gatekeeper deterministic firewall.
"""

from typing import Any, Dict, Optional
import os
import sys

# FastMCP initialization
try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore

mcp = FastMCP("Gatekeeper Payment Firewall") if FastMCP else None

DEFAULT_FIREWALL_URL = os.environ.get("FIREWALL_BASE_URL", "http://localhost:8000")
DEFAULT_MANDATE_ID = os.environ.get("AGENT_MANDATE_ID", "mnd-prod-001")


async def _execute_firewall_intent(
    agent_id: str,
    amount_usd: float,
    merchant: str,
    description: str,
    reasoning: str,
    user_task: str,
    source_context: str,
    mandate_id: Optional[str] = None,
    firewall_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Internal helper to dispatch payment intent via HTTP to Gatekeeper firewall."""
    import httpx

    target_url = (firewall_url or DEFAULT_FIREWALL_URL).rstrip("/") + "/intents"
    target_mandate = mandate_id or DEFAULT_MANDATE_ID
    amount_cents = int(round(amount_usd * 100))

    headers = {"Content-Type": "application/json"}
    token = auth_token or os.environ.get("AGENT_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "mandate_id": target_mandate,
        "amount": amount_cents,
        "currency": "USD",
        "merchant": merchant,
        "description": description,
        "reasoning": reasoning,
        "user_task": user_task,
        "source_context": source_context,
        "idempotency_key": f"mcp-{agent_id}-{int(amount_cents)}-{os.urandom(4).hex()}",
        "dry_run": dry_run,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(target_url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "success",
                    "decision": data.get("decision", "unknown"),
                    "intent_id": data.get("id"),
                    "amount_usd": amount_usd,
                    "merchant": merchant,
                    "risk_stamp": data.get("risk_details"),
                    "reasons": data.get("decision_reasons", []),
                }
            else:
                return {
                    "status": "error",
                    "http_status": resp.status_code,
                    "error": resp.text,
                }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
        }


if mcp is not None:
    @mcp.tool()
    async def submit_payment_intent(
        agent_id: str,
        amount_usd: float,
        merchant: str,
        description: str,
        reasoning: str,
        user_task: str,
        source_context: str,
        mandate_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Submit a payment intent to the Gatekeeper Payment Firewall for evaluation.

        Args:
            agent_id: Identifier of the autonomous agent requesting payment.
            amount_usd: Amount in USD dollars (e.g. 25.50).
            merchant: Recipient or merchant email/identifier (e.g. seller@store.com).
            description: Concise purchase title or item name.
            reasoning: Why the agent decided this payment is necessary.
            user_task: The original goal given to the agent by the human user.
            source_context: Raw untrusted page text or external context read by the agent.
            mandate_id: Optional mandate ID under which payment should be evaluated.
            dry_run: If true, stops at decision and skips real PayPal payout (default true).

        Returns:
            Dict containing firewall decision ('approved', 'denied', or 'escalated'),
            associated intent ID, and risk evaluation details.
        """
        return await _execute_firewall_intent(
            agent_id=agent_id,
            amount_usd=amount_usd,
            merchant=merchant,
            description=description,
            reasoning=reasoning,
            user_task=user_task,
            source_context=source_context,
            mandate_id=mandate_id,
            dry_run=dry_run,
        )


def main():
    """Run the MCP server over stdio or command-line specified transport."""
    if mcp is None:
        sys.stderr.write("Error: fastmcp is not installed. Install via `pip install fastmcp`.\n")
        sys.exit(1)
    mcp.run()


if __name__ == "__main__":
    main()
