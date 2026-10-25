# Agent Payment Firewall

A real-time security proxy and policy firewall that intercepts, inspects, and executes autonomous AI agent payment requests. It provides deterministic policy checks (budget limits, per-transaction caps, merchant allowlists), anomaly detection, cryptographically chained audit logging, and secure PayPal sandbox payout execution.

## System Architecture

- **Backend API**: FastAPI (Python 3.11+ async) serving REST endpoints for mandate governance, payment intent ingestion, policy evaluation, and payout triggers.
- **Data Persistence**: PostgreSQL (async via SQLAlchemy + asyncpg) for transactional data (Mandates, PaymentIntents, AuditLogs).
- **Cache & Rate Limiting**: Redis for idempotency locking and state caching.
- **PayPal Integration**: Sandbox OAuth authentication (in-memory caching) and batch payouts execution (`/v1/payments/payouts`).
- **Dashboard**: Next.js + TypeScript interface (placeholder in `/dashboard`).
- **Demo**: Scenarios and simulations (placeholder in `/demo`).

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development and testing)

### 1. Environment Setup

Copy `.env.example` to `.env` (do not commit `.env` with actual secrets):
```bash
cp .env.example .env
```

Configure your sandbox PayPal credentials in `.env`:
```ini
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret
PAYPAL_MODE=sandbox
PAYPAL_TEST_RECEIVER_EMAIL=your-sandbox-receiver@example.com
```

### 2. Running with Docker Compose

To start the API, PostgreSQL database, and Redis cache:
```bash
docker compose up --build -d
```

Verify the service is healthy:
```bash
curl http://localhost:8000/health
# Response: {"status":"OK"}
```

To stop the services:
```bash
docker compose down
```

> [!IMPORTANT]
> **Database Reset on Model Changes:** Database tables are initialized using SQLAlchemy `create_all`, which does not automatically alter existing table schemas. After schema or model changes during development, reset the database and persistent volumes using:
> ```bash
> docker compose down -v
> docker compose up --build -d
> ```

### 3. Local Development & Running Pytest

Install Python dependencies:
```bash
pip install -r backend/requirements.txt
```

Run tests from the project root:
```bash
pytest
```

Or run directly with coverage:
```bash
pytest -v
```

### 4. PayPal Webhook Configuration

The API provides a verified webhook receiver endpoint at `POST /webhooks/paypal` with cryptographic signature verification and idempotency deduplication.

#### Local Tunneling with ngrok
Because PayPal requires a public HTTPS URL to deliver webhook notifications, use ngrok (or Cloudflare Tunnels) during local development:

```bash
ngrok http 8000
```
Copy the generated HTTPS forwarding URL (e.g., `https://abc1234.ngrok-free.app`).

#### Register Webhook in PayPal Dashboard
1. Log into the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/).
2. Navigate to **Apps & Credentials** and select your Sandbox App.
3. Under **Webhooks**, click **Add Webhook**.
4. Set the **Webhook URL** to:
   ```
   https://<your-ngrok-url>.ngrok-free.app/webhooks/paypal
   ```
5. Select the following Payout event types:
   - `PAYMENT.PAYOUTS-ITEM.SUCCEEDED`
   - `PAYMENT.PAYOUTS-ITEM.FAILED`
   - `PAYMENT.PAYOUTS-ITEM.BLOCKED`
   - `PAYMENT.PAYOUTS-ITEM.DENIED`
   - `PAYMENT.PAYOUTS-ITEM.RETURNED`
   - `PAYMENT.PAYOUTSBATCH.SUCCESS`
   - `PAYMENT.PAYOUTSBATCH.DENIED`
6. Save the webhook and copy the generated **Webhook ID**.
7. Add the Webhook ID to your `.env` file:
   ```ini
   PAYPAL_WEBHOOK_ID=your_paypal_webhook_id_here
   ```

> [!NOTE]
> **Render Free Tier Sleep Behavior:** Render's free tier web services spin down after 15 minutes of inactivity. Incoming PayPal webhook calls to a sleeping instance may time out (HTTP 504) while waking up. For reliable webhook delivery in production, use a persistent instance or keep the instance awake.

## API Reference

All endpoints require authentication. Operators use `Authorization: Bearer <OPERATOR_TOKEN>`. Agents use `X-Agent-Key: <key>`.

### Health

```bash
curl http://localhost:8000/health
# {"status":"OK"}
```

### Mandates (Operator-only)

```bash
# Create a mandate
curl -X POST http://localhost:8000/mandates \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mandate_id": "mandate-001",
    "agent_id": "my-agent",
    "budget_total": "100.00",
    "per_transaction_cap": "50.00",
    "escalation_threshold": "20.00",
    "period": "lifetime",
    "allowed_currencies": ["USD"],
    "allowlist_merchants": ["vendor@paypal.com"]
  }'

# List all mandates
curl http://localhost:8000/mandates \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Get a specific mandate (includes remaining/reserved/spent)
curl http://localhost:8000/mandates/mandate-001 \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Freeze / Unfreeze / Revoke
curl -X POST http://localhost:8000/mandates/mandate-001/freeze \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
curl -X POST http://localhost:8000/mandates/mandate-001/unfreeze \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
curl -X POST http://localhost:8000/mandates/mandate-001/revoke \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```

### Payment Intents

```bash
# Submit a payment intent (Agent-authenticated)
# Returns: decision = approved | escalated | denied
curl -X POST http://localhost:8000/intents \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "txn-unique-001",
    "mandate_id": "mandate-001",
    "amount": "5.00",
    "currency": "USD",
    "merchant": "vendor@paypal.com",
    "description": "SaaS subscription renewal",
    "reasoning": "Monthly billing cycle"
  }'

# List all intents (Operator-only)
curl http://localhost:8000/intents \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Get a specific intent (Operator-only)
curl http://localhost:8000/intents/<intent-id> \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Approve an escalated intent (executes the PayPal payout)
curl -X POST http://localhost:8000/intents/<intent-id>/approve \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Reject an escalated intent (releases budget reservation)
curl -X POST http://localhost:8000/intents/<intent-id>/reject \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Amount exceeds policy for this week"}'
```

### Audit Log (Operator-only)

```bash
# List audit log entries (paginated)
curl "http://localhost:8000/audit?limit=50&offset=0" \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Verify cryptographic chain integrity
# Returns: {"valid": true, "checked": <n>, "first_broken_index": null}
curl http://localhost:8000/audit/verify \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```

### Example: Full Intent Flow

```bash
# 1. Create mandate ($100 budget, $50 cap, $20 escalation threshold)
curl -X POST http://localhost:8000/mandates \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mandate_id":"m1","agent_id":"bot","budget_total":"100.00","per_transaction_cap":"50.00","escalation_threshold":"20.00","period":"lifetime","allowed_currencies":["USD"],"allowlist_merchants":["vendor@paypal.com"]}'

# 2. Submit a $5 intent (auto-approved)
curl -X POST http://localhost:8000/intents \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"k1","mandate_id":"m1","amount":"5.00","currency":"USD","merchant":"vendor@paypal.com"}'

# 3. Submit a $25 intent (escalated — above $20 threshold)
curl -X POST http://localhost:8000/intents \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"k2","mandate_id":"m1","amount":"25.00","currency":"USD","merchant":"vendor@paypal.com"}'

# 4. Operator approves the escalated intent
curl -X POST http://localhost:8000/intents/<escalated-intent-id>/approve \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# 5. Submit a $99 intent (denied — exceeds $50 cap)
curl -X POST http://localhost:8000/intents \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"k3","mandate_id":"m1","amount":"99.00","currency":"USD","merchant":"vendor@paypal.com"}'

# 6. Verify audit chain is intact
curl http://localhost:8000/audit/verify \
  -H "Authorization: Bearer $OPERATOR_TOKEN"
```

### Risk Configuration & Admin (Operator-only)

Inspect or toggle the Canary and Judge layers at runtime for live demos:

```bash
# Get current runtime status
curl http://localhost:8000/admin/risk-config \
  -H "Authorization: Bearer $OPERATOR_TOKEN"

# Toggle layers (all updates are recorded to the immutable audit log)
curl -X POST http://localhost:8000/admin/risk-config \
  -H "Authorization: Bearer $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"canary_enabled": true, "judge_enabled": true}'
```

## AI Risk Layer: Canary, Judge & Circuit Breaker

The firewall introduces a multi-tier defense against malicious agent prompt injection and goal drift:

1. **Honeypot Canary Scanner (`app/risk/canary.py`)**:
   - Inspects `source_context` across 3500-char overlapping segments.
   - Wraps content in `<untrusted_content>` tags and prompts an isolated LLM with a deliberately permissive system prompt.
   - Exposes fake dummy tools (`execute_command`, `send_payment`, `send_email`, `read_database`, `transfer_funds`).
   - If an injection in the text triggers any honeypot tool call, the canary trips immediately.
   - Any LLM timeout/error or input $>20000$ characters **fails closed**.
   - Tripping the canary **immediately freezes the mandate** via the Circuit Breaker and releases the budget reservation.

2. **AI Payment Judge (`app/risk/judge.py`)**:
   - Examines mandate scope, intent details, reasoning, and untrusted context to detect goal drift, coercion language, or merchant mismatches.
   - Uses strict Pydantic JSON schema evaluation.
   - Deterministic verdict mapping:
     - `safe=True` and `confidence >= 0.8` $\to$ `allow`
     - `safe=True` and `confidence < 0.8` $\to$ `escalate`
     - `safe=False` $\to$ `deny`
     - Timeouts / errors $\to$ fallback to `JUDGE_FAIL_MODE` (`escalate` or `deny`).
   - A high-confidence injection (`injection_suspected=True`, `confidence >= 0.9`) also trips the Circuit Breaker.

3. **Automated Circuit Breaker (`app/services/circuit_breaker.py`)**:
   - Freezes compromised mandates in real-time (`status = frozen`).
   - Dispatches a `mandate_frozen` alert on Redis Pub/Sub channel `apf:events`.
   - Appends an audit event to the cryptographic chain.
   - Prevents all subsequent agent actions under that mandate until an operator unfreezes it.

### AI Risk Layer Environment Variables

```ini
LLM_BASE_URL=https://api.openai.com/v1      # OpenAI, Groq, OpenRouter, or Gemini compatible endpoint
LLM_API_KEY=your_llm_api_key_here          # API key for the LLM provider
CANARY_MODEL=gpt-4o-mini                    # Model used for honeypot tool evaluation
JUDGE_MODEL=gpt-4o-mini                     # Model used for contextual risk judging
LLM_TIMEOUT_SECONDS=15                      # Network timeout for LLM queries
JUDGE_FAIL_MODE=escalate                    # Fallback on LLM judge failure (escalate | deny)
CANARY_ENABLED=true                         # Initial state of canary scanner
JUDGE_ENABLED=true                          # Initial state of judge
LLM_CACHE_ENABLED=true                      # In-memory TTL cache for prompt responses
LLM_FALLBACK_BASE_URL=                      # Optional secondary provider endpoint
LLM_FALLBACK_API_KEY=                       # Optional secondary provider API key
LLM_FALLBACK_MODEL=                         # Optional secondary provider model
```

## Detection Quality & Calibration

Detection quality for the Honeypot Canary and AI Risk Judge is evaluated against a calibration suite covering benign product listings, invoices, multi-lingual contexts, and diverse prompt injection techniques (blunt override, hidden DOM elements, fake system banners, review-embedded traps, base64 payloads, spaced tokens, and multi-paragraph exploits).

Detailed empirical measurements and metrics breakdown are tracked in:
👉 [**Risk Layer Calibration Report (`results/CALIBRATION.md`)**](results/CALIBRATION.md)

> [!NOTE]
> LLM-based prompt injection detection is inherently probabilistic. Model generation behavior varies based on model family, temperature, quantization, and prompt phrasing. Our calibration dataset provides a standardized benchmark, but production deployments should continuously monitor audit logs and tune risk policies accordingly.

## Repository Structure

```
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules
├── docker-compose.yml        # Docker compose services (api, postgres, redis)
├── LICENSE                   # MIT License
├── pytest.ini                # Pytest configuration
├── README.md                 # Project documentation
├── backend/
│   ├── Dockerfile            # Container definition for FastAPI backend
│   ├── pytest.ini            # Pytest configuration for backend folder
│   ├── requirements.txt      # Python dependencies
│   ├── app/
│   │   ├── api/              # API endpoints and routers
│   │   ├── core/             # Configuration and database connection
│   │   ├── models/           # SQLAlchemy models (Mandate, PaymentIntent, AuditLog)
│   │   ├── paypal/           # PayPal OAuth client and Payouts integration
│   │   ├── risk/             # Risk scoring and evaluation engines
│   │   ├── services/         # Application business services
│   │   └── main.py           # FastAPI entry point
│   ├── scripts/              # Operational scripts (e.g. test_payout.py)
│   └── tests/                # Backend test package
├── dashboard/                # Next.js frontend dashboard placeholder
├── demo/                     # Scenario walkthroughs and demo scripts
└── tests/                    # Project test suite
```

## License

MIT License - Copyright (c) 2026 SHREESHANTH99
