"""Tests for SQLAlchemy database model definitions."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.models import Mandate, PaymentIntent, AuditLog, PaymentIntentStatus


def test_mandate_model_instantiation():
    """Verify Mandate model attributes and default initialization."""
    now = datetime.now(timezone.utc)
    mandate = Mandate(
        mandate_id=str(uuid.uuid4()),
        agent_id="agent-007",
        budget_total=Decimal("500.00"),
        per_transaction_cap=Decimal("50.00"),
        allowlist_merchants=["github.com", "openai.com"],
        valid_from=now,
        valid_until=now,
        escalation_threshold=Decimal("25.00"),
        status="active",
    )
    assert mandate.agent_id == "agent-007"
    assert mandate.budget_total == Decimal("500.00")
    assert mandate.per_transaction_cap == Decimal("50.00")
    assert mandate.allowlist_merchants == ["github.com", "openai.com"]
    assert mandate.escalation_threshold == Decimal("25.00")
    assert mandate.status == "active"


def test_payment_intent_model_instantiation():
    """Verify PaymentIntent model attributes and default initialization."""
    intent_id = str(uuid.uuid4())
    mandate_id = str(uuid.uuid4())
    key = str(uuid.uuid4())
    intent = PaymentIntent(
        id=intent_id,
        mandate_id=mandate_id,
        idempotency_key=key,
        amount=Decimal("19.99"),
        currency="USD",
        merchant="openai.com",
        description="API credits",
        reasoning="Autonomous agent needs LLM API tokens",
        source_context={"task_id": "123"},
        status=PaymentIntentStatus.PENDING,
        risk_details={"risk_score": 0.1},
    )
    assert intent.id == intent_id
    assert intent.mandate_id == mandate_id
    assert intent.idempotency_key == key
    assert intent.amount == Decimal("19.99")
    assert intent.currency == "USD"
    assert intent.merchant == "openai.com"
    assert intent.status == PaymentIntentStatus.PENDING
    assert intent.risk_details == {"risk_score": 0.1}


def test_audit_log_model_instantiation():
    """Verify AuditLog model attributes and initialization."""
    log_id = str(uuid.uuid4())
    intent_id = str(uuid.uuid4())
    audit_log = AuditLog(
        id=log_id,
        intent_id=intent_id,
        event="intent.approved",
        payload={"approved_by": "firewall_rules"},
        prev_hash="0000000000000000000000000000000000000000000000000000000000000000",
        hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )
    assert audit_log.id == log_id
    assert audit_log.intent_id == intent_id
    assert audit_log.event == "intent.approved"
    assert audit_log.payload["approved_by"] == "firewall_rules"
    assert len(audit_log.hash) == 64
