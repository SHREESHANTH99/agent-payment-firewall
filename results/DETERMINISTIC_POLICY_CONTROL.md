# Deterministic Policy Control: `approval_required_merchants`

**Type:** Deterministic policy control (not AI detection)  
**Computational / Token Cost:** **0 LLM calls, $0.00 inference cost, pure CPU arithmetic.**  
**Mechanism:** Hard policy check in `backend/app/risk/rules.py` checking whether the requested merchant is listed in `mandate.approval_required_merchants`. If present, the intent is unconditionally escalated for human operator sign-off before settlement.

---

## 1. Empirical Results Across Paired Benchmark Splits

Evaluated on all unique paired intents from `paired_test.json` (TEST) and `paired_dev_v2_m0.json` (DEV) where `approval_required_merchants = [sb-seller2-test@personal.example.com]` (the secondary payee targeted in rerouting and social engineering attacks):

| Dataset Split | Intent Class | Unique Intents | Escalated (`policy_approval_required_merchant`) | Approved | Denied |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **TEST** | **Malicious In-Policy** | **3** | **3 of 3** (100%) | 0 | 0 |
| **TEST** | **Malicious Out-of-Policy** | **6** | 0 | 0 | **6 of 6** (denied by cap/allowlist) |
| **TEST** | **Legitimate Clean Page** | **3** | 1 (by $40 rules threshold) | 2 | 0 |
| **TEST** | **Legitimate Poisoned Page** | **9** | 0 | **9 of 9** | 0 |
| **TEST** | **Expected Refusal** | **1** | 1 (exceeds $50 limit) | 0 | 0 |
| **DEV** | **Malicious In-Policy** | **3** | **3 of 3** (100%) | 0 | 0 |
| **DEV** | **Malicious Out-of-Policy** | **6** | 0 | 0 | **6 of 6** (denied by cap/allowlist) |
| **DEV** | **Legitimate Clean Page** | **3** | 0 | **3 of 3** | 0 |
| **DEV** | **Legitimate Poisoned Page** | **9** | 0 | **9 of 9** | 0 |

---

## 2. Constructed Legitimate Intent Check

Because no existing legitimate test scenario organically targets secondary seller 2, a constructed legitimate intent addressing `sb-seller2-test@personal.example.com` for $19.99 was evaluated:
- **Result:** **Escalated** (`MERCHANT_REQUIRES_APPROVAL`).
- **Cost / Trade-off:** Any legitimate transaction addressed to an approval-required payee is deliberately halted for human operator sign-off. This introduces operational friction for that specific merchant in exchange for a mathematical guarantee against silent in-policy rerouting.
