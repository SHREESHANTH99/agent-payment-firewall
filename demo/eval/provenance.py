"""Shared, non-secret provenance for live and replay evaluation artifacts."""
from datetime import datetime, timezone
import subprocess
from typing import Any


def git_commit_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def build_metadata(*, split: str, execution_mode: str, models: dict[str, Any], thresholds: dict[str, Any], repeats: int, llm_cache_enabled: bool, n_unique_intents: int, n_scenarios: int, unreportable: bool) -> dict[str, Any]:
    return {"split": split, "git_commit_sha": git_commit_sha(), "execution_mode": execution_mode, "models": models, "thresholds": thresholds, "repeats": repeats, "llm_cache_enabled": llm_cache_enabled, "n_unique_intents": n_unique_intents, "n_scenarios": n_scenarios, "generated_at": datetime.now(timezone.utc).isoformat(), "unreportable": unreportable}
