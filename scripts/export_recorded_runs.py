"""Export sanitized agent transcripts for the Judge Playground offline fallback."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "results" / "transcripts"
OUTPUT = ROOT / "dashboard" / "public" / "data" / "recorded_runs.json"
SECRET_KEYS = re.compile(r"(api[_-]?key|token|secret|authorization|password)", re.IGNORECASE)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SECRET_KEYS.search(str(key)) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def export() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in sorted(TRANSCRIPTS.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            transcript = sanitize(json.load(file))
        transcript["id"] = path.stem
        transcript["label"] = "recorded"
        transcript["risk_details"] = [
            event.get("result", {}).get("risk", {})
            for event in transcript.get("tool_calls", [])
            if isinstance(event, dict) and isinstance(event.get("result"), dict)
        ]
        runs.append(transcript)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(runs, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return runs


if __name__ == "__main__":
    print(f"Exported {len(export())} recorded runs")
