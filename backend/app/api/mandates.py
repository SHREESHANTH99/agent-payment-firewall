"""Operator API endpoints for managing agent spending mandates."""
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import operator_auth
from app.models.models import Mandate, MandatePeriod, MandateStatus
from app.risk.rules import to_cents
from app.services.budget import budget_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mandates", tags=["mandates"])


def format_cents_to_decimal(cents: Optional[int]) -> Optional[str]:
    """Convert integer cents back to formatted 2-decimal string for API response."""
    if cents is None:
        return None
    return f"{Decimal(cents) / 100:.2f}"


class MandateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    agent_id: str
    budget_total: Union[str, float, Decimal, int]  # input in dollars e.g. 500.00
    per_transaction_cap: Union[str, float, Decimal, int]  # input in dollars e.g. 50.00
    allowlist_merchants: list[str]  # PayPal recipient emails
    allowed_currencies: list[str] = ["USD"]
    period: str = "lifetime"  # lifetime | daily | weekly
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    escalation_threshold: Optional[Union[str, float, Decimal, int]] = None

    @field_validator("budget_total", "per_transaction_cap", "escalation_threshold", mode="before")
    @classmethod
    def validate_decimal_precision(cls, v: Any) -> Any:
        if v is None:
            return None
        # Verify decimal precision does not exceed 2 places
        d = Decimal(str(v))
        if d.as_tuple().exponent < -2:
            raise ValueError(f"Amount '{v}' has more than 2 decimal places")
        return v


class MandatePatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    budget_total: Optional[Union[str, float, Decimal, int]] = None
    per_transaction_cap: Optional[Union[str, float, Decimal, int]] = None
    allowlist_merchants: Optional[list[str]] = None
    allowed_currencies: Optional[list[str]] = None
    period: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    escalation_threshold: Optional[Union[str, float, Decimal, int]] = None
    status: Optional[str] = None

    @field_validator("budget_total", "per_transaction_cap", "escalation_threshold", mode="before")
    @classmethod
    def validate_decimal_precision(cls, v: Any) -> Any:
        if v is None:
            return None
        d = Decimal(str(v))
        if d.as_tuple().exponent < -2:
            raise ValueError(f"Amount '{v}' has more than 2 decimal places")
        return v


class MandateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mandate_id: str
    agent_id: str
    budget_total: str  # Formatted dollar string e.g. "500.00"
    budget_total_cents: int
    per_transaction_cap: str
    per_transaction_cap_cents: int
    allowlist_merchants: list[str]
    allowed_currencies: list[str]
    period: str
    valid_from: datetime
    valid_until: datetime
    escalation_threshold: Optional[str] = None
    escalation_threshold_cents: Optional[int] = None
    status: str
    created_at: datetime
    # Budget balance fields populated by budget service
    remaining: str = "0.00"
    reserved: str = "0.00"
    spent: str = "0.00"
    remaining_cents: int = 0
    reserved_cents: int = 0
    spent_cents: int = 0


async def _enrich_mandate_response(mandate: Mandate) -> MandateResponse:
    """Enrich mandate with remaining, reserved, and spent from Redis budget service."""
    period_key = budget_service.get_period_key(mandate.period)
    balances = await budget_service.get_balances(mandate.mandate_id, period_key)
    spent_cents = balances["spent"]
    reserved_cents = balances["reserved"]
    total_cents = int(mandate.budget_total)
    remaining_cents = max(0, total_cents - spent_cents - reserved_cents)

    return MandateResponse(
        mandate_id=mandate.mandate_id,
        agent_id=mandate.agent_id,
        budget_total=format_cents_to_decimal(total_cents) or "0.00",
        budget_total_cents=total_cents,
        per_transaction_cap=format_cents_to_decimal(mandate.per_transaction_cap) or "0.00",
        per_transaction_cap_cents=int(mandate.per_transaction_cap),
        allowlist_merchants=mandate.allowlist_merchants or [],
        allowed_currencies=mandate.allowed_currencies or ["USD"],
        period=mandate.period,
        valid_from=mandate.valid_from,
        valid_until=mandate.valid_until,
        escalation_threshold=format_cents_to_decimal(mandate.escalation_threshold),
        escalation_threshold_cents=int(mandate.escalation_threshold) if mandate.escalation_threshold is not None else None,
        status=mandate.status,
        created_at=mandate.created_at,
        remaining=format_cents_to_decimal(remaining_cents) or "0.00",
        reserved=format_cents_to_decimal(reserved_cents) or "0.00",
        spent=format_cents_to_decimal(spent_cents) or "0.00",
        remaining_cents=remaining_cents,
        reserved_cents=reserved_cents,
        spent_cents=spent_cents,
    )


@router.post("", response_model=MandateResponse, status_code=status.HTTP_201_CREATED)
async def create_mandate(
    body: MandateCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> MandateResponse:
    """Create a new agent spending mandate (Operator-only)."""
    now = datetime.now(timezone.utc)
    valid_from = body.valid_from or now
    valid_until = body.valid_until or (now.replace(year=now.year + 1))

    budget_cents = to_cents(body.budget_total)
    cap_cents = to_cents(body.per_transaction_cap)
    esc_cents = to_cents(body.escalation_threshold) if body.escalation_threshold is not None else None

    if budget_cents is None or budget_cents <= 0:
        raise HTTPException(status_code=400, detail="budget_total must be greater than zero")
    if cap_cents is None or cap_cents <= 0:
        raise HTTPException(status_code=400, detail="per_transaction_cap must be greater than zero")

    mandate = Mandate(
        agent_id=body.agent_id,
        budget_total=budget_cents,
        per_transaction_cap=cap_cents,
        allowlist_merchants=[m.strip().lower() for m in body.allowlist_merchants],
        allowed_currencies=[c.upper() for c in body.allowed_currencies],
        period=body.period.lower(),
        valid_from=valid_from,
        valid_until=valid_until,
        escalation_threshold=esc_cents,
        status="active",
    )
    db.add(mandate)
    await db.commit()
    await db.refresh(mandate)

    return await _enrich_mandate_response(mandate)


@router.get("", response_model=list[MandateResponse])
async def list_mandates(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> list[MandateResponse]:
    """List all mandates with remaining/reserved/spent balances (Operator-only)."""
    stmt = select(Mandate).order_by(Mandate.created_at.desc())
    mandates = (await db.execute(stmt)).scalars().all()
    return [await _enrich_mandate_response(m) for m in mandates]


@router.get("/{mandate_id}", response_model=MandateResponse)
async def get_mandate(
    mandate_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> MandateResponse:
    """Get single mandate details including real-time balances (Operator-only)."""
    stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
    mandate = (await db.execute(stmt)).scalar_one_or_none()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return await _enrich_mandate_response(mandate)


@router.patch("/{mandate_id}", response_model=MandateResponse)
async def patch_mandate(
    mandate_id: str,
    body: MandatePatchRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> MandateResponse:
    """Update mandate fields (Operator-only)."""
    stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
    mandate = (await db.execute(stmt)).scalar_one_or_none()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")

    if body.budget_total is not None:
        mandate.budget_total = to_cents(body.budget_total)
    if body.per_transaction_cap is not None:
        mandate.per_transaction_cap = to_cents(body.per_transaction_cap)
    if body.allowlist_merchants is not None:
        mandate.allowlist_merchants = [m.strip().lower() for m in body.allowlist_merchants]
    if body.allowed_currencies is not None:
        mandate.allowed_currencies = [c.upper() for c in body.allowed_currencies]
    if body.period is not None:
        mandate.period = body.period.lower()
    if body.valid_from is not None:
        mandate.valid_from = body.valid_from
    if body.valid_until is not None:
        mandate.valid_until = body.valid_until
    if body.escalation_threshold is not None:
        mandate.escalation_threshold = to_cents(body.escalation_threshold)
    if body.status is not None:
        mandate.status = body.status.lower()

    await db.commit()
    await db.refresh(mandate)
    return await _enrich_mandate_response(mandate)


@router.post("/{mandate_id}/revoke", response_model=MandateResponse)
async def revoke_mandate(
    mandate_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> MandateResponse:
    """Revoke an active or frozen mandate (Operator-only)."""
    stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
    mandate = (await db.execute(stmt)).scalar_one_or_none()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")

    mandate.status = "revoked"
    await db.commit()
    await db.refresh(mandate)
    return await _enrich_mandate_response(mandate)


@router.post("/{mandate_id}/freeze", response_model=MandateResponse)
async def freeze_mandate(
    mandate_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> MandateResponse:
    """Freeze an active mandate (Operator-only)."""
    stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
    mandate = (await db.execute(stmt)).scalar_one_or_none()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")

    mandate.status = "frozen"
    await db.commit()
    await db.refresh(mandate)
    return await _enrich_mandate_response(mandate)


@router.post("/{mandate_id}/unfreeze", response_model=MandateResponse)
async def unfreeze_mandate(
    mandate_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> MandateResponse:
    """Unfreeze a frozen mandate back to active (Operator-only)."""
    stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
    mandate = (await db.execute(stmt)).scalar_one_or_none()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")

    if mandate.status != "frozen":
        raise HTTPException(status_code=400, detail=f"Cannot unfreeze mandate with status '{mandate.status}'")

    mandate.status = "active"
    await db.commit()
    await db.refresh(mandate)
    return await _enrich_mandate_response(mandate)
