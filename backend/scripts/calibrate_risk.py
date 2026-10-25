"""Calibration runner measuring Canary, AI Judge, and Combined detection and false-positive rates."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List

import yaml

from app.core.config import settings
from app.risk.canary import canary_scan
from app.risk.judge import judge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("calibrate_risk")


def calculate_metrics(
    benign_results: List[Dict[str, Any]],
    injection_results: List[Dict[str, Any]],
    repeats: int,
) -> Dict[str, Any]:
    """Calculate accuracy, false positive rates, category breakdowns, and latencies."""
    # 1. Benign / False Positive analysis
    total_benign_runs = len(benign_results) * repeats
    canary_fp_runs = 0
    judge_fp_runs = 0  # Judge flagged as unsafe or denied
    combined_fp_runs = 0

    for item in benign_results:
        runs = item.get("runs", [])
        for r in runs:
            c_tripped = r.get("canary_tripped", False)
            j_verdict = r.get("judge_verdict", "allow")
            j_flagged = (j_verdict == "deny" or not r.get("judge_safe", True))

            if c_tripped:
                canary_fp_runs += 1
            if j_flagged:
                judge_fp_runs += 1
            if c_tripped or j_flagged:
                combined_fp_runs += 1

    canary_fp_rate = (canary_fp_runs / total_benign_runs) if total_benign_runs else 0.0
    judge_fp_rate = (judge_fp_runs / total_benign_runs) if total_benign_runs else 0.0
    combined_fp_rate = (combined_fp_runs / total_benign_runs) if total_benign_runs else 0.0

    # 2. Injection / Detection analysis
    total_inj_runs = len(injection_results) * repeats
    canary_detected_runs = 0
    judge_detected_runs = 0
    combined_detected_runs = 0

    category_stats: Dict[str, Dict[str, Any]] = {}

    total_latency_ms = 0.0
    total_calls = 0
    fallback_count = 0
    error_count = 0

    for item in injection_results:
        cat = item.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {
                "total_runs": 0,
                "canary_caught": 0,
                "judge_caught": 0,
                "combined_caught": 0,
            }

        runs = item.get("runs", [])
        for r in runs:
            total_calls += 1
            if r.get("canary_meta", {}).get("fallback_used") or r.get("judge_meta", {}).get("fallback_used"):
                fallback_count += 1
            if r.get("canary_error") or r.get("judge_error"):
                error_count += 1

            # Latencies
            c_lat = r.get("canary_meta", {}).get("latency_ms", 0.0)
            j_lat = r.get("judge_meta", {}).get("latency_ms", 0.0)
            total_latency_ms += (c_lat + j_lat)

            c_tripped = r.get("canary_tripped", False)
            j_verdict = r.get("judge_verdict", "allow")
            j_caught = (j_verdict in ("deny", "escalate") or not r.get("judge_safe", True))
            comb_caught = c_tripped or j_caught

            category_stats[cat]["total_runs"] += 1
            if c_tripped:
                canary_detected_runs += 1
                category_stats[cat]["canary_caught"] += 1
            if j_caught:
                judge_detected_runs += 1
                category_stats[cat]["judge_caught"] += 1
            if comb_caught:
                combined_detected_runs += 1
                category_stats[cat]["combined_caught"] += 1

    canary_det_rate = (canary_detected_runs / total_inj_runs) if total_inj_runs else 0.0
    judge_det_rate = (judge_detected_runs / total_inj_runs) if total_inj_runs else 0.0
    combined_det_rate = (combined_detected_runs / total_inj_runs) if total_inj_runs else 0.0

    avg_latency = (total_latency_ms / total_calls) if total_calls else 0.0

    # Format category breakdown rates
    category_breakdown = {}
    for cat, d in category_stats.items():
        tot = d["total_runs"]
        category_breakdown[cat] = {
            "runs": tot,
            "canary_rate": round(d["canary_caught"] / tot, 3) if tot else 0.0,
            "judge_rate": round(d["judge_caught"] / tot, 3) if tot else 0.0,
            "combined_rate": round(d["combined_caught"] / tot, 3) if tot else 0.0,
        }

    return {
        "sample_sizes": {
            "benign_cases": len(benign_results),
            "injection_cases": len(injection_results),
            "repeats": repeats,
            "total_benign_evaluations": total_benign_runs,
            "total_injection_evaluations": total_inj_runs,
        },
        "false_positive_rates": {
            "canary": round(canary_fp_rate, 4),
            "judge": round(judge_fp_rate, 4),
            "combined": round(combined_fp_rate, 4),
        },
        "overall_detection_rates": {
            "canary_alone": round(canary_det_rate, 4),
            "judge_alone": round(judge_det_rate, 4),
            "combined_defense": round(combined_det_rate, 4),
        },
        "category_breakdown": category_breakdown,
        "operational_metrics": {
            "total_evaluations": total_benign_runs + total_inj_runs,
            "average_latency_ms": round(avg_latency, 2),
            "fallback_calls": fallback_count,
            "errors": error_count,
        },
    }


def generate_markdown_report(metrics: Dict[str, Any], canary_model: str, judge_model: str) -> str:
    """Generate CALIBRATION.md formatted report with tables."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Risk Layer Detection & Calibration Report",
        "",
        f"**Date:** {now_str}  ",
        f"**Canary Model:** `{canary_model}`  ",
        f"**Judge Model:** `{judge_model}`  ",
        f"**Dataset Size:** {metrics['sample_sizes']['benign_cases']} benign contexts, {metrics['sample_sizes']['injection_cases']} injection contexts ({metrics['sample_sizes']['repeats']} repeats per case)  ",
        "",
        "---",
        "",
        "## 1. Overall Performance Summary",
        "",
        "| Metric | Canary Alone | Judge Alone | Combined Defense (Either Catches) |",
        "|---|:---:|:---:|:---:|",
        f"| **Attack Detection Rate** | {metrics['overall_detection_rates']['canary_alone'] * 100:.1f}% | {metrics['overall_detection_rates']['judge_alone'] * 100:.1f}% | **{metrics['overall_detection_rates']['combined_defense'] * 100:.1f}%** |",
        f"| **Benign False Positive Rate** | {metrics['false_positive_rates']['canary'] * 100:.1f}% | {metrics['false_positive_rates']['judge'] * 100:.1f}% | {metrics['false_positive_rates']['combined'] * 100:.1f}% |",
        "",
        "---",
        "",
        "## 2. Attack Detection Breakdown by Category",
        "",
        "| Attack Category | Evaluated Runs | Canary Trip Rate | Judge Catch Rate | Combined Detection |",
        "|---|:---:|:---:|:---:|:---:|",
    ]

    for cat, d in sorted(metrics["category_breakdown"].items()):
        c_pct = f"{d['canary_rate'] * 100:.1f}%"
        j_pct = f"{d['judge_rate'] * 100:.1f}%"
        cb_pct = f"{d['combined_rate'] * 100:.1f}%"
        lines.append(f"| `{cat}` | {d['runs']} | {c_pct} | {j_pct} | **{cb_pct}** |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Operational Telemetry",
        "",
        f"- **Total Evaluations:** {metrics['operational_metrics']['total_evaluations']}",
        f"- **Average Round-Trip Latency:** {metrics['operational_metrics']['average_latency_ms']} ms",
        f"- **Fallback Provider Invocations:** {metrics['operational_metrics']['fallback_calls']}",
        f"- **Unrecoverable Errors:** {metrics['operational_metrics']['errors']}",
        "",
        "> [!NOTE]",
        "> LLM detection is probabilistic and subject to model family variations and prompt phrasing.",
        "> The honeypot canary is specialized for active tool-calling traps, while the judge evaluates semantic intent alignment.",
        "",
    ])

    return "\n".join(lines)


async def run_single_case(text: str, is_injection: bool) -> Dict[str, Any]:
    """Execute canary scan and judge on a text context."""
    # 1. Canary
    c_res = await canary_scan(text)

    # 2. Judge with dummy mandate and intent
    mandate_summary = {
        "mandate_id": "mandate-calib-001",
        "agent_id": "agent-procurement",
        "budget_total": "100.00",
        "per_transaction_cap": "50.00",
        "allowlist_merchants": ["Office Supplies Staples Inc", "CloudScale Hosting Services LLC"],
    }
    intent_fields = {
        "amount": "15.00",
        "currency": "USD",
        "merchant": "Office Supplies Staples Inc",
        "description": "Standard stationery procurement",
        "reasoning": "Fulfilling team quarterly supplies request",
    }
    j_res, verdict = await judge(mandate_summary, intent_fields, text)

    return {
        "canary_tripped": c_res.tripped,
        "canary_calls": c_res.honeypot_calls,
        "canary_error": c_res.error,
        "canary_meta": c_res.meta or {},
        "judge_safe": j_res.safe,
        "judge_confidence": j_res.confidence,
        "judge_injection": j_res.injection_suspected,
        "judge_verdict": verdict,
        "judge_meta": j_res.meta or {},
    }


async def main():
    parser = argparse.ArgumentParser(description="Calibrate Canary and Judge risk layers.")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repetitions per case (default: 3)")
    parser.add_argument("--rpm", type=int, default=10, help="Requests per minute rate limit (default: 10)")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(Path(__file__).parent / "calibration_cases.yaml"),
        help="Path to YAML dataset",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        logger.error("Dataset file %s does not exist!", dataset_path)
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    benign_cases = data.get("benign", [])
    injection_cases = data.get("injection", [])

    logger.info("Loaded %d benign cases and %d injection cases.", len(benign_cases), len(injection_cases))

    # Calculate delay between calls to respect RPM: 60s / rpm
    delay_between_calls = 60.0 / float(args.rpm)
    logger.info("Enforcing rate limit: %d RPM (%.2fs delay between calls)", args.rpm, delay_between_calls)

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    evaluated_benign = []
    logger.info("--- Starting Benign Calibration ---")
    for b in benign_cases:
        case_runs = []
        for rep in range(args.repeats):
            logger.info("Evaluating benign case [%s] (repeat %d/%d)...", b["id"], rep + 1, args.repeats)
            run_data = await run_single_case(b["text"], is_injection=False)
            case_runs.append(run_data)
            await asyncio.sleep(delay_between_calls)
        evaluated_benign.append({
            "id": b["id"],
            "category": b.get("category", "benign"),
            "runs": case_runs,
        })

    evaluated_injections = []
    logger.info("--- Starting Injection Calibration ---")
    for inj in injection_cases:
        case_runs = []
        for rep in range(args.repeats):
            logger.info("Evaluating injection case [%s] (repeat %d/%d)...", inj["id"], rep + 1, args.repeats)
            run_data = await run_single_case(inj["text"], is_injection=True)
            case_runs.append(run_data)
            await asyncio.sleep(delay_between_calls)
        evaluated_injections.append({
            "id": inj["id"],
            "category": inj.get("category", "injection"),
            "runs": case_runs,
        })

    # Metrics aggregation
    metrics = calculate_metrics(evaluated_benign, evaluated_injections, repeats=args.repeats)

    # Save JSON results
    json_path = results_dir / "calibration.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "models": {
                    "canary": settings.CANARY_MODEL,
                    "judge": settings.JUDGE_MODEL,
                },
                "metrics": metrics,
            },
            f,
            indent=2,
        )
    logger.info("Saved calibration JSON to %s", json_path)

    # Save Markdown report
    md_content = generate_markdown_report(metrics, settings.CANARY_MODEL, settings.JUDGE_MODEL)
    md_path = results_dir / "CALIBRATION.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info("Saved calibration Markdown to %s", md_path)

    print("\n" + md_content + "\n")


if __name__ == "__main__":
    asyncio.run(main())
