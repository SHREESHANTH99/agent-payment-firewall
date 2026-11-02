"""Operator admin endpoints for runtime risk configuration."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import operator_auth
from app.services.audit import append_event
from app.services.events import event_publisher
from app.services.risk_config import RiskConfig, risk_config_state

router = APIRouter(prefix="/admin", tags=["admin"])


class RiskConfigUpdateRequest(BaseModel):
    canary_enabled: bool
    judge_enabled: bool
    llm_cache_enabled: bool | None = None


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
        llm_cache_enabled=body.llm_cache_enabled,
    )

    await append_event(
        db,
        intent_id=None,
        event="risk_config_updated",
        payload={
            "canary_enabled": new_cfg.canary_enabled,
            "judge_enabled": new_cfg.judge_enabled,
            "llm_cache_enabled": new_cfg.llm_cache_enabled,
        },
    )

    # Publish risk_config_changed event (fire-and-forget)
    await event_publisher.publish("risk_config_changed", {
        "canary_enabled": new_cfg.canary_enabled,
        "judge_enabled": new_cfg.judge_enabled,
        "changed_by": "operator",
    })

    return new_cfg


class RegisterAgentKeyRequest(BaseModel):
    agent_id: str
    key: str


@router.post("/agent-keys")
async def register_runtime_agent_key(
    body: RegisterAgentKeyRequest,
    _: bool = Depends(operator_auth),
) -> dict:
    """Register a runtime agent key for testing/eval isolation (Operator-only)."""
    from app.core.config import settings
    settings.AGENT_API_KEYS[body.key] = body.agent_id
    return {"status": "registered", "agent_id": body.agent_id}
