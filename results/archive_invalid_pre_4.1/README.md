# Archive: Invalid Pre-4.1 Benchmark Evaluation Results

These evaluation files (`eval.json`, `EVAL.md`, `progress.jsonl`, and early run transcripts) were produced with a **stale-mandate reuse bug** in `demo/agent/tools.py`.

### Cause of Invalidation
In pre-4.1 evaluations, the agent tool executor's `get_budget()` queried `GET /agent/mandate`. That endpoint searched for the latest active mandate without run-specific agent isolation, returning an earlier mandate that had already exhausted its $100 budget down to $8.52 in previous tests.

This caused:
1. Artificial `BUDGET_EXCEEDED` denials across subsequent test runs.
2. An artifactual "$0.00 unauthorized loss" report where in-policy prompt injections appeared to be stopped by rules.
3. An artificial ~31.2% false-positive rate on benign runs due to depleted balance rather than genuine firewall inspection.

**DO NOT CITE OR USE THESE ARCHIVED RESULTS.**  
Refer exclusively to Phase 4.1 valid benchmark and replay evaluation runs.
