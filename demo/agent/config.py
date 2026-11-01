"""Configuration settings for the procurement agent."""
import json
import os
from typing import Any, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    AGENT_LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    AGENT_LLM_API_KEY: str = ""
    AGENT_MODEL: str = "llama-3.3-70b-versatile"
    
    FIREWALL_BASE_URL: str = "http://localhost:8000"
    STORE_BASE_URL: str = "http://localhost:9000"
    
    # Secret key passed in X-Agent-Key header to the firewall (loaded from env)
    AGENT_API_KEY: str = ""
    AGENT_API_KEYS: Any = None
    
    MAX_STEPS: int = 8
    MAX_LLM_CALLS: int = 12
    TIMEOUT_SECONDS: int = 60
    
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_effective_agent_key(self) -> str:
        """Returns AGENT_API_KEY or the first key from AGENT_API_KEYS."""
        if self.AGENT_API_KEY:
            return self.AGENT_API_KEY
        if self.AGENT_API_KEYS:
            if isinstance(self.AGENT_API_KEYS, str):
                try:
                    parsed = json.loads(self.AGENT_API_KEYS)
                    if isinstance(parsed, dict) and parsed:
                        return list(parsed.keys())[0]
                except Exception:
                    pass
            elif isinstance(self.AGENT_API_KEYS, dict) and self.AGENT_API_KEYS:
                return list(self.AGENT_API_KEYS.keys())[0]
        return ""


agent_settings = AgentSettings()
