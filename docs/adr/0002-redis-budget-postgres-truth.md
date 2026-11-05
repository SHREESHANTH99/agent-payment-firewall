# ADR 0002: Redis Two-Phase Budget Accounting with PostgreSQL as Source of Truth

## Status
Accepted

## Context
High-throughput autonomous agents can issue concurrent requests. Relying solely on relational database row locking introduces latency and deadlocks. However, relying purely on Redis risks catastrophic data loss if Redis restarts or evicts keys.

## Decision
1. **Redis Two-Phase Accounting**: Budget is reserved in memory using atomic Lua scripts (`reserve` $\rightarrow$ `commit` or `release`).
2. **PostgreSQL as Source of Truth**: When an intent transitions to `EXECUTED` or `FAILED`, the event is permanently written to PostgreSQL.
3. **Cold-Start Rebuild**: On server startup, `budget_service.rebuild_from_db` scans PostgreSQL and reconstructs all Redis spent counters before accepting incoming intents.

## Consequences
Combines sub-millisecond concurrency protection with bulletproof persistence.
