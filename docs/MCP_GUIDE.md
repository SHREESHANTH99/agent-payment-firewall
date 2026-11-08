# Connecting to the Gatekeeper MCP Server

The **Agent Payment Firewall MCP Server** exposes the `submit_payment_intent` tool via the Model Context Protocol (MCP). Any MCP-compatible AI agent (Claude Desktop, Cursor, Gemini, LangChain, etc.) can discover and use Gatekeeper to verify payments before settlement.

---

## 1. Quick Local Start (stdio transport)

From the project root directory:

```bash
cd backend
python -m app.mcp_server
```

---

## 2. Connect to Claude Desktop

Add Gatekeeper to your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "gatekeeper-firewall": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "C:/path/to/agent-payment-firewall/backend",
      "env": {
        "FIREWALL_BASE_URL": "http://localhost:8000",
        "AGENT_MANDATE_ID": "mnd-prod-001",
        "MCP_AGENT_API_KEY": "your-agent-api-key",
        "MCP_DRY_RUN": "true"
      }
    }
  }
}
```

> **Deployed / Remote Mode**: If connecting to your live Render backend, simply set `"FIREWALL_BASE_URL": "https://payment-firewall-dashboard.onrender.com"` (or your backend URL).

---

## 3. Connect to Cursor / VS Code MCP Extensions

In Cursor's MCP Settings (`Settings -> Features -> MCP`):

- **Name**: `Gatekeeper Payment Firewall`
- **Type**: `command`
- **Command**: `python -m app.mcp_server`
- **Working Directory**: `/path/to/agent-payment-firewall/backend`

---

## 4. How the AI Agent Uses the Tool

Once connected, your agent will automatically see the tool:

### Tool Signature
```typescript
submit_payment_intent({
  amount_usd: number,        // e.g. 25.50
  merchant: string,          // e.g. "seller@office-supplies.com"
  description: string,       // e.g. "Reorder 5x ink cartridges"
  reasoning: string,         // e.g. "User asked to restock printer supplies" (max 4,000 chars)
  user_task: string,         // e.g. "Buy ink cartridges for the team under $50" (max 2,000 chars)
  source_context: string,    // Untrusted page text or catalog DOM read by the agent (max 50,000 chars)
  mandate_id?: string        // Optional: specific policy mandate ID (defaults to AGENT_MANDATE_ID)
})
```
> **Security Notice**:
> - `agent_id` is automatically authenticated and derived from `MCP_AGENT_API_KEY`; callers cannot spoof caller identity.
> - `dry_run` is controlled strictly by server configuration (`MCP_DRY_RUN`); callers cannot disable test isolation.

### Example Prompt in Claude Desktop / Cursor:
> *"I need you to buy 2 packs of paper from seller@office-supplies.com for $30.00. Submit the payment request through the Gatekeeper firewall tool."*

**Agent execution**:
1. Agent calls `submit_payment_intent(...)`.
2. Gatekeeper evaluates the intent against:
   - Idempotency & policy rules
   - Mandate bounds ($50 cap, allowlist)
   - Canary honeypot scanner
   - LLM risk judge
3. Agent receives the sanitized response:
   ```json
   {
     "intent_id": "int-98124a",
     "decision": "approved",
     "status": "approved",
     "reason": "Payment intent processed",
     "escalated": false
   }
   ```
4. If an adversarial injection was detected on the seller's page, the firewall halts payment with `"decision": "denied"`, `"reason": "Payment intent denied: CANARY_TRIPPED"`, without leaking honeypot canaries or risk judge chain-of-thought to the compromised agent.
