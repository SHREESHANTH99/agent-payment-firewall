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
        "AGENT_TOKEN": "your-agent-bearer-token"
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
  agent_id: string,          // e.g. "procurement-agent-1"
  amount_usd: number,        // e.g. 25.50
  merchant: string,          // e.g. "seller@office-supplies.com"
  description: string,       // e.g. "Reorder 5x ink cartridges"
  reasoning: string,         // e.g. "User asked to restock printer supplies"
  user_task: string,         // e.g. "Buy ink cartridges for the team under $50"
  source_context: string,    // Untrusted page text or catalog DOM read by the agent
  mandate_id?: string,       // Optional: specific policy mandate ID
  dry_run?: boolean          // Default: true (safe test evaluation)
})
```

### Example Prompt in Claude Desktop / Cursor:
> *"I need you to buy 2 packs of paper from seller@office-supplies.com for $30.00. Submit the payment request through the Gatekeeper firewall tool."*

**Agent execution**:
1. Agent calls `submit_payment_intent(...)`.
2. Gatekeeper evaluates the intent against:
   - Idempotency & policy rules
   - Mandate bounds ($50 cap, allowlist)
   - Canary honeypot scanner
   - LLM risk judge
3. Agent receives the response:
   ```json
   {
     "status": "success",
     "decision": "approved",
     "intent_id": "int-98124a",
     "amount_usd": 30.0,
     "merchant": "seller@office-supplies.com"
   }
   ```
4. If an adversarial injection was detected on the seller's page, the firewall halts payment with `"decision": "denied"` and returns the security flag to the agent without money moving.
