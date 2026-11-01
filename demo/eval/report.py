"""Report generator producing results/eval.json and results/EVAL.md markdown tables."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .metrics import aggregate_eval_runs


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

    # 7. Limitations
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
