# ADR 0004: Canary Honeypot Tool Call Detection

## Status
Accepted

## Context
Semantic prompt injection can persuade an agent to deviate from instructions without triggering token pattern matchers.

## Decision
We inject synthetic, unadvertised honeypot tool definitions (such as `system_override_admin_token`) into the LLM's available tool list.
- A legitimate agent prompted with user procurement tasks will never invoke these tools.
- If an injected payload instructs the agent to invoke the honeypot tool, the firewall intercepts the call immediately with zero LLM inference cost.

## Consequences
Provides an extremely low-cost, high-confidence tripwire for tool-calling prompt injection attacks.
