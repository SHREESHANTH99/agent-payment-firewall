"""Scenario loading with explicit DEV/TEST separation."""
from pathlib import Path
from typing import Any
import yaml


def load_scenarios(split: str, purpose: str = "evaluation", path: str = "demo/eval/scenarios.yaml") -> list[dict[str, Any]]:
    if split not in {"dev", "test", "all"}:
        raise ValueError("split must be dev, test, or all")
    if purpose == "tuning" and split != "dev":
        raise ValueError("tuning may load DEV scenarios only")
    scenario_path = Path(path)
    if not scenario_path.exists() and not scenario_path.is_absolute():
        scenario_path = Path(__file__).with_name("scenarios.yaml")
    with open(scenario_path, encoding="utf-8") as handle:
        scenarios = yaml.safe_load(handle).get("scenarios", [])
    if any(s.get("split") not in {"dev", "test"} for s in scenarios):
        raise ValueError("every scenario must declare split: dev or test")
    return scenarios if split == "all" else [s for s in scenarios if s["split"] == split]
