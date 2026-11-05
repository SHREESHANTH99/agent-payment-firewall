# Deploying Agent Payment Firewall to Render

This guide provides step-by-step instructions for deploying the Agent Payment Firewall to Render using the Infrastructure-as-Code Blueprint (`render.yaml`).

---

## 1. Blueprint Architecture

The Render Blueprint provisions 4 resources:
1. **`payment-firewall-api`**: FastAPI backend web service (Docker runtime, `/ready` health check).
2. **`payment-firewall-dashboard`**: Next.js 14 console & landing page web service (Docker runtime).
3. **`payment-firewall-db`**: PostgreSQL database (source of truth, hash-chained audit ledger).
4. **`payment-firewall-redis`**: Key-value instance (atomic reservation counter, pub/sub, sliding-window rate limiting).

---

## 2. Deployment Steps

### Step 1: Connect Repository to Render
1. In the [Render Dashboard](https://dashboard.render.com/), click **New +** $\rightarrow$ **Blueprint**.
2. Select the `agent-payment-firewall` GitHub repository.
3. Render will parse `render.yaml` and configure the 4 components.

### Step 2: Configure Environment Variables (Secrets)
The blueprint marks production secrets with `sync: false`. You will be prompted in the Render UI to fill in the following:

- `OPERATOR_TOKEN`: A secure, secret token at least 24 characters long used for operator authorization.
- `AGENT_API_KEYS`: JSON mapping of agent keys to agent IDs, e.g.:
  ```json
  {"secret-key-agent-alpha": "agent-alpha-001"}
  ```
- `PAYPAL_CLIENT_ID`: Your PayPal developer sandbox app client ID.
- `PAYPAL_CLIENT_SECRET`: Your PayPal developer sandbox client secret.
- `PAYPAL_WEBHOOK_ID`: The webhook ID obtained in Step 3 below.
- `LLM_API_KEY`: OpenAI or OpenAI-compatible API key for canary/judge inspection.

### Step 3: Register PayPal Webhook
1. Log in to the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/).
2. Under your Sandbox App, click **Add Webhook**.
3. Set the Webhook URL to:
   ```
   https://<your-render-api-url>/webhooks/paypal
   ```
4. Subscribe to the following events:
   - `PAYMENT.PAYOUTSBATCH.SUCCESS`
   - `PAYMENT.PAYOUTSBATCH.DENIED`
   - `PAYMENT.PAYOUTS-ITEM.SUCCEEDED`
   - `PAYMENT.PAYOUTS-ITEM.FAILED`
   - `PAYMENT.PAYOUTS-ITEM.BLOCKED`
   - `PAYMENT.PAYOUTS-ITEM.CANCELED`
5. Copy the generated **Webhook ID** and paste it into `PAYPAL_WEBHOOK_ID` in your Render API service environment variables.

---

## 3. Free-Tier Operational Caveats

Render's free tier is fully functional for demonstration and evaluation, but has three operational characteristics:

1. **Inactivity Sleep**: Free web services sleep after 15 minutes of inactivity. When a new agent intent or user arrives, a cold start delay of 30–50 seconds occurs.
2. **Cold Redis Rebuild**: Render's free Key Value instance is ephemeral. When restarting or following an eviction, the firewall handles this gracefully:
   - During the startup lifespan, `budget_service.rebuild_from_db(session)` runs automatically before traffic is served.
   - Active mandate spend counters and reservations are rebuilt from PostgreSQL (the source of truth).
3. **Free PostgreSQL Expiry**: Free Render PostgreSQL databases expire after 30 days. For prolonged operation, back up data or upgrade the database plan.

### Optional Keep-Alive
To prevent the API and Dashboard from sleeping during hackathon demos, register a free external uptime monitor (such as [UptimeRobot](https://uptimerobot.com/) or [BetterStack](https://betterstack.com/)) targeting the liveness endpoint:
```
GET https://<your-render-api-url>/health
```
This endpoint executes zero database queries, consumes minimal resources, and keeps the service warm.
