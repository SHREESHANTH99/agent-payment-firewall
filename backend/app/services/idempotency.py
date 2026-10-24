"""Idempotency service using Redis atomic claim and payload hash verification."""
import hashlib
import json
import logging
from typing import Any, Optional

from fastapi import HTTPException, status
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS = 120  # 120 seconds while processing
IDEMPOTENCY_COMPLETED_TTL_SECONDS = 86400    # 24 hours for final response
IDEMPOTENCY_TTL_SECONDS = IDEMPOTENCY_COMPLETED_TTL_SECONDS


def compute_payload_hash(payload: Any) -> str:
    """Compute deterministic SHA-256 hash of request payload."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class IdempotencyService:
    """Provides distributed idempotency locking and response replay via Redis."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis = redis_client

    async def get_redis(self) -> aioredis.Redis:
        import asyncio
        loop = asyncio.get_running_loop()
        if self._redis is None or getattr(self._redis, "_loop", None) != loop:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            setattr(self._redis, "_loop", loop)
        return self._redis

    def _key(self, idempotency_key: str) -> str:
        return f"idempotency:{idempotency_key}"

    async def check_and_claim(
        self,
        idempotency_key: str,
        payload_hash: str,
        ttl_seconds: int = IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS,
    ) -> Optional[dict[str, Any]]:
        """
        Check idempotency claim for a given key.
        - If key does not exist: claims it atomically with short TTL (120s) while processing.
        - If key exists with same payload hash:
            - If response is already stored: returns the stored response dict (replay).
            - If response is still pending: raises HTTP 409 {"detail": "request in progress"}.
        - If key exists with a different payload hash: raises HTTP 409 Conflict.
        """
        r = await self.get_redis()
        redis_key = self._key(idempotency_key)

        initial_data = json.dumps({
            "payload_hash": payload_hash,
            "response": None,
            "status": "in_progress",
        })

        # Atomically set if not exists
        acquired = await r.set(redis_key, initial_data, nx=True, ex=ttl_seconds)
        if acquired:
            # First time seeing this key with this payload
            return None

        # Key already exists: inspect stored state
        stored_str = await r.get(redis_key)
        if not stored_str:
            # Race condition: key expired between set and get; re-attempt acquire
            acquired2 = await r.set(redis_key, initial_data, nx=True, ex=ttl_seconds)
            if acquired2:
                return None
            stored_str = await r.get(redis_key) or "{}"

        try:
            stored = json.loads(stored_str)
        except Exception:
            stored = {}

        stored_hash = stored.get("payload_hash")
        if stored_hash != payload_hash:
            logger.warning(
                "Idempotency conflict for key=%s: received hash=%s, stored hash=%s",
                idempotency_key,
                payload_hash,
                stored_hash,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency key '{idempotency_key}' was previously used with a different request payload",
            )

        stored_response = stored.get("response")
        if stored_response is not None:
            return stored_response

        # Request is currently in progress
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request in progress",
        )

    async def delete_claim(self, idempotency_key: str) -> None:
        """Delete claim on pipeline failure to allow immediate retry."""
        r = await self.get_redis()
        await r.delete(self._key(idempotency_key))

    async def store_response(
        self,
        idempotency_key: str,
        response_data: dict[str, Any],
        ttl_seconds: int = IDEMPOTENCY_COMPLETED_TTL_SECONDS,
    ) -> None:
        """Store the final response with 24h TTL for replay on subsequent identical requests."""
        r = await self.get_redis()
        redis_key = self._key(idempotency_key)

        stored_str = await r.get(redis_key)
        payload_hash = None
        if stored_str:
            try:
                payload_hash = json.loads(stored_str).get("payload_hash")
            except Exception:
                pass

        updated_data = json.dumps({
            "payload_hash": payload_hash,
            "response": response_data,
            "status": "completed",
        })
        await r.set(redis_key, updated_data, ex=ttl_seconds)


idempotency_service = IdempotencyService()
