"""Synthetic, offline tests for replay metric population invariants."""
import pytest

from demo.eval.metrics import (
    assert_metric_invariants,
    cluster_bootstrap_interval,
    threshold_sweep,
    valid_observation_summary,
)
from demo.eval.replay import ReplayEvaluator


def observation(*, scenario="s1", decision="approved", llm_error=False, fail_mode=False):
    risk = {"canary": {}, "judge": {}}
    if llm_error:
        risk["judge"] = {"llm_error": True}
    if fail_mode:
        risk["denial_cause"] = "llm_error_fail_mode"
    return {
        "scenario_id": scenario,
        "decision": decision,
        "final_decision": decision,
        "risk_details": risk,
        "intent_request": {"merchant": "seller@example.com", "amount": "1.00", "description": scenario},
    }


def test_fail_mode_observations_are_excluded_from_every_detection_population():
    records = [observation(decision="denied"), observation(decision="denied", llm_error=True, fail_mode=True)]
    summary = valid_observation_summary(records)
    assert summary["n_total"] == 2
    assert summary["n_valid"] == 1
    assert summary["n_excluded"] == 1
    assert summary["numerator"] == 1
    assert summary["denominator"] == 1
    assert "llm_error:judge" in summary["exclusion_reasons"]
    assert "llm_error_fail_mode" in summary["exclusion_reasons"]


def test_intervals_include_point_for_empty_zero_and_all_detection_clusters():
    for records, expected in [
        ([observation(llm_error=True, fail_mode=True)], 0.0),
        ([observation(scenario="a"), observation(scenario="b")], 0.0),
        ([observation(scenario="a", decision="denied"), observation(scenario="b", decision="escalated")], 1.0),
    ]:
        summary = valid_observation_summary(records)
        assert summary["detection_rate"] == expected
        assert summary["ci_95"][0] <= expected <= summary["ci_95"][1]
        assert summary["cluster_bootstrap_ci_95"][0] <= expected <= summary["cluster_bootstrap_ci_95"][1]


def test_bootstrap_uses_only_valid_observations_with_uneven_clusters():
    records = [
        observation(scenario="large", decision="denied"),
        observation(scenario="large"),
        observation(scenario="large", llm_error=True, fail_mode=True),
        observation(scenario="small", decision="denied"),
    ]
    summary = valid_observation_summary(records)
    assert summary["n_valid"] == 3
    assert summary["numerator"] == 2
    assert summary["cluster_bootstrap_ci_95"][0] <= summary["detection_rate"] <= summary["cluster_bootstrap_ci_95"][1]


def test_sweep_excludes_fail_modes_and_reports_population_counts():
    records = [
        {**observation(decision="denied"), "label": "malicious", "safe": False, "confidence": 0.9},
        {**observation(llm_error=True, fail_mode=True), "label": "malicious", "safe": False, "confidence": 0.9},
        {**observation(scenario="b"), "label": "benign", "safe": True, "confidence": 0.95},
    ]
    row = threshold_sweep(records, [0.8])[0]
    assert row["n_total"] == 3
    assert row["n_valid"] == 2
    assert row["n_excluded"] == 1
    assert row["malicious_detection_rate"] == 1.0


def test_replay_summary_uses_same_valid_denominator_for_rate_and_bootstrap():
    runs = [
        {**observation(decision="denied"), "attack_class": "in_policy", "blocked_by": "judge", "would_have_executed": False},
        {**observation(llm_error=True, fail_mode=True), "attack_class": "in_policy", "blocked_by": "judge", "would_have_executed": False},
    ]
    summary = ReplayEvaluator._summarize_config(None, runs)["in_policy"]
    assert summary["n_total"] == 2
    assert summary["n_valid"] == 1
    assert summary["denominator"] == 1
    assert summary["numerator"] == 1
    assert summary["detection_rate"] == 1.0
    assert summary["cluster_bootstrap_ci_95"] == [1.0, 1.0]


def test_metric_invariant_rejects_impossible_rate_interval():
    with pytest.raises(ValueError, match="must contain"):
        assert_metric_invariants(
            {"numerator": 1, "denominator": 2, "detection_rate": 0.5, "ci_95": [0.0, 0.4], "cluster_bootstrap_ci_95": [0.0, 1.0]},
            [],
        )
