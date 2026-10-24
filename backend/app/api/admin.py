"""Operator admin endpoints for runtime risk configuration."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import operator_auth
from app.services.audit import append_event
from app.services.risk_config import RiskConfig, risk_config_state

router = APIRouter(prefix="/admin", tags=["admin"])


class RiskConfigUpdateRequest(BaseModel):
    canary_enabled: bool
    judge_enabled: bool


@router.get("/risk-config", response_model=RiskConfig)
async def get_risk_config(_: bool = Depends(operator_auth)) -> RiskConfig:
    """Retrieve current runtime risk configuration (Operator-only)."""
    return risk_config_state.get_config()


@router.post("/risk-config", response_model=RiskConfig)
async def update_risk_config(
    body: RiskConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> RiskConfig:
    """Update runtime risk configuration and record change to audit log (Operator-only)."""
    new_cfg = risk_config_state.set_config(
        canary_enabled=body.canary_enabled,
        judge_enabled=body.judge_enabled,
    )

    await append_event(
        db,
        intent_id=None,
        event="risk_config_updated",
        payload={
            "canary_enabled": new_cfg.canary_enabled,
            "judge_enabled": new_cfg.judge_enabled,
        },
    )

    return new_cfg
