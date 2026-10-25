"""API endpoints for payment intents: creation (agents) and management (operators)."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import agent_auth, operator_auth
from app.models.models import AuditLog, Mandate, MandateStatus, PaymentIntent, PaymentIntentStatus
from app.services.audit import append_event
from app.services.budget import budget_service
from app.services.execution import execute_intent
from app.services.pipeline import process_intent

router = APIRouter(prefix="/intents", tags=["intents"])


class IntentCreateRequest(BaseModel):
    idempotency_key: str
    mandate_id: str
    amount: Union[int, float, str, Decimal]
    currency: str = "USD"
    merchant: str
    description: Optional[str] = None
    reasoning: Optional[str] = Field(default=None, max_length=4000)
    source_context: Optional[str] = Field(default=None, max_length=50000)


class IntentDecisionResponse(BaseModel):
    intent_id: str
    decision: str
    status: str
    reasons: list[Any] = Field(default_factory=list)
    risk: dict[str, Any] = Field(default_factory=dict)


class IntentSummaryResponse(BaseModel):
    id: str
    mandate_id: Optional[str] = None
    idempotency_key: str
    amount: int
    currency: str
    merchant: str
    description: Optional[str] = None
    status: str
    decision_reasons: Optional[list[Any]] = None
    created_at: str
    updated_at: str


class IntentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mandate_id: Optional[str] = None
    idempotency_key: str
    amount: int
    currency: str
    merchant: str
    description: Optional[str] = None
    reasoning: Optional[str] = None
    status: str
    decision_reasons: Optional[list[Any]] = None
    risk_details: Optional[dict[str, Any]] = None
    paypal_ref: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedIntentsResponse(BaseModel):
    items: list[IntentSummaryResponse]
    total: int
    page: int
    page_size: int


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class StatsResponse(BaseModel):
    by_status: dict[str, int]
    total_spent_cents: int
    total_reserved_cents: int
    total_remaining_cents: int
    escalations_pending: int
    frozen_mandates: int
    last_24h_decisions: dict[str, int]


@router.post("", response_model=IntentDecisionResponse, status_code=status.HTTP_200_OK)
async def create_intent(
    body: IntentCreateRequest,
    agent_id: str = Depends(agent_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Submit a payment intent for processing (Agent-authenticated)."""
    request_data = body.model_dump()
    return await process_intent(agent_id=agent_id, request_data=request_data, session=db)


@router.get("", response_model=PaginatedIntentsResponse)
async def list_intents(
    mandate_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> PaginatedIntentsResponse:
    """List payment intents with filters, sort, and pagination (Operator-only)."""
    stmt = select(PaymentIntent)

    if mandate_id:
        stmt = stmt.where(PaymentIntent.mandate_id == mandate_id)
    if status_filter:
        try:
            status_enum = PaymentIntentStatus(status_filter)
            stmt = stmt.where(PaymentIntent.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}",
            )
    if date_from:
        stmt = stmt.where(PaymentIntent.created_at >= date_from)
    if date_to:
        stmt = stmt.where(PaymentIntent.created_at <= date_to)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Sort
    sort_col = getattr(PaymentIntent, sort, PaymentIntent.created_at)
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = (await db.execute(stmt)).scalars().all()

    items = [
        IntentSummaryResponse(
            id=r.id,
            mandate_id=r.mandate_id,
            idempotency_key=r.idempotency_key,
            amount=r.amount,
            currency=r.currency,
            merchant=r.merchant,
            description=r.description,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            decision_reasons=r.decision_reasons,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )
        for r in rows
    ]

    return PaginatedIntentsResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> StatsResponse:
    """Get aggregated firewall statistics (Operator-only)."""
    from datetime import timedelta, timezone as tz

    # Status counts
    by_status: dict[str, int] = {}
    for s in PaymentIntentStatus:
        count_stmt = select(func.count()).where(PaymentIntent.status == s)
        count = (await db.execute(count_stmt)).scalar_one()
        by_status[s.value] = count

    # Budget summary across active mandates
    active_mandates_stmt = select(Mandate).where(Mandate.status == MandateStatus.ACTIVE)
    active_mandates = (await db.execute(active_mandates_stmt)).scalars().all()

    total_spent_cents = 0
    total_reserved_cents = 0
    total_remaining_cents = 0
    for mandate in active_mandates:
        period_key = budget_service.get_period_key(mandate.period)
        try:
            balances = await budget_service.get_balances(mandate.mandate_id, period_key)
            spent = balances["spent"]
            reserved = balances["reserved"]
        except Exception:
            spent, reserved = 0, 0
        budget_total = int(mandate.budget_total)
        total_spent_cents += spent
        total_reserved_cents += reserved
        total_remaining_cents += max(0, budget_total - spent - reserved)

    # Escalations pending
    escalations_stmt = select(func.count()).where(PaymentIntent.status == PaymentIntentStatus.ESCALATED)
    escalations_pending = (await db.execute(escalations_stmt)).scalar_one()

    # Frozen mandates
    frozen_stmt = select(func.count()).where(Mandate.status == MandateStatus.FROZEN)
    frozen_mandates = (await db.execute(frozen_stmt)).scalar_one()

    # Last 24h decisions
    from datetime import datetime
    cutoff = datetime.now(tz.utc).replace(tzinfo=None) - timedelta(hours=24)

    last_24h: dict[str, int] = {}
    for decision_status in [PaymentIntentStatus.APPROVED, PaymentIntentStatus.DENIED, PaymentIntentStatus.ESCALATED]:
        count_stmt = select(func.count()).where(
            PaymentIntent.status == decision_status,
            PaymentIntent.created_at >= cutoff,
        )
        count = (await db.execute(count_stmt)).scalar_one()
        last_24h[decision_status.value] = count

    return StatsResponse(
        by_status=by_status,
        total_spent_cents=total_spent_cents,
        total_reserved_cents=total_reserved_cents,
        total_remaining_cents=total_remaining_cents,
        escalations_pending=escalations_pending,
        frozen_mandates=frozen_mandates,
        last_24h_decisions=last_24h,
    )


@router.get("/{intent_id}", response_model=dict)
async def get_intent(
    intent_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> dict:
    """Get full intent detail including risk_details and audit events (Operator-only)."""
    stmt = select(PaymentIntent).where(PaymentIntent.id == intent_id)
    intent = (await db.execute(stmt)).scalar_one_or_none()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment intent '{intent_id}' not found",
        )

    # Fetch audit events for this intent
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.intent_id == intent_id)
        .order_by(AuditLog.created_at.asc())
    )
    audit_rows = (await db.execute(audit_stmt)).scalars().all()
    audit_events = [
        {
            "id": row.id,
            "event": row.event,
            "payload": row.payload,
            "hash": row.hash[:16] + "...",
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in audit_rows
    ]

    return {
        "id": intent.id,
        "mandate_id": intent.mandate_id,
        "idempotency_key": intent.idempotency_key,
        "amount": intent.amount,
        "currency": intent.currency,
        "merchant": intent.merchant,
        "description": intent.description,
        "reasoning": intent.reasoning,
        "status": intent.status.value if hasattr(intent.status, "value") else str(intent.status),
        "decision_reasons": intent.decision_reasons,
        "risk_details": intent.risk_details,
        "paypal_ref": intent.paypal_ref,
        "created_at": intent.created_at.isoformat() if intent.created_at else "",
        "updated_at": intent.updated_at.isoformat() if intent.updated_at else "",
        "audit_events": audit_events,
    }


@router.post("/{intent_id}/approve")
async def approve_intent(
    intent_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> dict:
    """Approve an escalated payment intent and execute payout (Operator-only)."""
    from app.services.events import event_publisher

    stmt = select(PaymentIntent).where(PaymentIntent.id == intent_id)
    intent = (await db.execute(stmt)).scalar_one_or_none()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment intent '{intent_id}' not found",
        )

    if intent.status != PaymentIntentStatus.ESCALATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve intent with status '{intent.status.value}'. Must be 'escalated'.",
        )

    old_status = intent.status.value
    intent.status = PaymentIntentStatus.APPROVED
    await db.commit()
    await db.refresh(intent)

    await budget_service.persist(intent.id)

    await append_event(
        db,
        intent_id=intent.id,
        event="intent.approved",
        payload={"approved_by": "operator"},
    )

    await event_publisher.publish("intent_status_changed", {
        "intent_id": intent.id,
        "old_status": old_status,
        "new_status": "approved",
        "amount": intent.amount,
        "merchant": intent.merchant,
    })

    await execute_intent(intent, db)
    await db.refresh(intent)

    return {
        "id": intent.id,
        "status": intent.status.value if hasattr(intent.status, "value") else str(intent.status),
        "decision_reasons": intent.decision_reasons,
        "paypal_ref": intent.paypal_ref,
    }


@router.post("/{intent_id}/reject")
async def reject_intent(
    intent_id: str,
    body: Optional[RejectRequest] = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> dict:
    """Reject an escalated payment intent and release budget (Operator-only)."""
    from app.services.events import event_publisher

    stmt = select(PaymentIntent).where(PaymentIntent.id == intent_id)
    intent = (await db.execute(stmt)).scalar_one_or_none()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment intent '{intent_id}' not found",
        )

    if intent.status != PaymentIntentStatus.ESCALATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject intent with status '{intent.status.value}'. Must be 'escalated'.",
        )

    await budget_service.release(intent.id)

    reason = body.reason if body and body.reason else "Operator rejected transaction"
    old_status = intent.status.value
    intent.status = PaymentIntentStatus.REJECTED
    intent.decision_reasons = (intent.decision_reasons or []) + [{"code": "OPERATOR_REJECTED", "message": reason}]
    await db.commit()
    await db.refresh(intent)

    await append_event(
        db,
        intent_id=intent.id,
        event="intent.rejected",
        payload={"rejected_by": "operator", "reason": reason},
    )

    await event_publisher.publish("intent_status_changed", {
        "intent_id": intent.id,
        "old_status": old_status,
        "new_status": "rejected",
        "amount": intent.amount,
        "merchant": intent.merchant,
    })

    return {
        "id": intent.id,
        "status": intent.status.value if hasattr(intent.status, "value") else str(intent.status),
        "decision_reasons": intent.decision_reasons,
    }
