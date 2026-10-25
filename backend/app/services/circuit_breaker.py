"""Circuit breaker service automatically freezing compromised spending mandates."""
import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Mandate, MandateStatus
from app.services.audit import append_event
from app.services.budget import budget_service
from app.services.events import event_publisher

logger = logging.getLogger(__name__)


async def trip(
    mandate_id: str,
    intent_id: Optional[str],
    cause: str,
    details: Any,
    session: AsyncSession,
) -> bool:
    """
    Trip the circuit breaker for a mandate:
    1. Sets mandate status to 'frozen'.
    2. Appends an immutable audit event 'mandate_frozen' with the cause and details.
    3. Publishes an alert event on Redis channel 'apf:events'.
    """
    stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
    mandate = (await session.execute(stmt)).scalar_one_or_none()

    if not mandate:
        logger.error("Circuit breaker trip requested for non-existent mandate %s", mandate_id)
        return False

    logger.warning(
        "Circuit breaker TRIPPED for mandate %s (intent=%s, cause=%s)",
        mandate_id,
        intent_id,
        cause,
    )

    mandate.status = MandateStatus.FROZEN
    await session.commit()
    await session.refresh(mandate)

    # Append audit event
    await append_event(
        session,
        intent_id=intent_id,
        event="mandate_frozen",
        payload={
            "mandate_id": mandate_id,
            "cause": cause,
            "details": details if isinstance(details, (dict, list, str, int, float, bool)) else str(details),
        },
    )

    # Publish on Redis channel apf:events
    try:
        r = await budget_service.get_redis()
        event_payload = json.dumps({
            "type": "mandate_frozen",
            "mandate_id": mandate_id,
            "intent_id": intent_id,
            "cause": cause,
            "details": details if isinstance(details, (dict, list, str, int, float, bool)) else str(details),
        })
        await r.publish("apf:events", event_payload)
    except Exception as exc:
        logger.warning("Failed to publish mandate_frozen event to Redis: %s", exc)

    return True
