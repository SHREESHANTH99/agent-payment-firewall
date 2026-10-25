"""Unit tests for calibration script aggregation math and markdown generation."""
import pytest
from scripts.calibrate_risk import calculate_metrics, generate_markdown_report


def test_calculate_metrics_perfect_detection_zero_fp():
    """Metrics calculation when all injections are detected and no benign false positives."""
    benign_results = [
        {
            "id": "b1",
            "category": "catalog",
            "runs": [
                {"canary_tripped": False, "judge_safe": True, "judge_verdict": "allow"},
                {"canary_tripped": False, "judge_safe": True, "judge_verdict": "allow"},
            ],
        }
    ]
    injection_results = [
        {
            "id": "i1",
            "category": "blunt_override",
            "runs": [
                {"canary_tripped": True, "judge_safe": False, "judge_verdict": "deny"},
                {"canary_tripped": False, "judge_safe": False, "judge_verdict": "deny"},
            ],
        }
    ]

    metrics = calculate_metrics(benign_results, injection_results, repeats=2)

    assert metrics["sample_sizes"]["total_benign_evaluations"] == 2
    assert metrics["sample_sizes"]["total_injection_evaluations"] == 2
    assert metrics["false_positive_rates"]["canary"] == 0.0
    assert metrics["false_positive_rates"]["judge"] == 0.0
    assert metrics["false_positive_rates"]["combined"] == 0.0

    assert metrics["overall_detection_rates"]["canary_alone"] == 0.5  # 1 of 2
    assert metrics["overall_detection_rates"]["judge_alone"] == 1.0   # 2 of 2
    assert metrics["overall_detection_rates"]["combined_defense"] == 1.0  # 2 of 2

    assert "blunt_override" in metrics["category_breakdown"]
    assert metrics["category_breakdown"]["blunt_override"]["canary_rate"] == 0.5
    assert metrics["category_breakdown"]["blunt_override"]["judge_rate"] == 1.0
    assert metrics["category_breakdown"]["blunt_override"]["combined_rate"] == 1.0


def test_calculate_metrics_partial_detection_with_fp():
    """Metrics calculation with false positive and partial catch."""
    benign_results = [
        {
            "id": "b1",
            "category": "catalog",
            "runs": [
                {"canary_tripped": True, "judge_safe": True, "judge_verdict": "allow"},  # Canary FP
                {"canary_tripped": False, "judge_safe": True, "judge_verdict": "allow"},
            ],
        }
    ]
    injection_results = [
        {
            "id": "i1",
            "category": "fake_invoice",
            "runs": [
                {"canary_tripped": False, "judge_safe": True, "judge_verdict": "allow"},  # Both missed
                {"canary_tripped": True, "judge_safe": True, "judge_verdict": "allow"},   # Canary caught
            ],
        }
    ]

    metrics = calculate_metrics(benign_results, injection_results, repeats=2)
    assert metrics["false_positive_rates"]["canary"] == 0.5
    assert metrics["false_positive_rates"]["judge"] == 0.0
    assert metrics["false_positive_rates"]["combined"] == 0.5

    assert metrics["overall_detection_rates"]["canary_alone"] == 0.5
    assert metrics["overall_detection_rates"]["judge_alone"] == 0.0
    assert metrics["overall_detection_rates"]["combined_defense"] == 0.5


def test_generate_markdown_report_formatting():
    """Markdown report includes model names, table headers, and key metrics."""
    metrics = {
        "sample_sizes": {
            "benign_cases": 15,
            "injection_cases": 20,
            "repeats": 3,
            "total_benign_evaluations": 45,
            "total_injection_evaluations": 60,
        },
        "false_positive_rates": {
            "canary": 0.0,
            "judge": 0.02,
            "combined": 0.02,
        },
        "overall_detection_rates": {
            "canary_alone": 0.75,
            "judge_alone": 0.85,
            "combined_defense": 0.95,
        },
        "category_breakdown": {
            "blunt_override": {"runs": 3, "canary_rate": 1.0, "judge_rate": 1.0, "combined_rate": 1.0},
        },
        "operational_metrics": {
            "total_evaluations": 105,
            "average_latency_ms": 120.5,
            "fallback_calls": 0,
            "errors": 0,
        },
    }

    report = generate_markdown_report(metrics, "test-canary-model", "test-judge-model")
    assert "# Risk Layer Detection & Calibration Report" in report
    assert "`test-canary-model`" in report
    assert "`test-judge-model`" in report
    assert "95.0%" in report
    assert "`blunt_override`" in report
