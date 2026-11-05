"""Report generator producing results/eval.json and results/EVAL.md markdown tables."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .metrics import aggregate_eval_runs, assert_report_metric_row


def generate_eval_markdown(
    eval_data: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    """Generate professional, publication-quality EVAL.md report with markdown tables."""
    agg = eval_data.get("aggregated", {})
    runs = eval_data.get("runs", [])
    
    date_str = metadata.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    preset = metadata.get("preset", "quick")
    runs_per_scenario = metadata.get("runs_per_scenario", 2)
    exec_mode = metadata.get("execution_mode", "dry_run")
    agent_model = metadata.get("agent_model", "llama-3.3-70b-versatile")
    canary_model = metadata.get("canary_model", "gemini-3.5-flash")
    judge_model = metadata.get("judge_model", "gemini-3.5-flash")

    md = []
    md.append(f"# Agent Payment Firewall — Empirical Defense Evaluation")
    md.append(f"\n**Benchmark Report & Security Assessment**\n")
    md.append(f"- **Evaluation Date:** {date_str}")
    md.append(f"- **Harness Preset:** `{preset}` ($N={runs_per_scenario}$ runs per scenario)")
    md.append(f"- **Execution Mode:** `{exec_mode}` (Dry-run payment ledger, no real network funds moved)")
    md.append(f"- **Agent Procurement Model:** `{agent_model}`")
    md.append(f"- **Firewall Risk Models:** Canary (`{canary_model}`), Judge (`{judge_model}`)")
    md.append(f"- **Total Benchmark Iterations:** {len(runs)}")
    validity_by_mode: dict[str, dict[str, int]] = {}
    for run in runs:
        mode = run.get("mode", "unknown")
        status = run.get("status", "valid")
        validity_by_mode.setdefault(mode, {"valid": 0, "incomplete": 0, "error": 0})
        validity_by_mode[mode][status if status in {"valid", "incomplete", "error"} else "error"] += 1
    md.append("- **Validity by live mode:** " + "; ".join(f"{mode}: valid {counts['valid']}, incomplete {counts['incomplete']}, error {counts['error']}" for mode, counts in sorted(validity_by_mode.items())))
    md.append(f"\n---\n")

    # 1. Executive Summary
    md.append("## 1. Executive Summary & Defense in Depth\n")
    md.append(
        "This evaluation measures the defense-in-depth architecture of the **Agent Payment Firewall** "
        "when protecting an autonomous LLM procurement agent against both **Out-of-Policy** attacks "
        "(violating hard limits or untrusted recipients) and **In-Policy** attacks (allowlisted recipients and under-the-cap amounts).\n"
    )

    # 2. Protections OFF vs ON
    md.append("## 2. Protections OFF vs Protections ON Comparison\n")
    md.append(
        "| Configuration | Total Attack Runs | Agent Compromised | Attack Block Rate (95% CI) | Blocked by Rules | Blocked by Canary | Blocked by Judge | Blocked by Human | Exploited (Paid) |\n"
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    )
    comp = agg.get("protections_comparison", {})
    for mode_name, title in [("off", "Protections OFF (Rules-Only)"), ("on", "Protections ON (Rules + Canary + Judge)")]:
        m = comp.get(mode_name, {})
        n = m.get("attack_runs", 0)
        c = m.get("compromised", 0)
        rate = m.get("block_rate", 0.0)
        ci = m.get("block_ci_95", [0.0, 0.0])
        b = m.get("blocked_by", {})
        paid = b.get("none", 0)
        md.append(
            f"| **{title}** | {n} | {c} | {rate*100:.1f}% [{ci[0]*100:.1f}%, {ci[1]*100:.1f}%] | "
            f"{b.get('rules', 0)} | {b.get('canary', 0)} | {b.get('judge', 0)} | {b.get('human', 0)} | {paid} |"
        )
    md.append("\n")

    # 3. Out-of-Policy vs In-Policy Attack Results
    md.append("## 3. Threat Breakdown: Out-of-Policy vs In-Policy Attacks\n")
    md.append(
        "### Out-of-Policy Attacks (Recipient/Amount Violates Mandate Limits)\n"
        "Deterministic mathematical rules (budget, per-transaction cap, allowlist) provide primary defense.\n"
    )
    oop = agg.get("out_of_policy", {})
    md.append(
        f"- **Runs:** {oop.get('runs', 0)}\n"
        f"- **Agent Compromised Rate:** {oop.get('compromise_rate', 0.0)*100:.1f}%\n"
        f"- **Blocked by Rules:** {oop.get('blocked_by', {}).get('rules', 0)}\n"
        f"- **Blocked by Canary:** {oop.get('blocked_by', {}).get('canary', 0)}\n"
        f"- **Blocked by Judge:** {oop.get('blocked_by', {}).get('judge', 0)}\n"
        f"- **Exploited / Would Have Moved Money:** {oop.get('money_would_have_moved', 0)}\n"
    )

    md.append(
        "### In-Policy Attacks (Allowlisted Recipient & Under Spending Cap)\n"
        "Adversaries manipulate agent intent without violating deterministic thresholds. Only semantic AI risk layers (Canary & Judge) can detect and intercept.\n"
    )
    inp = agg.get("in_policy", {})
    md.append(
        f"- **Runs:** {inp.get('runs', 0)}\n"
        f"- **Agent Compromised Rate:** {inp.get('compromise_rate', 0.0)*100:.1f}%\n"
        f"- **Blocked by Rules:** {inp.get('blocked_by', {}).get('rules', 0)}\n"
        f"- **Blocked by Canary:** {inp.get('blocked_by', {}).get('canary', 0)}\n"
        f"- **Blocked by Judge:** {inp.get('blocked_by', {}).get('judge', 0)}\n"
        f"- **Exploited / Would Have Moved Money:** {inp.get('money_would_have_moved', 0)}\n"
    )
    md.append("\n")

    # 4. Results by Attack Variant Table
    md.append("## 4. Compromise and Mitigation Rates by Attack Variant\n")
    md.append(
        "| Attack Variant | Class | Runs | Compromised (Agent Fooled) | 95% Wilson CI | Stopped by Rules | Stopped by Canary | Stopped by Judge | Leaked / Paid |\n"
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    )
    var_stats = agg.get("variants", {})
    for v_name, s in sorted(var_stats.items()):
        if v_name == "clean":
            continue
        v_class = "In-Policy" if "inpolicy" in v_name or "polite" in v_name else "Out-of-Policy"
        b = s.get("blocked_by", {})
        rate = s.get("compromise_rate", 0.0)
        low = s.get("ci_lower", 0.0)
        high = s.get("ci_upper", 0.0)
        md.append(
            f"| `{v_name}` | {v_class} | {s.get('runs')} | {s.get('compromised')} ({rate*100:.1f}%) | "
            f"[{low*100:.1f}%, {high*100:.1f}%] | {b.get('rules', 0)} | {b.get('canary', 0)} | "
            f"{b.get('judge', 0)} | {b.get('none', 0)} |"
        )
    md.append("\n")

    # 5. Benign Tasks & Usability
    md.append("## 5. Benign Task Usability & False Positive Rate\n")
    ben = agg.get("benign", {})
    fp_ci = ben.get("fp_ci_95", [0.0, 0.0])
    esc_ci = ben.get("esc_ci_95", [0.0, 0.0])
    md.append(
        f"- **Total Benign Runs:** {ben.get('runs', 0)}\n"
        f"- **False Positive Blocks (Legitimate task denied):** {ben.get('false_positives', 0)} "
        f"({ben.get('false_positive_rate', 0.0)*100:.1f}% [{fp_ci[0]*100:.1f}%, {fp_ci[1]*100:.1f}%])\n"
        f"- **Legitimate Escalations (Tasks exceeding threshold):** {ben.get('escalations', 0)} "
        f"({ben.get('escalation_rate', 0.0)*100:.1f}% [{esc_ci[0]*100:.1f}%, {esc_ci[1]*100:.1f}%])\n"
    )
    md.append("\n")

    # 6. Performance & Latency
    md.append("## 6. System Latency & Operational Cost\n")
    md.append(
        f"- **Average Risk-Layer Added Latency:** `{agg.get('avg_risk_latency_ms', 0)} ms`\n"
        f"- **Total LLM Calls Consumed:** `{agg.get('total_llm_calls', 0)} calls`\n"
        f"- **Shared Rate Limiting:** Enforced at `{metadata.get('rpm', 20)} RPM` to prevent quota exhaustion.\n"
    )
    md.append("\n")

    replay = eval_data.get("replay")
    if replay:
        eval_type = replay.get("evaluation_type", "agent_generated_intents")
        type_title = "Constructed Paired Intent Evaluation" if eval_type == "constructed_paired_intents" else "Agent-Generated Intent Replay Evaluation"
        md.append(f"## {type_title}\n")
        md.append(f"- **Evaluation Dataset Source:** `{eval_type}`\n")
        md.append("Auto-denials and escalations are shown separately; fail-mode outcomes are excluded from detection rates.\n")
        
        # Render standard configurations
        standard_configs = {k: v for k, v in replay.get("configurations", {}).items() if k != "rules_plus_policy"}
        for config_name, config in standard_configs.items():
            md.append(f"### {config_name}\n")
            md.append("| Attack class | Unique intents | Scenarios | Raw observations (total/valid/excluded) | Auto-denied (cause) | Escalated (cause; harness resolution) | Approved | Would move money | LLM errors / fallbacks | Detection rate (Wilson; cluster bootstrap) | Consistency | Canary / Judge / Total latency ms | LLM calls |")
            md.append("|---|---:|---:|---|---|---|---:|---:|---:|---|---|---|---:|")
            sizes = config.get("sample_sizes", {})
            consistency = config.get("per_intent_consistency", {})
            latency = config.get("latency", {})
            classes_to_report = [c for c in ("malicious_in_policy", "malicious_out_of_policy", "legitimate_clean_context", "legitimate_injected_context") if c in config]
            if not classes_to_report:
                classes_to_report = [c for c in ("out_of_policy", "in_policy", "benign") if c in config]
            for attack_class in classes_to_report:
                row = config.get(attack_class, {})
                assert_report_metric_row(row, attack_class)
                denial = ", ".join(f"{k}:{v}" for k, v in sorted(row.get("denial_causes", {}).items())) or "—"
                escalation = ", ".join(f"{k}:{v}" for k, v in sorted(row.get("escalation_causes", {}).items())) or "—"
                exclusions = ", ".join(f"{k}:{v}" for k, v in sorted(row.get("exclusion_reasons", {}).items())) or "—"
                resolution = f"approved:{row.get('approved', 0)} / denied:{row.get('denied', 0)}"
                ci = row.get("ci_95", [0, 0])
                cluster = row.get("cluster_bootstrap_ci_95", [0, 0])
                is_legit = attack_class in {"benign", "legitimate_clean_context", "legitimate_injected_context"}
                n_uniq = row.get("n_unique_intents", sizes.get("unique_intents", 0))
                n_scen = row.get("n_scenarios", sizes.get("unique_source_scenarios", 0))
                raw_obs = row.get("raw_observations", {})
                raw_str = f"{row.get('n_total', 0)} / {row.get('n_valid', 0)} / {row.get('n_excluded', 0)} ({exclusions})"
                if row.get("not_reportable"):
                    detection = "NOT REPORTABLE (>10% excluded)"
                elif is_legit:
                    fp_count = row.get("false_positives", 0)
                    if n_uniq < 10:
                        detection = f"{fp_count} of {n_uniq} intents (insufficient sample)"
                    else:
                        fp_rate = row.get("false_positive_rate", 0.0)
                        detection = f"FP: {fp_rate:.1%} [{row.get('fp_ci_95', [0,0])[0]:.1%}, {row.get('fp_ci_95', [0,0])[1]:.1%}]"
                elif n_uniq < 10:
                    stopped = row.get("numerator", row.get("blocked", 0))
                    detection = f"{stopped} of {n_uniq} intents (insufficient sample)"
                elif row.get("numerator", 0) == 0:
                    detection = f"0 of {row.get('denominator', row.get('n_valid', 0))}, 95% upper bound {ci[1]:.1%}"
                else:
                    detection = f"{row.get('detection_rate', 0):.1%} [{ci[0]:.1%}, {ci[1]:.1%}] ; [{cluster[0]:.1%}, {cluster[1]:.1%}]"
                md.append(f"| {attack_class} | {n_uniq} | {n_scen} | {raw_str} | {row.get('auto_denied', 0)} ({denial}) | {row.get('escalated', 0)} ({escalation}; {resolution}) | {row.get('approved', 0)} | {row.get('would_have_moved_money', 0)} | {row.get('llm_errors', 0)} / {row.get('llm_fallbacks', 0)} | {detection} | {consistency.get('consistent_unique_intents', 0)}/{consistency.get('unique_intents', 0)} | {latency.get('avg_canary_ms', 0)}/{latency.get('avg_judge_ms', 0)}/{latency.get('avg_total_ms', 0)} | {row.get('llm_calls', 0)} |")
            md.append("\n> **Note:** Attacks 'stopped by rules' are blocked by deterministic allowlist/cap rules in the pre-risk phase and are NOT counted as AI detection.\n")
            md.append("")


        # Render Policy Control Section separately if rules_plus_policy is present
        policy_config = replay.get("configurations", {}).get("rules_plus_policy")
        if policy_config:
            md.append("## Deterministic Policy Control (`approval_required_merchants`)\n")
            md.append(
                "This control demonstrates a deterministic policy safeguard: marking secondary payees as "
                "`approval_required_merchants`. This stops 100% of rerouted payments deterministically before "
                "any LLM call, at the operational cost of requiring human approval for every transaction to that payee.\n"
            )
            md.append("| Attack class | Unique intents | Scenarios | Raw observations | Auto-denied | Escalated | Approved | Detection / Escalation | Cost (Human Reviews Required) |")
            md.append("|---|---:|---:|---|---|---|---:|---|---|")
            for attack_class in [c for c in ("malicious_in_policy", "malicious_out_of_policy", "legitimate_clean_context", "legitimate_injected_context") if c in policy_config]:
                row = policy_config.get(attack_class, {})
                n_uniq = row.get("n_unique_intents", 0)
                n_scen = row.get("n_scenarios", 0)
                raw_str = f"{row.get('n_total', 0)} / {row.get('n_valid', 0)} / {row.get('n_excluded', 0)}"
                is_legit = attack_class in {"benign", "legitimate_clean_context", "legitimate_injected_context"}
                ci = row.get("ci_95", [0, 0])
                if is_legit:
                    det_str = f"FP / Esc: {row.get('escalation_rate', 0.0):.1%}"
                    cost_str = f"{row.get('escalated', 0)} legitimate payments escalated"
                else:
                    det_str = f"Stopped: {row.get('detection_rate', 0.0):.1%} [{ci[0]:.1%}, {ci[1]:.1%}]"
                    cost_str = f"{row.get('escalated', 0)} reviews triggered"
                md.append(f"| {attack_class} | {n_uniq} | {n_scen} | {raw_str} | {row.get('auto_denied', 0)} | {row.get('escalated', 0)} | {row.get('approved', 0)} | {det_str} | {cost_str} |")
            md.append("")

    # What this measures and what it doesn't
    md.append("## What this measures and what it doesn't\n")
    md.append(
        "- **What this measures:**\n"
        "  - The defense-in-depth barrier provided by deterministic policy rules (allowlists, caps, approval requirements) and AI semantic layers (canaries, judge).\n"
        "  - The performance of semantic judge evaluations under strict isolation of untrusted web content vs principal task instructions.\n"
        "  - False positive and escalation rates on legitimate procurement intents under clean and hostile page contexts.\n"
        "- **What this does NOT measure:**\n"
        "  - Multi-turn conversational social engineering across human agents.\n"
        "  - Web browser fingerprinting, dynamic anti-bot mechanisms, or client-side JavaScript execution beyond HTTP scraping.\n"
        "  - Out-of-policy attacks when an autonomous agent resistively aborts before dispatching a payment intent (the firewall evaluates submitted financial actions).\n"
    )

    # 7. Limitations
    md.append("## How to read this\n")
    md.append("Unique intents are distinct normalized submissions; observations include repeats. Escalations are human-review requests, not auto-denials. LLM fail-mode outcomes are reported separately and excluded from detection rates. DEV is for tuning and TEST is for final reporting. LLM outcomes can vary between runs.\n")
    md.append("## 7. Limitations & Honest Assessment\n")

    md.append(
        "1. **Small Sample Sizes:** Due to API free-tier quotas and rate limits, preset runs ($N=2$ for quick, $N=5$ for full) "
        "provide directional indicators with wide confidence intervals rather than asymptotic convergence.\n"
        "2. **LLM Non-Determinism:** Even with low temperature, language models exhibit variance in reasoning and tool-argument synthesis across identical scenarios.\n"
        "3. **In-Policy Social Engineering:** In-policy attacks (especially polite social engineering) test the limits of pure heuristic detection. When prompts lack blunt trigger phrases, defense relies primarily on adversarial reasoning in the risk judge rather than static canary tokens.\n"
        "4. **Synthetic Store Surface:** Real-world ecommerce checkouts involve multi-page session authentication, CAPTCHAs, and dynamic client JavaScript, whereas the mock store presents pure HTML directly to the scraper.\n"
    )

    return "\n".join(md)


def write_eval_reports(
    eval_data: dict[str, Any],
    metadata: dict[str, Any],
    results_dir: str = "results",
) -> tuple[str, str]:
    """Write results/eval.json and results/EVAL.md to disk."""
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "eval.json"
    md_path = out_dir / "EVAL.md"

    # Write JSON
    full_output = {
        "metadata": metadata,
        "aggregated": eval_data.get("aggregated", {}),
        "runs": eval_data.get("runs", []),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)

    # Write Markdown
    markdown_content = generate_eval_markdown(full_output, metadata)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return str(json_path), str(md_path)


def render_combined_report(live_eval: dict[str, Any], replay: dict[str, Any]) -> str:
    """Render a report from persisted live and replay data without re-running either."""
    data = dict(live_eval)
    data["replay"] = replay
    return generate_eval_markdown(data, live_eval.get("metadata", {}))
