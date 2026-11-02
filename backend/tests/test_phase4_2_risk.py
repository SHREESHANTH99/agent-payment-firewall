import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from demo.eval.metrics import choose_threshold, cluster_bootstrap_interval, normalized_intent_key, threshold_sweep
from app.core.config import settings
from app.risk.judge import judge, map_judge_verdict, JudgeResult
from app.services.llm import llm_client
from demo.eval.scenarios import load_scenarios
from demo.eval.sweep import render_table


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

