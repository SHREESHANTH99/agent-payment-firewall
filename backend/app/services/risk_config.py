"""Risk configuration service and runtime toggles for Canary and Judge layers."""
from typing import Any

from pydantic import BaseModel

from app.core.config import settings


class RiskConfig(BaseModel):
    canary_enabled: bool
    judge_enabled: bool
    llm_cache_enabled: bool


class RiskConfigState:
    """In-memory runtime risk configuration with defaults loaded from settings."""

    def __init__(self):
        self.canary_enabled = settings.CANARY_ENABLED
        self.judge_enabled = settings.JUDGE_ENABLED

    def get_config(self) -> RiskConfig:
        return RiskConfig(
            canary_enabled=self.canary_enabled,
            judge_enabled=self.judge_enabled,
            llm_cache_enabled=settings.LLM_CACHE_ENABLED,
        )

    def set_config(self, canary_enabled: bool, judge_enabled: bool, llm_cache_enabled: bool | None = None) -> RiskConfig:
        self.canary_enabled = canary_enabled
        self.judge_enabled = judge_enabled
        if llm_cache_enabled is not None:
            settings.LLM_CACHE_ENABLED = llm_cache_enabled
        return self.get_config()


risk_config_state = RiskConfigState()
