# ADR 0007: Dry-Run Execution Mode for Safe Evaluation

## Status
Accepted

## Context
Benchmarking agent defenses against hundreds of prompt injection variants must never risk unintended financial settlement or deplete sandbox merchant quotas.

## Decision
We implement `EXECUTION_MODE=dry_run`:
1. All pipeline checkpoints (idempotency, rules, atomic budget, canary, judge, audit logging) execute identically to live mode.
2. Payout network calls to PayPal are bypassed, recording synthetic mock settlement IDs in the audit ledger.

## Consequences
Enables reproducible evaluation without third-party network flakiness.
