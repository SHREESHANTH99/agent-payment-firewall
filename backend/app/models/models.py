"""SQLAlchemy database models for agent mandates, payment intents, and audit logs."""
import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    event as sa_event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.core.database import Base


# Use JSONB on PostgreSQL if available, JSON otherwise
JSONType = JSON().with_variant(JSONB, "postgresql")


class MandatePeriod(str, enum.Enum):
    """Spending budget period type for a mandate."""
    LIFETIME = "lifetime"
    DAILY = "daily"
    WEEKLY = "weekly"


class MandateStatus(str, enum.Enum):
    """Lifecycle status of a mandate."""
    ACTIVE = "active"
    FROZEN = "frozen"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PaymentIntentStatus(str, enum.Enum):
    """Status lifecycle of a payment intent."""
    PENDING = "pending"
    DENIED = "denied"
    ESCALATED = "escalated"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


def generate_uuid() -> str:
    """Generate a UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Generate a timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Mandate(Base):
    """Spending mandate defining constraints and limits for an autonomous agent."""
    __tablename__ = "mandates"

    mandate_id = Column(String(64), primary_key=True, default=generate_uuid)
    agent_id = Column(String(255), nullable=False, index=True)
    budget_total = Column(BigInteger, nullable=False)  # stored in integer cents
    per_transaction_cap = Column(BigInteger, nullable=False)  # stored in integer cents
    allowlist_merchants = Column(JSONType, nullable=False, default=list)  # list of emails/merchants
    allowed_currencies = Column(JSONType, nullable=False, default=lambda: ["USD"])
    period = Column(String(20), nullable=False, default="lifetime")  # lifetime | daily | weekly
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    escalation_threshold = Column(BigInteger, nullable=True)  # stored in integer cents
    status = Column(String(50), nullable=False, default="active")  # active | frozen | revoked | expired
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class PaymentIntent(Base):
    """Intercepted agent payment intent awaiting policy checks or execution."""
    __tablename__ = "payment_intents"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    mandate_id = Column(String(64), ForeignKey("mandates.mandate_id", ondelete="SET NULL"), nullable=True, index=True)
    idempotency_key = Column(String(255), unique=True, index=True, nullable=False)
    amount = Column(BigInteger, nullable=False)  # stored in integer cents
    currency = Column(String(10), nullable=False, default="USD")
    merchant = Column(String(255), nullable=False)  # PayPal recipient email
    description = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    source_context = Column(JSONType, nullable=True)
    status = Column(
        SQLEnum(PaymentIntentStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=PaymentIntentStatus.PENDING,
    )
    risk_details = Column(JSONType, nullable=True, default=dict)
    paypal_ref = Column(String(255), nullable=True)
    decision_reasons = Column(JSONType, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AuditLog(Base):
    """Cryptographically chained immutable audit log of payment events."""
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    intent_id = Column(String(64), ForeignKey("payment_intents.id", ondelete="SET NULL"), nullable=True, index=True)
    event = Column(String(255), nullable=False)
    payload = Column(JSONType, nullable=False, default=dict)
    prev_hash = Column(String(64), nullable=True)
    hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


@sa_event.listens_for(AuditLog, "before_update")
def receive_before_update(mapper, connection, target):
    raise ValueError("AuditLog entries are immutable and cannot be updated")


@sa_event.listens_for(AuditLog, "before_delete")
def receive_before_delete(mapper, connection, target):
    raise ValueError("AuditLog entries are immutable and cannot be deleted")


class WebhookEvent(Base):
    """Incoming verified PayPal webhook event for asynchronous handling and idempotency."""
    __tablename__ = "webhook_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(255), nullable=False)
    resource = Column(JSONType, nullable=False, default=dict)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    processed = Column(Boolean, nullable=False, default=False)

