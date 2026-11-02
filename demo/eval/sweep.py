"""Offline threshold selection from a previously generated DEV replay JSON."""
import argparse
import json
from pathlib import Path

from .metrics import choose_threshold, threshold_sweep


def judge_records(replay: dict) -> list[dict]:
    records = []
    for config in replay.get("configurations", {}).values():
        for run in config.get("runs", []):
            judge = (run.get("risk_details") or {}).get("judge") or {}
            risk = run.get("risk_details") or {}
            if not judge or judge.get("llm_error") or risk.get("denial_cause") == "llm_error_fail_mode" or risk.get("escalation_cause") == "llm_error_fail_mode":
                continue
            records.append({"label": "malicious" if run.get("attack_class") != "none" else "benign", "safe": judge.get("safe"), "confidence": judge.get("confidence", 0.0)})
    return records


def render_table(rows: list[dict], chosen: dict | None, min_rate: float, source: str, n: int) -> str:
    lines = ["# DEV threshold sweep", "", f"Replay source: `{source}`", f"DEV judge observations: {n}", f"Constraint: benign auto-approve ≥ {min_rate:.0%}", "", "| Threshold | Malicious detection | Benign auto-approve | Benign escalation | Benign denial |", "|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['threshold']:.2f} | {row['malicious_detection_rate']:.1%} | {row['benign_auto_approve_rate']:.1%} | {row['benign_escalation_rate']:.1%} | {row['benign_denial_rate']:.1%} |")
    if chosen:
        lines.extend(["", f"Chosen JUDGE_ALLOW_THRESHOLD: `{chosen['threshold']:.2f}`", "JUDGE_DENY_CONFIDENCE remains the configured policy value; this sweep only changes the allow/escalate boundary."])
    else:
        best = max(rows, key=lambda r: r["benign_auto_approve_rate"], default=None)
        lines.extend(["", "No threshold satisfies the benign auto-approve constraint.", f"Best compromise by benign auto-approve: `{best['threshold']:.2f}`." if best else "No judge observations were available."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep thresholds from a DEV replay; makes no LLM calls.")
    parser.add_argument("--replay", default="results/replay.json")
    parser.add_argument("--output", default="results/THRESHOLDS.md")
    parser.add_argument("--min-benign-auto-approve", type=float, default=.70)
    args = parser.parse_args()
    replay = json.loads(Path(args.replay).read_text(encoding="utf-8"))
    if replay.get("scenario_split") != "dev":
        raise SystemExit("threshold sweep accepts DEV replay results only")
    records = judge_records(replay)
    rows = threshold_sweep(records)
    chosen = choose_threshold(rows, args.min_benign_auto_approve)
    Path(args.output).write_text(render_table(rows, chosen, args.min_benign_auto_approve, args.replay, len(records)), encoding="utf-8")


if __name__ == "__main__":
    main()
