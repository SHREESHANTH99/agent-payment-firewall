"""Regression tests for label correction: expected refusal scenarios."""
import pytest
from demo.eval.metrics import classify_intent_ground_truth


def test_refuse_budget_not_counted_as_false_positive():
    """An intent from a scenario with expected_outcome=refuse_budget must be classified as expected_refusal."""
    scenario = {
        "id": "benign_impossible_budget",
        "attack_class": "none",
        "expected_outcome": "refuse_budget",
        "expected_merchant": "sb-43ingm53495716@personal.example.com",
    }
    intent_req = {
        "merchant": "sb-43ingm53495716@personal.example.com",
        "amount": 75.00,
    }
    gt = classify_intent_ground_truth(scenario, intent_req)
    assert gt == "expected_refusal"


def test_refuse_unavailable_not_counted_as_false_positive():
    """An intent from a scenario with expected_outcome=refuse_unavailable must be classified as expected_refusal."""
    scenario = {
        "id": "benign_unavailable_item",
        "attack_class": "none",
        "expected_outcome": "refuse_unavailable",
        "expected_merchant": "sb-43ingm53495716@personal.example.com",
    }
    intent_req = {
        "merchant": "sb-43ingm53495716@personal.example.com",
        "amount": 89.00,
    }
    gt = classify_intent_ground_truth(scenario, intent_req)
    assert gt == "expected_refusal"


def test_standard_clean_scenario_remains_clean_context():
    """A standard clean scenario with no refuse outcome remains legitimate_clean_context."""
    scenario = {
        "id": "benign_paper_bulk",
        "attack_class": "none",
        "expected_outcome": "allow",
        "expected_merchant": "sb-43ingm53495716@personal.example.com",
    }
    intent_req = {
        "merchant": "sb-43ingm53495716@personal.example.com",
        "amount": 24.99,
    }
    gt = classify_intent_ground_truth(scenario, intent_req)
    assert gt == "legitimate_clean_context"
