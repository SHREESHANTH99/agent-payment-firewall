"""Converts evaluation and calibration results into stable dashboard schemas."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Optional


def transform_eval_data(eval_data: dict[str, Any], calibration_data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Transforms eval_data into stable schema:
    {
      generated_at,
      models: {agent, canary, judge},
      execution_mode,
      sample_sizes,
      attack_categories: [{name, attack_class, runs, agent_compromised, blocked_by: {rules, canary, judge, human, none}, money_would_have_moved}],
      benign: {runs, false_positives, escalations},
      layers: {canary_alone, judge_alone, combined},
      avg_added_latency_ms,
      llm_calls
    }
    Rules: Do not invent, round up, or backfill values; omit keys that are missing.
    """
    metadata = eval_data.get("metadata", {})
    aggregated = eval_data.get("aggregated", {})
    runs = eval_data.get("runs", [])

    out: dict[str, Any] = {}

    # generated_at
    gen_at = metadata.get("date") or metadata.get("timestamp") or datetime.now(timezone.utc).isoformat()
    if gen_at:
        out["generated_at"] = gen_at

    # models
    models_dict = {}
    if metadata.get("agent_model"):
        models_dict["agent"] = metadata["agent_model"]
    if metadata.get("canary_model"):
        models_dict["canary"] = metadata["canary_model"]
    if metadata.get("judge_model"):
        models_dict["judge"] = metadata["judge_model"]
    if models_dict:
        out["models"] = models_dict

    # execution_mode
    if metadata.get("execution_mode"):
        out["execution_mode"] = metadata["execution_mode"]

    # sample_sizes
    if "total_runs" in aggregated:
        attack_count = len([r for r in runs if r.get("attack_class") != "none"])
        benign_count = aggregated.get("benign", {}).get("runs", 0)
        out["sample_sizes"] = {
            "total_runs": aggregated["total_runs"],
            "attack_runs": attack_count,
            "benign_runs": benign_count,
        }

    # attack_categories
    variants = aggregated.get("variants", {})
    if variants:
        categories = []
        for v_name, s in variants.items():
            if v_name == "clean":
                continue
            v_class = "in_policy" if "inpolicy" in v_name or "polite" in v_name else "out_of_policy"
            
            # calculate money_would_have_moved for this variant
            money_moved = sum(
                1 for r in runs if r.get("variant") == v_name and r.get("would_have_executed")
            )

            cat_item: dict[str, Any] = {
                "name": v_name,
                "attack_class": v_class,
                "runs": s.get("runs", 0),
                "agent_compromised": s.get("compromised", 0),
                "blocked_by": s.get("blocked_by", {}),
                "money_would_have_moved": money_moved,
            }
            categories.append(cat_item)
        out["attack_categories"] = categories

    # benign
    benign_data = aggregated.get("benign")
    if benign_data:
        out["benign"] = {
            "runs": benign_data.get("runs", 0),
            "false_positives": benign_data.get("false_positives", 0),
            "escalations": benign_data.get("escalations", 0),
        }

    # layers (detection rates from calibration or eval)
    if calibration_data:
        det_rates = calibration_data.get("metrics", {}).get("overall_detection_rates", {})
        if det_rates:
            layers_dict = {}
            if "canary_alone" in det_rates:
                layers_dict["canary_alone"] = det_rates["canary_alone"]
            if "judge_alone" in det_rates:
                layers_dict["judge_alone"] = det_rates["judge_alone"]
            if "combined_defense" in det_rates:
                layers_dict["combined"] = det_rates["combined_defense"]
            if layers_dict:
                out["layers"] = layers_dict
    elif "protections_comparison" in aggregated:
        on_data = aggregated.get("protections_comparison", {}).get("on", {})
        b = on_data.get("blocked_by", {})
        total_att = on_data.get("attack_runs", 0)
        if total_att > 0:
            out["layers"] = {
                "canary_alone": round(b.get("canary", 0) / total_att, 4),
                "judge_alone": round(b.get("judge", 0) / total_att, 4),
                "combined": round((b.get("canary", 0) + b.get("judge", 0)) / total_att, 4),
            }

    # avg_added_latency_ms
    if "avg_risk_latency_ms" in aggregated:
        out["avg_added_latency_ms"] = aggregated["avg_risk_latency_ms"]

    # llm_calls
    if "total_llm_calls" in aggregated:
        out["llm_calls"] = aggregated["total_llm_calls"]

    return out


def main():
    root_dir = Path(__file__).resolve().parent.parent
    results_dir = root_dir / "results"
    dashboard_data_dir = root_dir / "dashboard" / "public" / "data"
    dashboard_data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Locate eval.json
    eval_file = results_dir / "eval.json"
    if not eval_file.exists():
        print(f"Warning: {eval_file} not found. Creating placeholder eval.json from existing progress if any.")
        progress_file = results_dir / "progress.jsonl"
        runs = []
        if progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        runs.append(json.loads(line.strip()))
        from demo.eval.metrics import aggregate_eval_runs
        eval_data = {
            "metadata": {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "execution_mode": "dry_run"},
            "aggregated": aggregate_eval_runs(runs),
            "runs": runs,
        }
    else:
        with open(eval_file, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

    # 2. Locate calibration.json
    cal_file = results_dir / "calibration.json"
    if not cal_file.exists():
        backend_cal = root_dir / "backend" / "results" / "calibration.json"
        if backend_cal.exists():
            cal_file = backend_cal

    calibration_data = None
    if cal_file.exists():
        with open(cal_file, "r", encoding="utf-8") as f:
            calibration_data = json.load(f)

    # 3. Transform eval data
    transformed_eval = transform_eval_data(eval_data, calibration_data)

    target_eval_file = dashboard_data_dir / "eval.json"
    with open(target_eval_file, "w", encoding="utf-8") as f:
        json.dump(transformed_eval, f, indent=2)
    print(f"Exported eval data to {target_eval_file}")

    # 4. Copy calibration data if present
    if calibration_data:
        target_cal_file = dashboard_data_dir / "calibration.json"
        with open(target_cal_file, "w", encoding="utf-8") as f:
            json.dump(calibration_data, f, indent=2)
        print(f"Exported calibration data to {target_cal_file}")


if __name__ == "__main__":
    main()
