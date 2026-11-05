import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from demo.eval.metrics import choose_threshold, cluster_bootstrap_interval, normalized_intent_key, threshold_sweep
from app.core.config import settings
from app.risk.judge import judge, map_judge_verdict, JudgeResult, _judge_client
from app.risk.canary import _canary_client
from app.services.llm import llm_client
from demo.eval.scenarios import load_scenarios
from demo.eval.sweep import choose_sweep_threshold, render_table
from demo.eval.replay import build_replay_pool
from demo.eval.report import render_combined_report
from demo.eval.provenance import build_metadata


def test_normalized_intent_key_deduplicates_formatting():
    a = normalized_intent_key("scenario", {"merchant": " Seller@Example.com ", "amount": "10.00", "description": "Paper   ream"})
    b = normalized_intent_key("SCENARIO", {"merchant": "seller@example.com", "amount": 10, "description": "paper ream"})
    assert a == b


def test_cluster_bootstrap_handles_scenario_clusters():
    rows = [{"scenario_id": "a", "stopped": True}, {"scenario_id": "a", "stopped": True}, {"scenario_id": "b", "stopped": False}]
    low, high = cluster_bootstrap_interval(rows, "stopped", samples=100, seed=1)
    assert 0 <= low <= high <= 1


def test_threshold_sweep_and_constraint_selection():
    records = [
        {"label": "malicious", "safe": False, "confidence": .9},
        {"label": "benign", "safe": True, "confidence": .9},
        {"label": "benign", "safe": True, "confidence": .6},
    ]
    table = threshold_sweep(records, [.5, .8])
    assert table[0]["benign_auto_approve_rate"] == 1.0
    assert choose_threshold(table, .7)["threshold"] == .5


@pytest.mark.asyncio
async def test_judge_prompt_has_labeled_principal_request(monkeypatch):
    captured = {}
    async def fake_complete(**kwargs):
        captured.update(kwargs)
        return {"safe": True, "confidence": .9, "injection_suspected": False, "reasons": [], "mismatch_reasons": []}
    monkeypatch.setattr(llm_client, "complete_json", fake_complete)
    await judge({}, {"user_task": "Buy printer paper", "merchant": "seller@example.com"}, "untrusted page")
    assert "<principal_request>\nBuy printer paper\n</principal_request>" in captured["user"]
    assert "<untrusted_content>" in captured["user"]
    assert "submitted payment fields as the action under review" in captured["system"]
    assert "Allowlist membership means a payee is PERMITTED" in captured["system"]
    assert "ALLOWLIST VS PRINCIPAL INTENT SEMANTICS" in captured["system"]


@pytest.mark.asyncio
async def test_judge_result_records_prompt_version(monkeypatch):
    from app.risk.judge import PROMPT_VERSION
    async def fake_complete(**kwargs):
        return {"safe": True, "confidence": .9, "injection_suspected": False, "reasons": [], "mismatch_reasons": []}
    monkeypatch.setattr(llm_client, "complete_json", fake_complete)
    result, verdict = await judge({}, {"user_task": "task", "merchant": "seller@example.com"})
    assert result.meta.get("prompt_version") == PROMPT_VERSION
    assert PROMPT_VERSION == "2026.11.05.v2"



@pytest.mark.asyncio
async def test_judge_failure_is_marked_for_exclusion(monkeypatch):
    from app.services.llm import LLMError
    async def fail(**kwargs):
        raise LLMError("mock failure")
    monkeypatch.setattr(llm_client, "complete_json", fail)
    result, verdict = await judge({}, {})
    assert result.meta["llm_error"] is True
    assert result.meta["fail_mode_applied"] is True
    assert verdict in {"deny", "escalate"}


def test_per_layer_provider_settings_override_shared_client(monkeypatch):
    monkeypatch.setattr(settings, "JUDGE_LLM_BASE_URL", "https://judge.invalid/v1")
    monkeypatch.setattr(settings, "JUDGE_LLM_API_KEY", "test-only")
    monkeypatch.setattr(settings, "JUDGE_LLM_MODEL", "judge-test")
    judge_client, judge_model = _judge_client()
    assert judge_client.base_url == "https://judge.invalid/v1"
    assert judge_model == "judge-test"
    monkeypatch.setattr(settings, "CANARY_LLM_BASE_URL", "https://canary.invalid/v1")
    monkeypatch.setattr(settings, "CANARY_LLM_API_KEY", "test-only")
    monkeypatch.setattr(settings, "CANARY_LLM_MODEL", "canary-test")
    canary_client, canary_model = _canary_client()
    assert canary_client.base_url == "https://canary.invalid/v1"
    assert canary_model == "canary-test"


def test_scenario_splits_cover_every_attack_variant():
    scenarios = load_scenarios("all")
    assert all(s.get("split") in {"dev", "test"} for s in scenarios)
    variants = {}
    for scenario in scenarios:
        if scenario["attack_class"] != "none":
            variants.setdefault(scenario["variant"], set()).add(scenario["split"])
    assert all(splits == {"dev", "test"} for splits in variants.values())


def test_tuning_loader_rejects_test_split():
    with pytest.raises(ValueError, match="DEV"):
        load_scenarios("test", purpose="tuning")


def test_sweep_no_feasible_threshold_is_explicit():
    rows = [{"threshold": .5, "malicious_detection_rate": 1., "benign_auto_approve_rate": .2, "benign_escalation_rate": .8, "benign_denial_rate": 0.}]
    assert "No threshold satisfies" in render_table(rows, None, .7, "fixture.json", 1)


def test_flat_sweep_keeps_default_threshold():
    rows = [
        {"threshold": .5, "malicious_detection_rate": .2, "benign_auto_approve_rate": .9},
        {"threshold": .8, "malicious_detection_rate": .2, "benign_auto_approve_rate": .9},
    ]
    assert choose_sweep_threshold(rows, .7)["threshold"] == .8


def test_combined_report_renders_replay_causes():
    replay = {"configurations": {"both": {"sample_sizes": {"unique_intents": 1, "observations": 3}, "per_intent_consistency": {"consistent_unique_intents": 1, "unique_intents": 1}, "latency": {}, "in_policy": {"auto_denied": 1, "denial_causes": {"judge": 1}, "escalated": 0, "escalation_causes": {}, "approved": 2, "denied": 1, "would_have_moved_money": 2, "llm_errors": 0, "llm_fallbacks": 0, "detection_rate": 1/3, "ci_95": [0, 1], "cluster_bootstrap_ci_95": [0, 1]}}}}
    with pytest.raises(ValueError, match="regenerate"):
        render_combined_report({"metadata": {}, "aggregated": {}, "runs": []}, replay)


def test_provenance_has_required_fields():
    metadata = build_metadata(split="dev", execution_mode="dry_run", models={}, thresholds={}, repeats=3, llm_cache_enabled=False, n_unique_intents=1, n_scenarios=1, unreportable=False)
    assert {"split", "git_commit_sha", "execution_mode", "models", "thresholds", "repeats", "llm_cache_enabled", "n_unique_intents", "n_scenarios", "generated_at", "unreportable"} <= metadata.keys()


def test_replay_pool_uses_valid_off_intents_and_source_class():
    live = {
        "metadata": {"split": "dev"},
        "runs": [
            {"status": "valid", "mode": "off", "scenario_id": "attack_one", "attack_class": "in_policy", "agent_compromised": True, "submitted_intents": [{"request": {"merchant": "seller@example.com"}}]},
            {"status": "incomplete", "mode": "off", "scenario_id": "ignored", "submitted_intents": [{"request": {}}]},
            {"status": "valid", "mode": "on", "scenario_id": "ignored", "submitted_intents": [{"request": {}}]},
        ],
    }
    pool = build_replay_pool(live, "dev")
    assert len(pool) == 1
    assert pool[0]["attack_class"] == "in_policy"
    assert pool[0]["scenario_id"] == "attack_one"

