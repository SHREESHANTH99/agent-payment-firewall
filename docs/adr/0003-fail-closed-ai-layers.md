# ADR 0003: Fail-Closed Design for AI Risk Layers

## Status
Accepted

## Context
Large Language Models (Canary inspection and Risk Judge) are subject to external API outages, latency spikes, rate limits, and network errors.

## Decision
All AI risk inspection layers fail closed:
1. If the Canary scanner or Risk Judge raises a timeout, HTTP 429 quota error, or unexpected exception, the transaction is **never** approved automatically.
2. In production mode, errors either **escalate** to human review (if within budget/mandate) or **deny** outright, based on `JUDGE_FAIL_MODE`.
3. Deterministic rules run strictly before any AI check, ensuring hard limit violations are blocked with zero LLM dependencies.

## Consequences
Guarantees that an adversary cannot bypass the payment firewall by DoS-ing or exhausting LLM provider quotas.
