# Threat Model: Agent Payment Firewall (Spendlatch)

## 0. Product Name & Etymology

**Spendlatch** (`spend` + `latch`): A *latch* is a physical hardware mechanism that firmly locks a barrier into place until explicitly released. Spendlatch acts as an automated settlement latch for autonomous AI agents — holding financial disbursements in a locked, dry-run state through six deterministic checkpoints until all security, budget, and policy conditions are satisfied.

---

## 1. System Assets
1. **Mandate Funds & Budget Limits**: Total lifetime/periodic spending allowances assigned to autonomous agents.
2. **Settlement Credentials**: PayPal Sandbox OAuth client credentials and payout execution tokens.
3. **Audit Ledger**: Append-only PostgreSQL SHA-256 hash-chained history of all intent evaluations and state transitions.
4. **Operator Secrets**: Admin tokens granting approval, mandate revocation, and configuration access.

---

## 2. Trust Boundaries
- **Untrusted External Web / Environment**: Any web page, merchant catalog, DOM element, PDF, or API response fetched by an agent.
- **Semi-Trusted Autonomous Agent**: Agent runtime with delegated procurement tasks. It can be prompt-injected or tricked.
- **Trusted Payment Firewall Core**: Deterministic rules, atomic budget accounting, honeypot canary, and hash-chain ledger.
- **Trusted Human Operator**: Admin authorized to unfreeze mandates and approve escalated transactions.

---

## 3. Threat Categories & Mitigations

| Threat / Attacker Type | Attack Vector | Mitigation Architecture | Implementing Module | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Malicious Web Content** | Prompt injection in product review/invoice overriding purchase task. | Honeypot canary tools + LLM semantic risk judge inspection. | `backend/app/risk/canary.py`, `backend/app/risk/judge.py` | Highly subtle indirect reroutes without blatant delimiters; mitigated by deterministic merchant allowlist. |
| **Compromised Agent** | Agent hijacked to send payment to attacker email. | Deterministic allowlist & per-transaction caps before AI risk layers. | `backend/app/risk/rules.py` | Attacker account compromise on an already allowlisted merchant. |
| **Allowlisted Merchant Reroute** | Injected text instructs agent to purchase from a different allowlisted merchant. | Deterministic `approval_required_merchants` policy control holding transfers for human sign-off. | `backend/app/services/pipeline.py` | 100% human review overhead for payees designated approval-required. |
| **Concurrent Budget Exhaustion** | Agent spawns parallel threads to race and overdraw mandate budget. | Atomic Redis Lua script (`INCRBY` + compare-and-swap balance checks). | `backend/app/services/budget.py` | Ephemeral Redis failure; mitigated by rebuilding state from Postgres on startup. |
| **Replay / Duplicate Attacks** | Agent retries intent on crash or network blip causing double-pay. | Atomic Redis `SETNX` idempotency lock with request payload hash. | `backend/app/services/idempotency.py` | Idempotency key collision across completely distinct intents (hash check prevents this). |
| **Webhook Spoofing** | Adversary posts forged payout success to trigger unauthorized budget commits. | Cryptographic verification via PayPal verify-webhook-signature API using raw payload bytes. | `backend/app/paypal/webhooks.py` | PayPal sandbox API availability. |
| **Operator Brute-Force** | Brute forcing `/ws/ticket` or admin endpoints. | Constant-time HMAC token comparison + per-IP sliding-window rate limiting. | `backend/app/core/security.py`, `backend/app/core/rate_limit.py` | Distributed credential stuffing across broad botnet IP ranges. |
| **Audit Log Tampering** | Attacker gaining database write access to modify past transaction records. | SHA-256 hash chain where each row embeds `prev_hash` of predecessor. | `backend/app/services/audit.py` | Database deletion of entire table history (mitigated by external replication/backups). |
