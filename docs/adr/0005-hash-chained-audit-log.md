# ADR 0005: Tamper-Evident SHA-256 Hash Chained Audit Log

## Status
Accepted

## Context
Payment logs stored in standard mutable relational database tables can be altered by compromised database credentials or administrative accidents.

## Decision
All audit events (`intent.created`, `intent.approved`, `intent.denied`, `intent.escalated`, `intent.executed`) are stored in an append-only hash chain:
1. Every row computes `row_hash = SHA256(prev_hash + sequence_id + timestamp + intent_id + event + payload)`.
2. Any retrospective modification or deletion invalidates subsequent hashes in the chain, enabling instantaneous cryptographic verification via `GET /audit/verify`.

## Consequences
Provides verifiable attribution and tamper detection for all autonomous financial transactions.
