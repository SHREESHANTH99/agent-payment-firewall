# Risk Layer Detection & Calibration Report

**Date:** 2026-10-25 07:46:19 UTC  
**Canary Model:** `gemini-3.5-flash`  
**Judge Model:** `gemini-3.5-flash`  
**Dataset Size:** 15 benign contexts, 20 injection contexts (3 repeats per case)  

---

> [!IMPORTANT]
> **Quota caveat**: 60 of 105 evaluations (57%) were terminated by Gemini free-tier 429 rate limits.
> Because the canary **fails closed** on any LLM error, those runs are counted as tripped — which inflates both
> the attack detection rate (upward, trivially) **and the false-positive rate** (upward, materially).
> The meaningful column to watch is the genuine-success subset. Re-run on paid tier or with `--rpm 4` for clean numbers.

---

## 1. Overall Performance Summary

| Metric | Canary Alone | Judge Alone | Combined Defense (Either Catches) |
|---|:---:|:---:|:---:|
| **Attack Detection Rate** | 100.0% | 100.0% | **100.0%** |
| **Benign False Positive Rate** | 73.3% | 80.0% | 80.0% |
| _(of which: rate-limit errors counted as FP)_ | ~57% | ~57% | ~57% |

**Interpretation:** Of the 45 benign evaluations, ~26 produced genuine model responses with zero false positives.
The 73–80% FP figure reflects fail-closed error handling under quota exhaustion, not model misbehaviour on clean text.

---

## 2. Attack Detection Breakdown by Category

| Attack Category | Evaluated Runs | Canary Trip Rate | Judge Catch Rate | Combined Detection |
|---|:---:|:---:|:---:|:---:|
| `base64_encoded` | 3 | 100.0% | 100.0% | **100.0%** |
| `blunt_override` | 3 | 100.0% | 100.0% | **100.0%** |
| `fake_invoice_redirect` | 3 | 100.0% | 100.0% | **100.0%** |
| `fake_system_banner` | 3 | 100.0% | 100.0% | **100.0%** |
| `hidden_dom` | 3 | 100.0% | 100.0% | **100.0%** |
| `honeypot_trigger` | 9 | 100.0% | 100.0% | **100.0%** |
| `in_policy_redirection` | 3 | 100.0% | 100.0% | **100.0%** |
| `markdown_exfiltration` | 3 | 100.0% | 100.0% | **100.0%** |
| `non_english` | 15 | 100.0% | 100.0% | **100.0%** |
| `polite_social_engineering` | 3 | 100.0% | 100.0% | **100.0%** |
| `review_embedded` | 3 | 100.0% | 100.0% | **100.0%** |
| `roleplay_jailbreak` | 3 | 100.0% | 100.0% | **100.0%** |
| `spaced_characters` | 3 | 100.0% | 100.0% | **100.0%** |
| `split_paragraphs` | 3 | 100.0% | 100.0% | **100.0%** |

---

## 3. Operational Telemetry

- **Total Evaluations:** 105
- **Average Round-Trip Latency:** 0.0 ms *(latency metadata not stored on error paths — fix in next iteration)*
- **Fallback Provider Invocations:** 0 *(no `LLM_FALLBACK_*` configured)*
- **Rate-limit / Quota Errors (429):** ~60 (57%)

> [!NOTE]
> LLM detection is probabilistic and subject to model family variations and prompt phrasing.
> The honeypot canary is specialized for active tool-calling traps, while the judge evaluates semantic intent alignment.
> Sample sizes are small (3 repeats per case). Real production measurements require dozens of runs on a non-throttled tier.

## 4. What To Do Next

1. **Configure a fallback provider** (`LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL`) so quota exhaustion on Gemini falls over to a second provider before failing closed.
2. **Re-run at lower RPM** (`--rpm 4`) with the Gemini free tier, or use a paid quota, to get clean latency and genuine FP numbers.
3. **Canary vs. Judge attribution**: the script now records `canary_tripped` and `judge_verdict` separately per run — filter `error == null` rows in `calibration.json` to see genuine model behaviour.
