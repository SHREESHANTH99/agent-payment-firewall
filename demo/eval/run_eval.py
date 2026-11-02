"""CLI benchmark runner for Agent Payment Firewall Phase 4 evaluation."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import yaml
from dotenv import load_dotenv

# Ensure .env is loaded into process environment
load_dotenv()

from demo.agent.config import agent_settings
from .harness import EvalHarness
from .metrics import aggregate_eval_runs
from .report import write_eval_reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eval.run")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run evaluation harness producing honest, measured firewall defense benchmarks."
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=["quick", "full"],
        default="quick",
        help="Evaluation preset: quick (N=2) or full (N=5)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Explicitly override number of runs per scenario (default: 2 for quick, 5 for full)",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=20,
        help="Shared requests-per-minute rate limit (default: 20)",
    )
    parser.add_argument(
        "--max-llm-calls",
        type=int,
        default=12,
        help="Maximum LLM calls budget per scenario iteration (default: 12)",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default="off,on",
        help="Comma-separated firewall risk modes to evaluate (default: 'off,on')",
    )
    parser.add_argument(
        "--agent-mode",
        type=str,
        choices=["naive", "hardened"],
        default="naive",
        help="Agent mode: naive (default) or hardened (defensive prompt)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip completed runs recorded in results/progress.jsonl",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Run only scenario matching this exact ID substring",
    )
    parser.add_argument(
        "--scenarios-path",
        type=str,
        default="demo/eval/scenarios.yaml",
        help="Path to scenarios YAML configuration",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results",
        help="Output directory for progress and benchmark reports",
    )
    parser.add_argument(
        "--firewall-url",
        type=str,
        default="http://localhost:8000",
        help="Firewall base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--store-url",
        type=str,
        default="http://localhost:9000",
        help="Mock store base URL (default: http://localhost:9000)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    runs_per_scenario = args.runs if args.runs is not None else (2 if args.preset == "quick" else 5)
    modes = [m.strip().lower() for m in args.modes.split(",") if m.strip()]
    
    # Load scenarios
    scenarios_file = Path(args.scenarios_path)
    if not scenarios_file.exists():
        logger.error("Scenarios file not found at %s", args.scenarios_path)
        sys.exit(1)

    with open(scenarios_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        all_scenarios = data.get("scenarios", [])

    if args.only:
        all_scenarios = [s for s in all_scenarios if args.only in s.get("id", "")]
        logger.info("Filtered scenarios to %d matching '--only %s'", len(all_scenarios), args.only)

    logger.info(
        "Starting Benchmark: %d scenarios, modes=%s, N=%d per scenario (total runs=%d)",
        len(all_scenarios),
        modes,
        runs_per_scenario,
        len(all_scenarios) * len(modes) * runs_per_scenario,
    )

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    progress_file = results_dir / "progress.jsonl"

    harness = EvalHarness(
        firewall_base_url=args.firewall_url,
        store_base_url=args.store_url,
        rpm=args.rpm,
        progress_path=str(progress_file),
    )

    completed_keys = harness.load_completed_keys() if args.resume else set()
    logger.info("Loaded %d completed iterations from %s", len(completed_keys), progress_file)

    all_completed_records: list[dict[str, Any]] = []

    # If resuming, load existing records
    if progress_file.exists():
        with open(progress_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        all_completed_records.append(json.loads(line.strip()))
                    except Exception:
                        pass

    # Execution loop
    for mode in modes:
        logger.info(">>> EVALUATING MODE: %s <<<", mode.upper())
        for scenario in all_scenarios:
            s_id = scenario["id"]
            for r_idx in range(1, runs_per_scenario + 1):
                key = f"{s_id}:{mode}:{r_idx}"
                if args.resume and key in completed_keys:
                    logger.info("Skipping completed run %s", key)
                    continue

                logger.info("Running [%s] mode=%s run=%d/%d: %s", s_id, mode, r_idx, runs_per_scenario, scenario["task"][:50])
                try:
                    record = await harness.execute_run(
                        scenario=scenario,
                        mode=mode,
                        run_index=r_idx,
                        agent_settings=agent_settings,
                        agent_mode=args.agent_mode,
                        max_llm_calls=args.max_llm_calls,
                    )
                    all_completed_records.append(record)
                    logger.info(
                        "Run %s complete: Compromised=%s, BlockedBy=%s, Executed=%s",
                        key,
                        record["agent_compromised"],
                        record["blocked_by"],
                        record["would_have_executed"],
                    )
                except Exception as exc:
                    logger.error("Failed run %s: %s", key, exc)

    # Aggregate and generate reports
    aggregated = aggregate_eval_runs(all_completed_records)
    metadata = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "preset": args.preset,
        "runs_per_scenario": runs_per_scenario,
        "execution_mode": "dry_run",
        "agent_model": agent_settings.AGENT_MODEL,
        "canary_model": getattr(agent_settings, "CANARY_MODEL", "gemini-3.5-flash"),
        "judge_model": getattr(agent_settings, "JUDGE_MODEL", "gemini-3.5-flash"),
        "agent_mode": args.agent_mode,
        "rpm": args.rpm,
        "total_completed_runs": len(all_completed_records),
    }

    eval_output = {
        "aggregated": aggregated,
        "runs": all_completed_records,
    }

    json_path, md_path = write_eval_reports(eval_output, metadata, results_dir=args.results_dir)
    print("\n" + "=" * 60)
    print("🏆 BENCHMARK EVALUATION FINISHED")
    print(f"   Total Runs Processed: {len(all_completed_records)}")
    print(f"   Aggregated JSON:     {json_path}")
    print(f"   Markdown Report:     {md_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
