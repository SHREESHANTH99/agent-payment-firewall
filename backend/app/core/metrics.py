"""Prometheus metrics collectors and registries for Agent Payment Firewall."""
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Dedicated Prometheus registry
metrics_registry = CollectorRegistry(auto_describe=True)

# 1. Intent counters
INTENT_DECISIONS_TOTAL = Counter(
    "apf_intent_decisions_total",
    "Total payment intents processed, partitioned by decision and stopping layer.",
    ["decision", "stopping_layer"],
    registry=metrics_registry,
)

# 2. Risk check verdicts
RISK_CHECKS_TOTAL = Counter(
    "apf_risk_checks_total",
    "Total risk checks performed by layer and verdict.",
    ["layer", "verdict"],
    registry=metrics_registry,
)

# 3. Circuit breaker trips
CIRCUIT_BREAKER_TRIPS_TOTAL = Counter(
    "apf_circuit_breaker_trips_total",
    "Total times the mandate circuit breaker or auto-freeze was tripped.",
    ["trigger"],
    registry=metrics_registry,
)

# 4. Webhook events
WEBHOOK_EVENTS_TOTAL = Counter(
    "apf_webhook_events_total",
    "Total incoming PayPal webhook events by event_type and verification result.",
    ["event_type", "verification"],
    registry=metrics_registry,
)

# 5. LLM calls
LLM_CALLS_TOTAL = Counter(
    "apf_llm_calls_total",
    "Total LLM inferences consumed by layer, model, and outcome.",
    ["layer", "model", "outcome"],
    registry=metrics_registry,
)

# 6. Histograms for latency
PIPELINE_LATENCY_SECONDS = Histogram(
    "apf_pipeline_latency_seconds",
    "End-to-end processing latency for payment intents.",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=metrics_registry,
)

LLM_LATENCY_SECONDS = Histogram(
    "apf_llm_latency_seconds",
    "Inference latency for risk evaluation LLM calls.",
    ["layer", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0),
    registry=metrics_registry,
)

# 7. Gauges
ESCALATED_PENDING_GAUGE = Gauge(
    "apf_escalated_intents_pending",
    "Current number of intents held in pending escalation status.",
    registry=metrics_registry,
)

FROZEN_MANDATES_GAUGE = Gauge(
    "apf_frozen_mandates_count",
    "Current number of frozen mandates.",
    registry=metrics_registry,
)


def export_metrics() -> tuple[bytes, str]:
    """Generate Prometheus exposition text and appropriate media content type."""
    return generate_latest(metrics_registry), CONTENT_TYPE_LATEST
