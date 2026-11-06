# Archive: Label Correction Deviation

**Archived on:** 2026-11-06  
**Reason:** In the original TEST and DEV evaluation runs, scenarios with `expected_outcome` set to `refuse_budget` or `refuse_unavailable` (specifically `benign_unavailable_item` in TEST and `benign_impossible_budget` in DEV) were inadvertently lumped into `legitimate_clean_context`. Because these scenarios are expected refusals where the user task requests an item exceeding mandate spending caps, a denial by deterministic rules is the correct policy behavior, not a false positive.

### Key Details
- **Discovered:** After inspecting the frozen TEST benchmark dataset.
- **Scope of Change:** Classification label correction only.
- **Guarantees:** No prompts, rules, thresholds, models, or raw observations were altered.
- **Original Uncorrected Files Stored Here:**
  - `dev_replay_20261104_regen.json`
  - `paired_dev_v2_m0.json`
  - `paired_test.json`
