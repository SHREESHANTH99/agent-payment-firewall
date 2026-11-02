# Evaluation scenario splits

Every scenario has an explicit `split`. For each two-task attack variant, task `*_1` is DEV and `*_2` is TEST. Benign tasks alternate DEV/TEST; the escalation and refusal outcomes are distributed across the two sets. Tune thresholds and canary prompts only with DEV. TEST is reserved for final reporting.
