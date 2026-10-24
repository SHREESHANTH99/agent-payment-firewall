"""Authentication dependencies for agents and operators."""
import hmac
from typing import Annotated, Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def agent_auth(
    x_agent_key: Annotated[Optional[str], Header(alias="X-Agent-Key")] = None,
) -> str:
    """
    Authenticate autonomous agent via X-Agent-Key header.
    Returns agent_id if key matches any entry in AGENT_API_KEYS using constant-time comparison.
    Raises 401 if missing or unknown.
    """
    if not x_agent_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Agent-Key header",
        )

    matched_agent_id: Optional[str] = None
    for key, agent_id in settings.AGENT_API_KEYS.items():
        if hmac.compare_digest(x_agent_key, key):
            matched_agent_id = agent_id
            break

    if matched_agent_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Agent-Key",
        )

    return matched_agent_id


async def operator_auth(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Security(bearer_scheme)] = None,
) -> bool:
    """
    Authenticate human/admin operator via Authorization: Bearer <OPERATOR_TOKEN>.
    Uses constant-time comparison.
    Raises 401 if missing or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_token = settings.OPERATOR_TOKEN
    if not expected_token or not hmac.compare_digest(credentials.credentials, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Operator Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
