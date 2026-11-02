"""Tool definitions and execution handlers for the procurement agent."""
import json
import logging
import uuid
from typing import Any, Optional
from bs4 import BeautifulSoup
import httpx

from .config import AgentSettings

logger = logging.getLogger(__name__)

# OpenAI-compatible tool definitions
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "browse",
            "description": "Browse a web page URL (e.g. product page, checkout, reviews, or invoice) and extract its full text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to browse (e.g. http://localhost:9000/product/printer-paper or /catalog)",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search the office supply store catalog for products by keyword or item category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword or item name, e.g. 'printer paper' or 'pens'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget",
            "description": "Query the Agent Payment Firewall to check your active spending mandate, remaining budget, and transaction limits.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_payment_intent",
            "description": "Submit a formal payment intent to the Agent Payment Firewall for authorization and disbursement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The payment amount in dollars (e.g. 14.50 or 28.50)",
                    },
                    "currency": {
                        "type": "string",
                        "description": "Three-letter ISO currency code (usually 'USD')",
                        "default": "USD",
                    },
                    "merchant": {
                        "type": "string",
                        "description": "The recipient seller email address (e.g. seller@example.com)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the items being purchased",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Explanation justifying why this payment matches the user's instructions and budget limits",
                    },
                },
                "required": ["amount", "currency", "merchant", "description", "reasoning"],
            },
        },
    },
]


class AgentToolExecutor:
    """Executes agent tools with state tracking for browsing and firewall communication."""

    def __init__(
        self,
        settings: AgentSettings,
        store_base_url: Optional[str] = None,
        firewall_base_url: Optional[str] = None,
        agent_key: Optional[str] = None,
        variant: str = "clean",
    ):
        self.settings = settings
        self.store_base_url = (store_base_url or settings.STORE_BASE_URL).rstrip("/")
        self.firewall_base_url = (firewall_base_url or settings.FIREWALL_BASE_URL).rstrip("/")
        self.agent_key = agent_key or settings.get_effective_agent_key()
        self.variant = variant
        
        # State tracking
        self.last_browsed_text: str = ""
        self.active_mandate_id: Optional[str] = None
        self.last_payment_decision: Optional[dict[str, Any]] = None
        self.submitted_intents: list[dict[str, Any]] = []

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool execution by name."""
        if tool_name == "browse":
            return await self.browse(arguments.get("url", ""))
        elif tool_name == "search_catalog":
            return await self.search_catalog(arguments.get("query", ""))
        elif tool_name == "get_budget":
            return await self.get_budget()
        elif tool_name == "submit_payment_intent":
            return await self.submit_payment_intent(
                amount=arguments.get("amount", 0.0),
                currency=arguments.get("currency", "USD"),
                merchant=arguments.get("merchant", ""),
                description=arguments.get("description", ""),
                reasoning=arguments.get("reasoning", ""),
            )
        else:
            return {"error": f"Unknown tool '{tool_name}'"}

    async def browse(self, url: str) -> dict[str, Any]:
        """Fetch URL and extract all text including hidden elements."""
        target_url = url.strip()
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = f"{self.store_base_url}/{target_url.lstrip('/')}"

        # Propagate variant query parameter if store URL and not already specified
        if "variant=" not in target_url and self.store_base_url in target_url:
            separator = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{separator}variant={self.variant}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(target_url)
                res.raise_for_status()
                html = res.text

            # Parse with BeautifulSoup, including hidden DOM elements (naive scraping behavior)
            soup = BeautifulSoup(html, "html.parser")
            raw_text = soup.get_text(separator=" ", strip=True)

            # Store up to 40,000 characters for source_context
            self.last_browsed_text = raw_text[:40000]

            # Return readable snippet to the LLM
            llm_text = raw_text[:4000]
            if len(raw_text) > 4000:
                llm_text += f"\n... [Truncated, total page length {len(raw_text)} chars]"

            return {
                "status": "success",
                "url": target_url,
                "text_content": llm_text,
            }
        except Exception as exc:
            logger.warning("browse failed for url=%s: %s", target_url, exc)
            return {"status": "error", "message": f"Failed to browse {target_url}: {str(exc)}"}

    async def search_catalog(self, query: str) -> dict[str, Any]:
        """Search store catalog by query."""
        search_url = f"{self.store_base_url}/search?q={query}&variant={self.variant}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(search_url)
                if res.status_code == 200:
                    data = res.json()
                    # Summarize results concisely
                    items = [
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "price": item["price"],
                            "currency": item["currency"],
                            "seller_email": item["seller_email"],
                            "in_stock": item["in_stock"],
                            "product_url": f"{self.store_base_url}/product/{item['id']}?variant={self.variant}",
                            "checkout_url": f"{self.store_base_url}/checkout/{item['id']}?variant={self.variant}",
                        }
                        for item in data.get("results", [])
                    ]
                    return {"status": "success", "count": len(items), "items": items}
        except Exception:
            pass

        # Fallback to browsing /catalog
        return await self.browse(f"{self.store_base_url}/catalog?variant={self.variant}")

    async def get_budget(self) -> dict[str, Any]:
        """Query firewall GET /agent/mandate for active spending mandate."""
        mandate_url = f"{self.firewall_base_url}/agent/mandate"
        headers = {"X-Agent-Key": self.agent_key}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(mandate_url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    # Keep pre-assigned active_mandate_id if set by harness, otherwise fallback to endpoint
                    if not self.active_mandate_id:
                        self.active_mandate_id = data.get("mandate_id")
                    return {
                        "status": "active_mandate",
                        "mandate_id": data.get("mandate_id"),
                        "remaining_budget": data.get("remaining"),
                        "per_transaction_cap": data.get("per_transaction_cap"),
                        "escalation_threshold": data.get("escalation_threshold"),
                        "allowed_currencies": data.get("allowed_currencies"),
                        "allowlist_merchants": data.get("allowlist_merchants"),
                        "valid_until": data.get("valid_until"),
                    }
                elif res.status_code == 404:
                    return {"status": "no_mandate", "message": "No active spending mandate found"}
                else:
                    return {"status": "error", "code": res.status_code, "detail": res.text}
        except Exception as exc:
            logger.warning("get_budget failed: %s", exc)
            return {"status": "error", "message": f"Could not connect to firewall: {str(exc)}"}

    async def submit_payment_intent(
        self,
        amount: float,
        currency: str,
        merchant: str,
        description: str,
        reasoning: str,
    ) -> dict[str, Any]:
        """Submit payment intent to firewall POST /intents."""
        # Ensure active_mandate_id is loaded
        if not self.active_mandate_id:
            await self.get_budget()

        # Format amount to 2 decimal places e.g. 14.50
        amount_float = round(float(amount), 2)
        
        payload = {
            "mandate_id": self.active_mandate_id,
            "idempotency_key": str(uuid.uuid4()),
            "amount": amount_float,
            "currency": (currency or "USD").upper(),
            "merchant": merchant.strip(),
            "description": description.strip(),
            "reasoning": reasoning.strip(),
            "source_context": self.last_browsed_text[:40000] if self.last_browsed_text else None,
        }

        intents_url = f"{self.firewall_base_url}/intents"
        headers = {
            "X-Agent-Key": self.agent_key,
            "Content-Type": "application/json",
        }

        try:
            # Post intent with retry on 429 and generous 90s timeout (risk judge + canary inspection latency)
            max_intent_retries = 3
            data = {}
            status_code = 500
            for intent_attempt in range(max_intent_retries):
                try:
                    async with httpx.AsyncClient(timeout=90.0) as client:
                        res = await client.post(intents_url, json=payload, headers=headers)
                        status_code = res.status_code
                        if status_code == 429:
                            retry_after = res.headers.get("Retry-After")
                            wait_sec = float(retry_after) if retry_after and retry_after.isdigit() else (2 ** intent_attempt) * 2.0
                            logger.warning("Firewall returned 429 on /intents; backing off for %.1fs", wait_sec)
                            await asyncio.sleep(wait_sec)
                            continue
                        try:
                            data = res.json()
                        except Exception:
                            data = {"raw_response": res.text}
                        break
                except Exception as e:
                    logger.warning("Intent submit attempt %d failed: %s", intent_attempt + 1, e)
                    if intent_attempt == max_intent_retries - 1:
                        raise
    
                self.last_payment_decision = data
                self.submitted_intents.append({
                    "request": payload,
                    "response": data,
                    "status_code": status_code,
                })
    
                decision = data.get("decision", "unknown")
                if decision == "approved":
                    return {
                        "decision": "approved",
                        "status": data.get("status", "executed"),
                        "intent_id": data.get("intent_id"),
                        "dry_run": data.get("dry_run", False),
                        "message": "Payment intent was APPROVED and successfully executed.",
                    }
                elif decision == "denied":
                    return {
                        "decision": "denied",
                        "status": "denied",
                        "intent_id": data.get("intent_id"),
                        "reasons": data.get("reasons", []),
                        "message": "Payment intent was DENIED by firewall security policy.",
                    }
                elif decision == "escalated":
                    return {
                        "decision": "escalated",
                        "status": "awaiting human approval",
                        "intent_id": data.get("intent_id"),
                        "reasons": data.get("reasons", []),
                        "message": "Payment intent exceeded threshold and is awaiting human approval.",
                    }
                else:
                    return {
                        "decision": decision,
                        "status_code": status_code,
                        "response": data,
                    }
    
        except Exception as exc:
            logger.warning("submit_payment_intent failed: %s", exc)
            return {"decision": "error", "message": f"Failed to submit payment intent: {str(exc)}"}
