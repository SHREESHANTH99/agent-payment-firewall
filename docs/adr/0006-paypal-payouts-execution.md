# ADR 0006: PayPal Payouts as the Execution Path

## Status
Accepted

## Context
Autonomous agents require programmatic disbursement to external merchant accounts without interactive browser popups, 3D-Secure challenges, or human presence.

## Decision
We utilize the PayPal Payouts v1 API targeting Sandbox:
1. Payouts execute server-to-server via asynchronous batch dispatch.
2. The firewall records the `payout_batch_id` and registers webhooks for asynchronous settlement confirmation (`PAYMENT.PAYOUTS-ITEM.SUCCEEDED`).
3. If webhooks are delayed, a background scheduler polls `GET /v1/payments/payouts/{batch_id}`.

## Consequences
Enables completely headless, autonomous settlement with two-phase commit verification.
