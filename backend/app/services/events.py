"""Centralized Redis event publisher for real-time firewall telemetry."""
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

EVENTS_CHANNEL = "apf:events"


class EventPublisher:
    """Helper to publish JSON events {type, ts, data} to Redis channel apf:events."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[aioredis.Redis] = None

    async def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Publish an event to Redis pub/sub channel.
        Never raises exceptions to callers; logs warnings if publish fails.
        """
        payload = {
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        try:
            client = await self._get_client()
            await client.publish(EVENTS_CHANNEL, json.dumps(payload))
            logger.debug("Published event [%s] to channel %s", event_type, EVENTS_CHANNEL)
        except Exception as exc:
            logger.warning("Failed to publish event [%s] to Redis: %s", event_type, exc)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None


event_publisher = EventPublisher()
