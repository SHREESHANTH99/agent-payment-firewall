"""Agent API endpoints for autonomous agents."""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import agent_auth
from app.models.models import Mandate, MandateStatus
from app.services.budget import budget_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


def format_cents_to_decimal(cents: Optional[int]) -> Optional[str]:
    """Convert integer cents back to formatted 2-decimal string."""
    if cents is None:
        return None
    return f"{Decimal(cents) / 100:.2f}"


class AgentMandateSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mandate_id: str
    remaining: str
    per_transaction_cap: str
    escalation_threshold: Optional[str] = None
    allowed_currencies: list[str]
    allowlist_merchants: list[str]
    valid_until: datetime


@router.get("/mandate", response_model=AgentMandateSummaryResponse)
async def get_agent_mandate(
    agent_id: str = Depends(agent_auth),
    db: AsyncSession = Depends(get_db),
) -> AgentMandateSummaryResponse:
    """
    Retrieve the agent's most recent active mandate summary.
    Requires agent authentication via X-Agent-Key.
    Returns 404 if no active or valid mandate exists.
    """
    stmt = (
        select(Mandate)
        .where(
            Mandate.agent_id == agent_id,
            Mandate.status == MandateStatus.ACTIVE.value,
        )
        .order_by(Mandate.created_at.desc())
    )
    result = await db.execute(stmt)
    mandate = result.scalars().first()

    if not mandate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active mandate found for agent",
        )

    # Check expiration
    now = datetime.now(timezone.utc)
    valid_until = mandate.valid_until
    if valid_until.tzinfo is None:
        valid_until = valid_until.replace(tzinfo=timezone.utc)

    if valid_until < now:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mandate has expired",
        )

    # Calculate remaining balance from budget service
    try:
        period_key = budget_service.get_period_key(mandate.period)
        balances = await budget_service.get_balances(mandate.mandate_id, period_key)
        spent_cents = balances.get("spent", 0)
        reserved_cents = balances.get("reserved", 0)
    except Exception as exc:
        logger.warning("Could not fetch balances from budget service for mandate %s: %s", mandate.mandate_id, exc)
        spent_cents = 0
        reserved_cents = 0

    total_cents = int(mandate.budget_total)
    remaining_cents = max(0, total_cents - spent_cents - reserved_cents)

    return AgentMandateSummaryResponse(
        mandate_id=mandate.mandate_id,
        remaining=format_cents_to_decimal(remaining_cents) or "0.00",
        per_transaction_cap=format_cents_to_decimal(mandate.per_transaction_cap) or "0.00",
        escalation_threshold=format_cents_to_decimal(mandate.escalation_threshold),
        allowed_currencies=mandate.allowed_currencies or ["USD"],
        allowlist_merchants=mandate.allowlist_merchants or [],
        valid_until=valid_until,
    )
