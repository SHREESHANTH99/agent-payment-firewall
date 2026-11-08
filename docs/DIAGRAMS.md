# Spendlatch Architecture and Diagrams

This reference contains the formal Mermaid diagrams and architecture definitions for Spendlatch (Agent Payment Firewall).

---

## 1. System Architecture

The firewall sits at the boundary between untrusted external content and the payment rails:

```mermaid
flowchart TD
    subgraph Untrusted ["Untrusted Environment"]
        Page["External Web Page / Catalog (Potential Injection)"]
        Agent["AI Procurement Agent"]
    end

    subgraph Spendlatch ["Spendlatch Firewall (Trusted Proxy)"]
        API["FastAPI Intent Endpoint (POST /intents)"]
        State["State Stores: Postgres (Source of Truth) & Redis (Rebuildable)"]
        Pipeline["Inspection Pipeline: Rules, Budget, Canary, Judge"]
    end

    subgraph Settlement ["Settlement Rails (Sandbox Only)"]
        PayPal["PayPal Sandbox Payouts API"]
        Human["Human Operator (Escalation Review)"]
    end

    Page -->|Context| Agent
    Agent -->|Submit Intent| API
    API --> Pipeline
    Pipeline <--> State
    Pipeline -->|Approved| PayPal
    Pipeline -->|Escalated| Human
    Pipeline -->|Denied / Freeze| State
```
*Figure 1: Spendlatch system architecture and trust boundaries.*

---

## 2. Intent Pipeline

Every payment intent submitted to Spendlatch undergoes six sequential checks:

```mermaid
flowchart LR
    Start([Intent Received]) --> C1[1. Idempotency Check]
    C1 --> C2[2. Mandate & Rules]
    C2 --> C3[3. Atomic Budget Reservation]
    C3 --> C4[4. Canary Scanner]
    C4 --> C5[5. LLM Risk Judge]
    C5 --> C6[6. Decision & Settlement]
    C6 --> End([Approved / Escalated / Denied])
```
*Figure 2: Sequential intent inspection pipeline.*

---

## 3. Attack Lifecycle and Detection

How an indirect prompt injection attack unfolds and gets stopped:

```mermaid
sequenceDiagram
    autonumber
    actor Attacker as Malicious Page
    actor Agent as Procurement Agent
    participant Firewall as Spendlatch Firewall
    participant Human as Human Reviewer
    participant PayPal as PayPal Sandbox

    Attacker->>Agent: Supplies catalog with hidden prompt injection
    Agent->>Firewall: Submits hijacked payment intent (POST /intents)
    rect rgb(240, 240, 240)
        Note over Firewall: Checks 1-3: Rules & Budget evaluation
        Note over Firewall: Checks 4-5: Canary scan & LLM Judge evaluation
    end
    alt Out-of-policy Payee
        Firewall-->>Agent: Denied (Deterministic Allowlist)
    else Canary Tripped / High-Confidence Deviation
        Firewall-->>Agent: Denied (Mandate Frozen via Circuit Breaker)
    else In-policy Payee Reroute (Approval Required)
        Firewall->>Human: Escalated for Human Review
        Human-->>Firewall: Approve or Deny
    else Clean Valid Intent
        Firewall->>PayPal: Execute Payout (Sandbox)
    end
```
*Figure 3: Attack sequence and defense intervention points.*

---

## 4. Layer Coverage Matrix

Which defense layer covers which threat category:

```mermaid
flowchart TD
    subgraph Threats ["Threat Categories"]
        T1["Out-of-policy transfer (untrusted payee or over-cap amount)"]
        T2["Blunt tool-calling prompt injection in page context"]
        T3["Semantic task diversion (wrong-item substitution)"]
        T4["Subtle payee rerouting among allowlisted merchants"]
        T5["Concurrent balance overdraw / replay attack"]
    end

    subgraph Defenses ["Covering Defense Layer"]
        D1["Deterministic Mandate Rules (Allowlist & Caps)"]
        D2["Canary Scanner (Gullible LLM Honeypot)"]
        D3["Adversarial LLM Judge (Semantic Task Comparison)"]
        D4["Policy Control: approval_required_merchants (Human Review)"]
        D5["Redis Idempotency & Lua CAS Reservation"]
    end

    T1 --> D1
    T2 --> D2
    T3 --> D3
    T4 --> D4
    T5 --> D5
```
*Figure 4: Risk coverage mapping across deterministic, LLM, and policy layers.*
