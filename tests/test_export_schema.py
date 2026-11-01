"""Unit test for Phase 4 Part 5: JSON Schema compliance of exported dashboard data."""
import os
import sys
import pytest

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from scripts.export_eval import transform_eval_data


def test_export_schema_complete():
    sample_eval = {
        "metadata": {
            "date": "2026-11-01",
            "execution_mode": "dry_run",
            "agent_model": "llama-3.3-70b-versatile",
            "canary_model": "gemini-3.5-flash",
            "judge_model": "gemini-3.5-flash",
        },
        "aggregated": {
            "total_runs": 10,
            "variants": {
                "hidden_dom": {
                    "runs": 2,
                    "compromised": 2,
                    "blocked_by": {"rules": 2, "canary": 0, "judge": 0, "human": 0, "none": 0},
                },
                "reroute_inpolicy": {
                    "runs": 2,
                    "compromised": 2,
                    "blocked_by": {"rules": 0, "canary": 0, "judge": 2, "human": 0, "none": 0},
                },
            },
            "benign": {
                "runs": 6,
                "false_positives": 0,
                "escalations": 1,
            },
            "avg_risk_latency_ms": 142.5,
            "total_llm_calls": 24,
        },
        "runs": [
            {"variant": "hidden_dom", "attack_class": "out_of_policy", "would_have_executed": False},
            {"variant": "hidden_dom", "attack_class": "out_of_policy", "would_have_executed": False},
            {"variant": "reroute_inpolicy", "attack_class": "in_policy", "would_have_executed": False},
            {"variant": "reroute_inpolicy", "attack_class": "in_policy", "would_have_executed": False},
        ],
    }

    sample_calibration = {
        "metrics": {
            "overall_detection_rates": {
                "canary_alone": 0.85,
                "judge_alone": 0.95,
                "combined_defense": 1.0,
            }
        }
    }

    exported = transform_eval_data(sample_eval, sample_calibration)

    # 1. Top-level keys verification
    assert "generated_at" in exported
    assert exported["generated_at"] == "2026-11-01"

    assert "models" in exported
    assert exported["models"]["agent"] == "llama-3.3-70b-versatile"
    assert exported["models"]["canary"] == "gemini-3.5-flash"
    assert exported["models"]["judge"] == "gemini-3.5-flash"

    assert exported["execution_mode"] == "dry_run"

    assert "sample_sizes" in exported
    assert exported["sample_sizes"]["total_runs"] == 10
    assert exported["sample_sizes"]["attack_runs"] == 4
    assert exported["sample_sizes"]["benign_runs"] == 6

    # 2. Attack categories verification
    assert "attack_categories" in exported
    assert len(exported["attack_categories"]) == 2
    for cat in exported["attack_categories"]:
        assert "name" in cat
        assert "attack_class" in cat
        assert "runs" in cat
        assert "agent_compromised" in cat
        assert "blocked_by" in cat
        assert "money_would_have_moved" in cat
        assert isinstance(cat["blocked_by"], dict)

    # 3. Benign verification
    assert "benign" in exported
    assert exported["benign"]["runs"] == 6
    assert exported["benign"]["false_positives"] == 0
    assert exported["benign"]["escalations"] == 1

    # 4. Layers verification
    assert "layers" in exported
    assert exported["layers"]["canary_alone"] == 0.85
    assert exported["layers"]["judge_alone"] == 0.95
    assert exported["layers"]["combined"] == 1.0

    # 5. Metrics & latency
    assert exported["avg_added_latency_ms"] == 142.5
    assert exported["llm_calls"] == 24


def test_export_schema_omits_missing_keys():
    """Verify rule: Do not invent, round up, or backfill values; omit keys that are missing."""
    sparse_eval = {
        "metadata": {},
        "aggregated": {},
        "runs": [],
    }

    exported = transform_eval_data(sparse_eval, None)

    # Missing models, latency, layers, attack_categories must be omitted, not fabricated
    assert "models" not in exported
    assert "avg_added_latency_ms" not in exported
    assert "layers" not in exported
    assert "attack_categories" not in exported
    assert "llm_calls" not in exported
