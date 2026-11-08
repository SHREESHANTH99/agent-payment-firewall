# Spendlatch System Architecture

For visual diagram flows, see [`docs/DIAGRAMS.md`](DIAGRAMS.md).

## Storage and State Division
- **PostgreSQL**: Authoritative source of truth for all entities: spending mandates, payment intents, and the immutable SHA-256 hash-chained audit ledger.
- **Redis**: Rebuildable operational cache used for fast distributed idempotency claims (`SETNX`) and atomic Lua-scripted budget reservations (`reserve`, `commit`, `release`).

## Trust Boundaries
1. **Untrusted External Data**: Any web page, product review, catalog DOM, or PDF processed by the agent.
2. **Semi-Trusted Agent**: Autonomous agents execute tasks on behalf of users, but their reasoning contexts can be hijacked via indirect prompt injection.
3. **Trusted Security Proxy**: Spendlatch enforces policy rules, deterministic budgets, honeypot traps, and LLM verification prior to invoking external payment rails.
4. **Settlement Rails**: PayPal Sandbox payouts and human review queues for transactions flagged as requiring escalation.
