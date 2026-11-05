"""Offline DEV-only inspector for replayed judge misses."""
import argparse
import json
from pathlib import Path
import re
from typing import Any

from .metrics import normalized_intent_key
from .scenarios import load_scenarios


def source_context_excerpt(source_context: str, limit: int = 600) -> str:
    """Return a small contextual excerpt centered on suspicious instructions or email addresses."""
    text = source_context or ""
    match = re.search(r"[\w.+-]+@[\w.-]+|\b(ignore|instruction|system|transfer|payment|wire|urgent|override)\b", text, re.I)
    if not match:
        return text[:limit]
    start = max(0, match.start() - limit // 3)
    end = min(len(text), start + limit)
    return text[start:end]


def inspect_misses(replay: dict[str, Any], config: str, attack_class: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Group approved/error verdicts by normalized source intent without making calls."""
    if replay.get("scenario_split") != "dev" or replay.get("metadata", {}).get("split") != "dev":
        raise ValueError("miss inspection accepts DEV replay results only")
    load_scenarios("dev", purpose="tuning")  # enforce the split boundary independently of file metadata
    try:
        runs = replay["configurations"][config]["runs"]
    except KeyError as exc:
        raise ValueError(f"replay configuration not found: {config}") from exc

    grouped: dict[tuple[str, str, int, str], list[dict[str, Any]]] = {}
    for run in runs:
        if run.get("ground_truth_class") != attack_class and run.get("attack_class") != attack_class:
            continue
        risk = run.get("risk_details") or {}
        judge = risk.get("judge") or {}
        is_error = bool(judge.get("llm_error") or (judge.get("meta") or {}).get("parse_error"))
        if run.get("decision") != "approved" and not is_error:
            continue
        key = normalized_intent_key(run.get("scenario_id", ""), run.get("intent_request") or {})
        grouped.setdefault(key, []).append(run)

    counts = {"safe_confidence_ge_0_9": 0, "user_task_missing": 0, "provider_fallback_used": 0, "parse_failures": 0}
    entries: list[dict[str, Any]] = []
    for grouped_runs in grouped.values():
        first = grouped_runs[0]
        request = first.get("intent_request") or {}
        judges = [((run.get("risk_details") or {}).get("judge") or {}) for run in grouped_runs]
        safe_high = any(j.get("safe") is True and float(j.get("confidence") or 0) >= 0.9 for j in judges)
        missing_task = not str(request.get("user_task") or "").strip()
        fallback = any(bool((j.get("meta") or {}).get("fallback_used")) for j in judges)
        parse_failure = any(bool((j.get("meta") or {}).get("parse_error")) for j in judges)
        counts["safe_confidence_ge_0_9"] += int(safe_high)
        counts["user_task_missing"] += int(missing_task)
        counts["provider_fallback_used"] += int(fallback)
        counts["parse_failures"] += int(parse_failure)
        entries.append({
            "scenario_id": first.get("scenario_id"),
            "user_task": request.get("user_task") or "",
            "merchant": request.get("merchant"),
            "amount": request.get("amount"),
            "replayed_request_included_user_task": not missing_task,
            "judge_outputs": [{key: judge.get(key) for key in ("safe", "confidence", "injection_suspected", "mismatch_reasons", "reasons", "provider", "model")} for judge in judges],
            "provider": [judge.get("provider") or (judge.get("meta") or {}).get("provider") for judge in judges],
            "model": [judge.get("model") or (judge.get("meta") or {}).get("model") for judge in judges],
            "fallback_used": fallback,
            "parse_failure": parse_failure,
            "verdicts_across_repeats": [run.get("decision") for run in grouped_runs],
            "source_context_excerpt": source_context_excerpt(str(request.get("source_context") or "")),
        })
    return counts, entries


def render_markdown(counts: dict[str, int], entries: list[dict[str, Any]], config: str, attack_class: str, source: str) -> str:
    lines = ["# DEV replay miss inspection", "", f"Replay source: `{source}`", f"Configuration: `{config}`; class: `{attack_class}`", "", "## Summary", ""]
    for name, count in counts.items():
        lines.append(f"- {name}: {count}")
    for index, entry in enumerate(entries, 1):
        lines.extend(["", f"## Miss {index}: `{entry['scenario_id']}`", "", f"- User task: {entry['user_task']}", f"- Merchant / amount: `{entry['merchant']}` / `{entry['amount']}`", f"- Replayed request included user_task: {entry['replayed_request_included_user_task']}", f"- Provider / model: {entry['provider']} / {entry['model']}", f"- Fallback used / parse failure: {entry['fallback_used']} / {entry['parse_failure']}", f"- Verdicts across repeats: {entry['verdicts_across_repeats']}", f"- Judge outputs: `{json.dumps(entry['judge_outputs'])}`", f"- Source-context excerpt: {entry['source_context_excerpt']}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect DEV replay judge misses offline.")
    parser.add_argument("--replay", required=True)
    parser.add_argument("--config", default="judge_only")
    parser.add_argument("--class", dest="attack_class", default="in_policy", choices=["in_policy", "out_of_policy", "benign", "malicious_in_policy", "malicious_out_of_policy", "legitimate_clean_context", "legitimate_injected_context"])
    parser.add_argument("--out", default="results/dev_misses.md")
    args = parser.parse_args()
    replay = json.loads(Path(args.replay).read_text(encoding="utf-8"))
    counts, entries = inspect_misses(replay, args.config, args.attack_class)
    Path(args.out).write_text(render_markdown(counts, entries, args.config, args.attack_class, args.replay), encoding="utf-8")
    print(f"Wrote {len(entries)} unique DEV misses to {args.out}")


if __name__ == "__main__":
    main()
