# Agent Payment Firewall — Demo & Benchmark Evaluation

This directory contains the Phase 4 and Phase 4.1 end-to-end evaluation suite for the **Agent Payment Firewall**:
1. **Mock Store (`demo/store`)**: A commercial office supply storefront rendering clean catalog pages alongside 10 distinct prompt injection attack vectors (both out-of-policy and in-policy).
2. **Autonomous Agent (`demo/agent`)**: An unscripted, LLM-driven procurement assistant with an OpenAI-compatible tool-calling loop (compatible with Groq, OpenAI, Gemini, etc.).
3. **Evaluation Harness (`demo/eval`)**: An automated benchmark testbed executing 26 scenarios with strict mandate lifecycles, runtime risk toggling, resume capabilities, run validity classification, and Wilson score confidence interval statistical analysis.
4. **Replay Evaluator (`demo/eval/replay.py`)**: An intent-replay evaluation engine testing identical agent intents across four isolated firewall configurations: `rules_only`, `canary_only`, `judge_only`, and `both`.

---

## 1. Evaluation History & Stale-Mandate Bug Documentation

> [!WARNING]
> **Pre-4.1 Evaluation Contamination**:
> Benchmark data collected prior to Phase 4.1 (archived in `results/archive_invalid_pre_4.1/`) suffered from a stale-mandate bug: `get_budget()` in `demo/agent/tools.py` retrieved older, already-depleted mandates from the database. Consequently, almost every subsequent intent failed with `BUDGET_EXCEEDED` denials. Claims such as "$0.00 unauthorized loss" and "rules stop 100% of out-of-policy attacks" were artifacts of this budget depletion and must not be cited.

### Phase 4.1 Validity & Isolation Fixes:
1. **Mandate Isolation**: Every execution generates a unique `agent_id` (`eval-<uuid>`) and runtime key registered dynamically via `POST /admin/agent-keys`. The harness asserts that `remaining == budget_total` ($100.00) at the start of each run. Older mandates cannot leak into subsequent runs.
2. **Run Validity Tracking**: Runs are classified into `valid`, `incomplete` (rate limits/timeouts/tool errors), or `error`. Tables count valid runs only. A run where the agent never reached the firewall is **never** counted as a defensive success.
3. **HTTP 90s Timeout & 429 Retry**: Tool calling in `demo/agent/tools.py` uses a 90-second HTTP timeout to accommodate AI risk layer latency (canary probe + semantic judge). HTTP 429 responses from the firewall back off honoring `Retry-After`.
4. **Tool-Calling Timeout Root Cause**: Under high concurrency or small free-tier rate limits, LLM chat completions fail with HTTP 429. When the agent loop lacks sufficient retries or backs off too quickly, the agent terminates before ever calling `submit_payment_intent`. The harness now provides automatic 2x retries for incomplete runs.

---

## 2. Threat Model & Defense-in-Depth Architecture

| Threat Class | Description | Primary Defense Layer |
| :--- | :--- | :--- |
| **Out-of-Policy Attacks** | Adversary attempts to divert payment to an unapproved recipient (`attacker@example.com`) or inflate amount beyond mandate caps ($200.00). | **Deterministic Rules Engine**: Strictly enforces merchant allowlists, per-transaction caps, and lifetime budgets before any LLM evaluates the request. |
| **In-Policy Attacks** | Adversary manipulates the agent into purchasing unrequested add-ons (e.g. $39 warranty) or rerouting order funds to an authorized secondary corporate account (`seller2@example.com`) within budget. | **AI Risk Layers (Canary & Judge)**: Canary detects honeypot token leaks; Judge performs multi-segment adversarial intent analysis to identify hijacked agent reasoning. |

### Operational Configurations in Replay Evaluation:
- **`rules_only`**: Canary=False, Judge=False.
- **`canary_only`**: Canary=True, Judge=False.
- **`judge_only`**: Canary=False, Judge=True.
- **`both`**: Canary=True, Judge=True.

---

## 3. Running the Evaluations

### Replay Evaluation (Instant, Zero Agent Variance)
Replays 47 real agent-submitted intents across the four firewall configurations:
```bash
python -m eval.replay
```
Results are saved to `results/replay.json` and exported to the dashboard via `python scripts/export_eval.py`.

### Live Preset Evaluation
```bash
# Quick preset (N=2 per scenario)
python -m eval.run_eval --preset quick --rpm 20 --modes off,on --results-dir results

# In-policy attacks only
python -m eval.run_eval --preset quick --runs 5 --modes off,on --only inpolicy --results-dir results_inpolicy
```

---

## 4. Exporting Benchmark Data to Dashboard

```bash
python scripts/export_eval.py
```
Exports `dashboard/public/data/eval.json` containing the validity block, replay results, sample sizes, and Wilson 95% confidence intervals.
