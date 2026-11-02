# Evaluation scenario splits

Every scenario has an explicit `split`. For each two-task attack variant, task `*_1` is DEV and `*_2` is TEST. Benign tasks alternate DEV/TEST; the escalation and refusal outcomes are distributed across the two sets. Tune thresholds and canary prompts only with DEV. TEST is reserved for final reporting.

Run commands from the repository root:

```powershell
# Live DEV, protections off
python -m eval.run_eval --split dev --modes off --runs 5 --rpm 10 --resume
# DEV replay (supply the stored OFF intents through the replay entrypoint)
python -m demo.eval.replay --split dev --repeats 3
# Offline DEV-only threshold sweep
python -m demo.eval.sweep --replay results/replay.json --min-benign-auto-approve 0.70
# Final TEST replay and live modes; do not tune afterwards
python -m demo.eval.replay --split test --repeats 3
python -m eval.run_eval --split test --modes off,on --runs 5 --rpm 10 --resume
# Export only final TEST data (DEV requires --allow-dev)
python scripts/export_eval.py
```
