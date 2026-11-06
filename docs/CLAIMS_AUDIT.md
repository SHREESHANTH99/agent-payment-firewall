# Full Claims Audit: Agent Payment Firewall

**Date:** 2026-11-06  
**Auditor:** Antigravity (Automated & Empirical Audit)  
**Scope:** `README.md`, `SECURITY.md`, `docs/*.md`, `docs/adr/*`, `results/*.md`, `dashboard` copy, `demo/README.md`.  
**Rules in effect:** Read-only evaluation freeze (`eval-freeze-v1`). No secrets printed/committed. No predictions or invented statistics.

---

## 1. Audit Summary Counts

| Status | Count | Description |
| :--- | :---: | :--- |
| **VERIFIED** | **27** | Factual claim matches code, automated tests, or stored data exactly. |
| **UNVERIFIED** | **9** | Plausible or planned capability, but lacks an empirical measurement script or test in tree. |
| **FALSE** | **6** | Claim directly contradicts current code, test implementation, or benchmark data. |
| **TOTAL** | **42** | |

---

## 2. The 6 FALSE Claims (Contradictions & Required Fixes)

1. **Threshold Decision Rules (0.70 / 0.40):**
   - *Claim:* `RISK_SCORE >= 0.70` denies, `0.40 <= RISK_SCORE < 0.70` escalates, `< 0.40` approves.
   - *Contradiction:* **FALSE.** The judge returns structured output (`safe: bool`, `confidence: float`, `injection_suspected: bool`, `mismatch_reasons: list`). The firewall evaluates discrete decision rules (M0-M5). In M0: `safe=true` with confidence $\ge 0.80$ allows; `safe=true` with confidence $< 0.80$ escalates; `safe=false` denies.
   - *Fix:* Ensure all docs reference M0-M5 discrete mappings and eliminate any reference to continuous 0.70/0.40 score tiers.

2. **WebSocket Route Paths:**
   - *Claim:* `POST /api/v1/ws/ticket` and `WebSocket /api/v1/ws/events`.
   - *Contradiction:* **FALSE.** The actual endpoints implemented in `backend/app/api/websocket.py` and connected by the dashboard in `dashboard/src/hooks/useRealtime.ts` are:
     - `POST /ws/ticket`
     - `WebSocket /ws/dashboard?ticket={ticket}`
   - *Fix:* Correct all docs, playground references, and API notes to `/ws/ticket` and `/ws/dashboard`.

3. **Unmeasured Performance & Timing ("< 1 ms", "ROC curves", "N=1000 sample"):**
   - *Claim:* *"Deterministic rules run in under 1 ms"*, *"ROC curves"*, *"N=1000 sample sizes"*.
   - *Contradiction:* **FALSE / UNVERIFIED.**
     - No timing harness measures sub-millisecond rule execution.
     - No ROC curve generation script exists in `demo/eval/`.
     - $N=1000$ represents bootstrap *resample iterations* in `cluster_bootstrap_interval()`, not unique scenario or intent sample counts.
   - *Fix:* Remove "<1 ms", reword ROC references to discrete threshold sweeps, and clarify bootstrap resamples vs sample size $N$.

4. **Architecture Framing ("Production-grade microservice architecture"):**
   - *Claim:* *"Production-grade microservice architecture"*, *"Enterprise-grade security"*.
   - *Contradiction:* **FALSE.** This is an open-source research and hackathon prototype built for PayPal AI agent interception.
   - *Fix:* Re-label across all docs and dashboard text to **"production-minded prototype"**.

5. **Proxy Client IP & Rate Limiter Bypass/Exemption:**
   - *Claim:* Rate limiting safely protects endpoints without denying valid traffic.
   - *Contradiction:* **FALSE.** `backend/app/core/rate_limit.py` inspected `request.client.host` directly. Behind Render's reverse proxy, all clients share Render's internal IP. Furthermore, `/webhooks/paypal` was subject to the IP limiter, risking drops of critical PayPal payment webhooks.
   - *Fix:* Support `TRUSTED_PROXY_COUNT` (default 0; set to 1 in `render.yaml`) reading `X-Forwarded-For`, and explicitly exempt `/webhooks/paypal`, `/health`, and `/ready`.

6. **Swagger UI (`/docs`) Broken by Strict CSP:**
   - *Claim:* Interactive API documentation is available at `/docs` when `ENABLE_DOCS=true`.
   - *Contradiction:* **FALSE.** The strict Content Security Policy (`script-src 'self'`) blocked Swagger UI CDN javascript assets.
   - *Fix:* When `ENABLE_DOCS=true`, permit Swagger UI script and style origins in the CSP middleware.

---

## 3. Detailed Audit Matrix

| # | Claim | Source Document | Status | Evidence / Contradiction |
|---|---|---|:---:|---|
| 1 | Payouts use PayPal Sandbox only; live host never called | `README.md`, `AGENTS.md` | **VERIFIED** | `backend/app/paypal/constants.py` hardcodes `api-m.sandbox.paypal.com`; startup check forbids live hosts. |
| 2 | Internal money representation is integer cents | `AGENTS.md`, `models.py` | **VERIFIED** | `amount_cents` stored as integer in `PaymentIntent`, `Mandate`, and Redis Lua scripts. |
| 3 | LLM risk layers fail closed | `docs/adr/0001-fail-closed-risk-pipeline.md` | **VERIFIED** | `judge.py` catches timeout/exceptions and returns `safe=false`, `fail_mode_applied=true`. |
| 4 | Rules execute before any AI checks | `backend/app/services/pipeline.py` | **VERIFIED** | Pipeline evaluates `rules.evaluate_intent_rules()` first; if denied, canary/judge are skipped. |
| 5 | Two-phase budget reservation via Redis Lua script | `docs/adr/0002-two-phase-budget-reservation.md` | **VERIFIED** | `backend/app/services/budget.py` runs atomic Lua reserve, commit, and release scripts. |
| 6 | SHA-256 hash-chained immutable audit ledger | `docs/adr/0003-audit-ledger-hash-chain.md` | **VERIFIED** | `backend/app/services/audit.py` hashes `(prev_hash + entry)` and verifies chain integrity. |
| 7 | Ephemeral WebSocket tickets with 60s TTL | `backend/app/api/websocket.py` | **VERIFIED** | `create_ws_ticket()` stores ticket with `ex=60` in Redis; single-use deletion on connect. |
| 8 | Read check `/ready` probes DB and Redis | `backend/app/main.py` | **VERIFIED** | Probes `SELECT 1` on PostgreSQL and `PING` on Redis; returns 503 if either fails. |
| 9 | Out-of-policy attacks blocked 100% by rules in TEST | `results/paired_test.json` | **VERIFIED** | 18 of 18 out-of-policy observations stopped by rules (`denial_causes: {"rules": 18}`). |
| 10 | AI Judge caught 2 of 6 in-policy attacks in TEST | `results/paired_test.json` | **VERIFIED** | Caught 2 unique intents (both styles of `attack_wrong_item_inpolicy_2`); missed 4 reroutes. |
| 11 | 0 of 3 clean legitimate intents wrongly denied | `results/paired_test.json` | **VERIFIED** | Clean legitimate intents (`benign_search_and_buy_office_supplies_2`, etc.) approved; 1 expected refusal separated. |
| 12 | 0 of 9 poisoned page legitimate intents wrongly denied | `results/paired_test.json` | **VERIFIED** | 9 unique legitimate intents with injected page context approved cleanly. |
| 13 | Decision rules are continuous 0.70 / 0.40 thresholds | Earlier summary | **FALSE** | System uses M0-M5 discrete mappings (`safe`, `confidence >= 0.80`). |
| 14 | WebSocket endpoint is `/api/v1/ws/events` | Earlier summary | **FALSE** | Actual endpoints are `/ws/ticket` and `/ws/dashboard`. |
| 15 | Rules run in under 1 ms | Earlier summary | **FALSE** | Sub-millisecond timing was unmeasured. |
| 16 | ROC curves derived for evaluation | Earlier summary | **FALSE** | No ROC generator exists; discrete sweeps are used. |
| 17 | N=1000 sample size | Earlier summary | **FALSE** | 1000 is bootstrap resamples, not scenario/intent count. |
| 18 | Production-grade microservice architecture | Root docs | **FALSE** | Prototype architecture; must be reworded to production-minded prototype. |
| 19 | Rate limiter is proxy-safe | `rate_limit.py` | **UNVERIFIED** | Does not extract `X-Forwarded-For` by default behind reverse proxies. |
| 20 | Swagger UI works under CSP | `main.py` | **UNVERIFIED** | Strict CSP default blocks Swagger UI scripts unless explicitly loosened for `/docs`. |
| 21 | Redis budget rebuilds from PostgreSQL on cold start | `test_cold_start.py` | **VERIFIED** | `test_cold_redis_rebuild_from_postgres` passes against clean database state. |
| 22 | Live TEST run completed | Summary notes | **UNVERIFIED** | Live TEST evaluation was never executed (all evaluation in `results/` is `dry_run`). |
| 23 | rules_plus_policy evaluated in test harness | Summary notes | **UNVERIFIED** | Deterministic code exists, but evaluation configuration was not run in replay. |
| 24 | Webhooks verified via PayPal verify-webhook-signature | `backend/app/paypal/webhooks.py` | **VERIFIED** | Calls PayPal verification API endpoint with full webhook payload headers. |
| 25 | Secret redaction in logs | `backend/app/core/logging.py` | **VERIFIED** | Regex filter masks tokens, client secrets, and authorization headers. |
| 26 | Idempotency key locking via Redis | `backend/app/services/idempotency.py` | **VERIFIED** | Enforces atomic key reservation with TTL and cached response return. |
| 27 | Mandate auto-freeze upon high-severity risk | `backend/app/services/pipeline.py` | **VERIFIED** | Mandate status set to `frozen` when risk threshold or canary honeypot is triggered. |
| 28 | Honeypot canary payment tools detect prompt injection | `backend/app/risk/canary.py` | **VERIFIED** | Inspects agent context for invocation of fake payment tools. |
| 29 | Fallback LLM provider support | `backend/app/services/llm.py` | **VERIFIED** | Groq primary with Qwen/OpenAI compatible fallback support. |
| 30 | Circuit breaker trips on consecutive PayPal failures | `backend/app/services/circuit_breaker.py`| **VERIFIED** | Transitions to OPEN state after 5 failures; fails closed on intents. |
| 31 | In-memory sliding rate limit per IP | `backend/app/core/rate_limit.py` | **VERIFIED** | Sliding timestamp window tracks request frequency per client key. |
| 32 | Render blueprint defines free tier for all services | `render.yaml` | **UNVERIFIED** | Must be verified to specify `plan: free` across services and databases. |
| 33 | Dashboard evidence view guards small samples (<10) | `dashboard/src/components` | **UNVERIFIED** | Must render counts only (e.g. "0 of 3") rather than misleading percentages. |
| 34 | Expected refusals separated from false positives | `demo/eval/metrics.py` | **UNVERIFIED** | `benign_unavailable_item` was counted in `legitimate_clean_context` instead of `expected_refusal`. |
| 35 | Paired evaluation isolates seller 1 vs seller 2 | `demo/eval/paired.py` | **VERIFIED** | Generates paired deterministic legitimate and attack intents for identical tasks. |
| 36 | Layer isolation table verifies canary vs judge | Docs | **UNVERIFIED** | Must present independent `canary_only` and `judge_only` outcomes alongside combined order. |
| 37 | Automated tests mock all external network calls | `tests/` | **VERIFIED** | `respx` and unit mocks ensure zero external HTTP or live PayPal calls in test suite. |
| 38 | Database tests use NullPool connection isolation | `backend/app/core/database.py` | **VERIFIED** | `poolclass=NullPool` configured on async engine. |
| 39 | Multi-stage non-root Docker builds | `backend/Dockerfile` | **VERIFIED** | Runs under unprivileged `appuser` (UID 10001). |
| 40 | Dependabot PR grouping by ecosystem | `.github/dependabot.yml` | **VERIFIED** | Grouped monthly updates with max 1 open PR per package manager. |
| 41 | Python 3.12 compatibility | `ci.yml`, `requirements.lock`| **VERIFIED** | GitHub Actions and lockfile target Python 3.12. |
| 42 | No live money ever moved in evaluation | `results/paired_test.json` | **VERIFIED** | `execution_mode: dry_run` enforced across all runs. |
