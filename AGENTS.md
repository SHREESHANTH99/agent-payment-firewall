# Agent Payment Firewall: guide for coding agents

## What this is
Open-source payment firewall between AI agents and PayPal (SANDBOX ONLY). An agent submits a payment intent to POST /intents; the firewall decides approve / deny / escalate-to-human and pays via PayPal Payouts. Hackathon project; deadline Nov 13 2026.

## Layout
- backend/ FastAPI, async SQLAlchemy, Postgres (source of truth), Redis (budget, idempotency, pub/sub)
  - app/risk: rules.py (pure), canary.py (honeypot tools), judge.py (LLM, structured output)
  - app/services: pipeline.py, budget.py (Lua reserve/commit/release), idempotency.py, audit.py (SHA-256 hash chain), circuit_breaker.py, llm.py (OpenAI-compatible client, retries, fallback, cache)
  - app/paypal: auth, payouts, webhooks (verify via PayPal verify-webhook-signature API)
- dashboard/ Next.js + TypeScript + AG Grid (landing page, console, demo mode)
- demo/ store/ (mock store with attack variants), agent/ (LLM tool-calling agent), eval/ (harness, replay, metrics)
- results/ EVAL.md, eval.json, calibration (archive_invalid_pre_4.1/ must never be cited)

## Rules (non-negotiable)
- NEVER print, log, echo, or commit secrets (.env, API keys, tokens). Do not read .env contents into output. Reference variable names only.
- Sandbox only: PayPal base URL is the sandbox host. Never add live endpoints.
- Money is integer cents internally.
- LLM layers fail closed. Rules run before AI checks. Postgres is the source of truth; Redis is rebuildable.
- Report only MEASURED values in docs and results. No predicted outcomes, no invented statistics, no unverified security claims.
- Tests must not use real network or real LLM calls (mock them). Keep existing tests passing.
- Evaluation tuning uses DEV scenarios only; the TEST set is for final reporting.

## Commands
- Backend tests: cd backend && pytest
- Dashboard: cd dashboard && npm test && npm run build
- Stack: docker compose up --build (demo profile: --profile demo)
- Eval: python -m eval.run_eval ... (run by the human, needs real LLM keys)

## Conventions
Small commits per logical part; run tests after each; push to the working branch; summarize what changed WITHOUT printing secrets.
