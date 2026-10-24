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
