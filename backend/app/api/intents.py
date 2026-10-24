"""API endpoints for payment intents: creation (agents) and management (operators)."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import agent_auth, operator_auth
from app.models.models import PaymentIntent, PaymentIntentStatus
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
    reasoning: Optional[str] = None
    source_context: Optional[dict[str, Any]] = None


class IntentDecisionResponse(BaseModel):
    intent_id: str
    decision: str
    status: str
    reasons: list[Any] = Field(default_factory=list)
    risk: dict[str, Any] = Field(default_factory=dict)


class IntentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mandate_id: Optional[str] = None
    idempotency_key: str
    amount: int  # in integer cents
    currency: str
    merchant: str
    description: Optional[str] = None
    reasoning: Optional[str] = None
    source_context: Optional[dict[str, Any]] = None
    status: str
    decision_reasons: Optional[list[Any]] = None
    risk_details: Optional[dict[str, Any]] = None
    paypal_ref: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RejectRequest(BaseModel):
    reason: Optional[str] = None


@router.post("", response_model=IntentDecisionResponse, status_code=status.HTTP_200_OK)
async def create_intent(
    body: IntentCreateRequest,
    agent_id: str = Depends(agent_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Submit a payment intent for processing (Agent-authenticated)."""
    # Convert body to dictionary for pipeline processing
    request_data = body.model_dump()
    return await process_intent(agent_id=agent_id, request_data=request_data, session=db)


@router.get("", response_model=list[IntentDetailResponse])
async def list_intents(
    mandate_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> list[PaymentIntent]:
    """List payment intents (Operator-only)."""
    stmt = select(PaymentIntent).order_by(PaymentIntent.created_at.desc()).offset(offset).limit(limit)
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

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{intent_id}", response_model=IntentDetailResponse)
async def get_intent(
    intent_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> PaymentIntent:
    """Get single payment intent by ID (Operator-only)."""
    stmt = select(PaymentIntent).where(PaymentIntent.id == intent_id)
    intent = (await db.execute(stmt)).scalar_one_or_none()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment intent '{intent_id}' not found",
        )
    return intent


@router.post("/{intent_id}/approve", response_model=IntentDetailResponse)
async def approve_intent(
    intent_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> PaymentIntent:
    """Approve an escalated payment intent and execute payout (Operator-only)."""
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

    intent.status = PaymentIntentStatus.APPROVED
    await db.commit()
    await db.refresh(intent)

    await append_event(
        db,
        intent_id=intent.id,
        event="intent.approved",
        payload={"approved_by": "operator"},
    )

    # Execute payout
    await execute_intent(intent, db)
    await db.refresh(intent)
    return intent


@router.post("/{intent_id}/reject", response_model=IntentDetailResponse)
async def reject_intent(
    intent_id: str,
    body: Optional[RejectRequest] = None,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> PaymentIntent:
    """Reject an escalated payment intent and release budget (Operator-only)."""
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

    # Release budget reservation
    await budget_service.release(intent.id)

    reason = body.reason if body and body.reason else "Operator rejected transaction"
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

    return intent
