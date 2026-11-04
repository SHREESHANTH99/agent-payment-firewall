"""Regenerate persisted replay summaries without contacting the firewall or an LLM."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from .replay import ReplayEvaluator


def regenerate(replay: dict, source: str) -> dict:
    """Recompute configuration summaries from their stored raw observations."""
    regenerated = deepcopy(replay)
    evaluator = ReplayEvaluator()
    configurations = regenerated.get("configurations") or {}
    if not configurations:
        raise ValueError("replay has no configurations to regenerate")
    for name, configuration in configurations.items():
        runs = configuration.get("runs")
        if not isinstance(runs, list):
            raise ValueError(f"replay configuration {name!r} has no stored raw observations")
        configurations[name] = evaluator._summarize_config(runs)

    metadata = regenerated.setdefault("metadata", {})
    metadata["regen_provenance"] = {
        "source_replay": source,
        "regenerated_at": datetime.now(timezone.utc).isoformat(),
        "summary_logic": "valid-observations-only-v1",
    }
    return regenerated


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate replay summaries offline from stored observations.")
    parser.add_argument("--replay", required=True, help="Existing replay JSON with raw configuration runs")
    parser.add_argument("--out", required=True, help="New output path; the input is never modified")
    args = parser.parse_args()
    source = Path(args.replay)
    destination = Path(args.out)
    if source.resolve() == destination.resolve():
        raise SystemExit("--out must differ from --replay; regeneration never overwrites the source")
    replay = json.loads(source.read_text(encoding="utf-8"))
    regenerated = regenerate(replay, str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(regenerated, indent=2), encoding="utf-8")
    print(f"Regenerated replay summaries to {destination}")


if __name__ == "__main__":
    main()
