# ADR 0001: Integer Cents Internal Representation

## Status
Accepted

## Context
Floating point arithmetic (`0.1 + 0.2 = 0.30000000000000004`) introduces rounding inaccuracies that can violate budget limits, break hash chains, and cause reconciliation discrepancies.

## Decision
All financial figures across the system are strictly stored and computed as **integer cents** (e.g., \$15.50 is stored as `1550`). Conversion happens immediately upon request ingestion and formatting to two-decimal strings is deferred strictly to payout execution.

## Consequences
Eliminates all rounding errors and guarantees exact equality checks during atomic budget reservation.
