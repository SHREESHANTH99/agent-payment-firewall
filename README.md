# Agent Payment Firewall (Gatekeeper)

A real-time security proxy and settlement firewall that intercepts, inspects, and executes autonomous AI agent payment requests before money moves.

It provides deterministic policy enforcement (budget limits, per-transaction caps, merchant allowlists), atomic Redis budget reservation, honeypot canary token traps, LLM-based adversarial risk adjudication, an automated circuit breaker, a SHA-256 hash-chained immutable audit ledger in PostgreSQL, and secure PayPal sandbox payout execution.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Autonomous AI Agent       |
                      +--------------+--------------+
                                     |
                                     |  X-Agent-Key: Bearer <key>
                                     v
                      +-----------------------------+
                      |  Agent Payment Firewall API |
                      +--------------+--------------+
                                     |
             +-----------------------+-----------------------+
             |                       |                       |
             v                       v                       v
     [ 1. Idempotency ]      [ 2. Mandate Check ]    [ 3. Atomic Budget ]
    Atomic key locking in    Agent ID, allowlist,    Redis reserve/commit
            Redis              lifetime/period caps       with TTL release
             |                       |                       |
             +-----------------------+-----------------------+
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
    [ 4. Honeypot Canary ]                          [ 5. Risk Judge ]
   Overlapping context scan                        Adversarial prompt
    detects honeypot tool                          injection & semantic
      calls (fail-closed)                             drift analysis
             |                                               |
             +-----------------------+-----------------------+
                                     |
                                     v
                           [ 6. Decision Engine ]
                                     |
                 +-------------------+-------------------+
                 |                                       |
           (Approved)                               (Escalated)
                 |                                       |
                 v                                       v
     [ PayPal Sandbox Payout ]                 [ Human Review Queue ]
     OAuth token batch payout                WebSocket streaming to Console
     + Webhook signature check               Operator Approve / Reject
                 |                                       |
                 +-------------------+-------------------+
                                     |
                                     v
                         [ SHA-256 Audit Chain ]
                        Postgres chained ledger
                        Genesis -> Head verification
```

### Defense-in-Depth Pipeline

1. **Idempotency Deduplication**: Atomic Redis key locking prevents replay attacks and race condition double-spending.
2. **Deterministic Mandate & Policy Rules**: Strict validation of agent ID, currency, merchant allowlists, per-transaction limits, and period budgets.
3. **Atomic Redis Budgeting**: Strict `reserve` $\to$ `commit` or `release` pattern guarantees budgets cannot be overspent across concurrent requests.
4. **Honeypot Canary Scanner**: Injects dummy tool definitions into untrusted context segments. If prompt injection induces an agent tool call, the canary trips and auto-freezes the mandate via the circuit breaker.
5. **LLM Risk Judge**: Evaluates intent reasoning, recipient, and untrusted context against adversarial manipulation and semantic drift with structured Pydantic schema validation.
6. **Automated Circuit Breaker**: Instantly freezes compromised mandates, emits real-time WebSocket alerts, and halts any further settlement until an operator reviews.
7. **Human Escalation Queue**: Transactions exceeding policy thresholds or flagged by risk layers require operator authorization.
8. **Cryptographic SHA-256 Hash Chain**: Every state change, approval, rejection, and circuit breaker trip is appended to an immutable tamper-evident audit ledger in PostgreSQL.
9. **PayPal Sandbox Settlement**: Final execution through PayPal Sandbox Payouts API (`/v1/payments/payouts`) with cryptographic webhook signature verification.

---

## Web Interface: Landing Page & Operator Console

The frontend is built with **Next.js 14**, **TypeScript**, and **Tailwind CSS**, designed using the Paper & Ink aesthetic token system (Paper `#F3F0E8`, Ink `#14130F`, Vermilion `#E5391B`, Forest `#1F7A4D`, Amber `#B7791F` with dark mode support).

### 1. Public Landing Page (`/`)
- **Sticky Navigation**: Clean section navigation with 72px scroll-spy offset, dark/light theme toggle, and a **Launch Console** dropdown (Demo mode vs. Operator Token sign-in).
- **Interactive Settlement Simulator**: Test 4 real-world attack scenarios (clean purchase, over-limit, prompt injection, in-policy redirect) with live firewall ON/OFF toggling.
- **Empirical Calibration Evidence**: Grounded accuracy charts rendered from benchmark evaluation runs (`/public/data/eval.json` and `results/CALIBRATION.md`).
- **Architecture & Attack Story**: Visual walkthrough of DOM-based prompt injection threats and how honeypot canaries neutralize them.

### 2. Operator Governance Console (`/console`)
- **Overview**: 5 live KPIs (Settled, Reserved, Remaining Budget, Pending Approvals, Frozen Mandates), 24-hour decision distribution chart, 6-stage pipeline inspection strip, and live WebSocket activity ledger.
- **Approvals (`/console/approvals`)**: Human-in-the-loop escalation cards displaying merchant, amount, reasoning, collapsible source context, and canary/judge stamps with real-time countdown expiry and one-click Approve/Reject.
- **Intents (`/console/intents`)**: AG Grid ledger with status filters and slide-over drawer displaying raw JSON risk details and audit logs.
- **Mandates (`/console/mandates`)**: Mandate management table with spent/reserved/remaining budget bars and instant Freeze, Unfreeze, and Revoke controls.
- **Audit Chain (`/console/audit`)**: Linked SHA-256 hash block visualization with an animated "Verify Chain Integrity" tool that detects broken hashes.
- **Risk Controls (`/console/controls`)**: Runtime toggles for the Canary Scanner and AI Judge with persistent security warnings when defenses are disarmed.
- **Dual Operating Modes**:
  - **Live Sandbox Mode**: Authenticates with `OPERATOR_TOKEN` and connects to the FastAPI backend and WebSocket event stream.
  - **Interactive Demo Mode (`/console?demo=1`)**: Fully offline mock provider that simulates real-time events, approvals, freeze actions, and chain verification with sample data.

---

## Getting Started

### Prerequisites
- **Docker & Docker Compose** (Docker Desktop on Windows/macOS/Linux)
- **Node.js 18+ & npm** (for dashboard development)
- **Python 3.11+** (for backend testing and scripts)

---

### Step 1: Clone and Configure Environment

```bash
git clone https://github.com/SHREESHANTH99/agent-payment-firewall.git
cd agent-payment-firewall
cp .env.example .env
```

Edit `.env` to configure your sandbox tokens and LLM credentials:

```ini
# Database & Redis
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/firewall
REDIS_URL=redis://localhost:6379/0

# Operator & Agent Authentication Keys
OPERATOR_TOKEN=ff0a74cff100d5c1ecadf26fe8d08ff1082b5aca59f47db941c5d939cdecfdb2
AGENT_API_KEYS={"1738cb5f7b39d2ae0cd4c7b4fd544901a7dc21699c6e68f6":"agent-007"}

# AI Risk Inspection Engine
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=your_gemini_or_openai_api_key
CANARY_MODEL=gemini-3.5-flash
JUDGE_MODEL=gemini-3.5-flash
CANARY_ENABLED=true
JUDGE_ENABLED=true

# PayPal Sandbox Credentials
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_MODE=sandbox
PAYPAL_TEST_RECEIVER_EMAIL=your_sandbox_buyer_email@example.com
```

---

### Step 2: Start Services via Docker

To run the complete stack (FastAPI Backend, PostgreSQL, Redis, and Next.js Dashboard):

```bash
docker compose up -d
```

Verify the backend service is healthy:
```bash
curl http://localhost:8000/health
# {"status":"OK"}
```

Access the web interfaces:
- **Landing Page**: [http://localhost:3000](http://localhost:3000)
- **Interactive Demo Console**: [http://localhost:3000/console?demo=1](http://localhost:3000/console?demo=1)
- **Operator Console Sign-In**: [http://localhost:3000/console/login](http://localhost:3000/console/login)

---

### Step 3: Running the Dashboard in Local Dev Mode

If developing or modifying the Next.js dashboard locally:

```bash
cd dashboard
npm install
npm run dev
```

Run frontend tests:
```bash
npm test
```

Build for production:
```bash
npm run build
```

---

## API Reference

All requests require either Operator authentication (`Authorization: Bearer <OPERATOR_TOKEN>`) or Agent authentication (`X-Agent-Key: <key>`).

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. Mandates (Operator Only)
```bash
# Create spending mandate
curl -X POST http://localhost:8000/mandates \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mandate_id": "mnd-prod-007",
    "agent_id": "agent-007",
    "budget_total": "1500.00",
    "per_transaction_cap": "25.00",
    "escalation_threshold": "15.00",
    "period": "monthly",
    "allowed_currencies": ["USD"],
    "allowlist_merchants": ["cloud-compute-grid.net", "developer-tools.com"]
  }'

# Freeze a mandate
curl -X POST http://localhost:8000/mandates/mnd-prod-007/freeze \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Unfreeze a mandate
curl -X POST http://localhost:8000/mandates/mnd-prod-007/unfreeze \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```

### 3. Payment Intents (Agents & Operators)
```bash
# Submit an intent as an AI agent
curl -X POST http://localhost:8000/intents \
  -H "X-Agent-Key: 1738cb5f7b39d2ae0cd4c7b4fd544901a7dc21699c6e68f6" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "unique-uuid-001",
    "mandate_id": "mnd-prod-007",
    "amount": "14.00",
    "currency": "USD",
    "merchant": "developer-tools.com",
    "description": "Monthly CI build worker renewal",
    "reasoning": "Sprint pipeline automation dependency",
    "source_context": "Task #402: provision CI runner node for release build"
  }'

# Approve an escalated intent (Operator only)
curl -X POST http://localhost:8000/intents/<intent-id>/approve \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Reject an escalated intent
curl -X POST http://localhost:8000/intents/<intent-id>/reject \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Exceeds daily provisioning budget"}'
```

### 4. Audit Chain Verification (Operator Only)
```bash
# Verify cryptographic hash chain integrity
curl http://localhost:8000/audit/verify \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
# {"valid": true, "checked": 42, "first_broken_index": null, "chain_head_hash": "..."}
```

### 5. Risk Configuration (Operator Only)
```bash
# Toggle Canary Scanner and AI Judge
curl -X POST http://localhost:8000/admin/risk-config \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"canary_enabled": true, "judge_enabled": true}'
```

---

## Testing & Quality Assurance

### Backend Unit & Integration Tests (Pytest)
```bash
pytest
```
Covers:
- Idempotency deduplication & Redis reserve/commit/release lifecycle.
- Deterministic policy enforcement (caps, allowlists, currency).
- Honeypot canary token tripping and fail-closed behaviors.
- Judge prompt formatting, schema validation, and confidence fallbacks.
- SHA-256 cryptographic hash-chain tamper detection.
- PayPal OAuth token caching and payout dispatch mock verification.

### Frontend Unit & State Tests (Vitest)
```bash
cd dashboard
npm test
```
Covers:
- Number formatting (currency compact & full notation).
- Semantic status badge mapping and verdict stamps.
- Mock API provider workflows (intent filtering, budget calculation, freeze/unfreeze).
- Cryptographic hash shortening and SHA-256 copy helpers.

---

## Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI endpoints (intents, mandates, audit, admin, webhooks, ws)
│   │   ├── core/             # Database connection, security, config settings
│   │   ├── models/           # SQLAlchemy models (Mandate, PaymentIntent, AuditLog)
│   │   ├── paypal/           # PayPal client, payout batches, webhook verification
│   │   ├── risk/             # Honeypot Canary scanner and AI Risk Judge
│   │   ├── services/         # Budget accounting, pipeline processor, circuit breaker
│   │   └── main.py           # FastAPI entry point & lifespan routines
│   ├── results/              # Calibration benchmark outputs and reports
│   └── tests/                # Pytest integration & unit test suite
├── dashboard/
│   ├── public/               # SVG illustrations, favicon, scenarios.json, calibration data
│   ├── src/
│   │   ├── app/
│   │   │   ├── console/      # Operator console routes (overview, approvals, intents, mandates, audit, controls)
│   │   │   ├── globals.css   # Paper & Ink design tokens, hairline borders, AG Grid theme
│   │   │   └── page.tsx      # Public landing page with interactive simulator
│   │   ├── components/       # UI elements (Stamps, KpiNumerals, PipelineStrip, Drawer)
│   │   ├── hooks/            # useRealtime WebSocket hook
│   │   ├── lib/              # API clients (real & mockService for demo mode)
│   │   └── types/            # TypeScript interfaces
│   └── package.json
├── docker-compose.yml        # Docker compose configuration (API, Postgres, Redis, Dashboard)
├── .env.example              # Environment variables template
└── README.md
```

---

## Security Model & Truthful Disclosure

- **Presentation Layer Integrity**: The dashboard presentation layer is decoupled from payment settlement logic. The frontend communicates with the backend exclusively via standard REST endpoints and authenticated WebSocket tickets.
- **Fail-Closed Principle**: If LLM risk inspection layers time out or encounter rate limits, transactions do not execute silently; they fail closed and escalate for human operator verification.
- **Immutable Ledger**: Every financial state transition is recorded in PostgreSQL with the SHA-256 hash of the payload linked to the previous entry (`prev_hash`). Any manual database record modification breaks the verification hash chain.

---

## License

MIT License. Copyright (c) 2026 SHREESHANTH99.
