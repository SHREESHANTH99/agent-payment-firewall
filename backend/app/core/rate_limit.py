"""Rate limiting utility using Redis token bucket / sliding counter."""
import time
from typing import Optional
from fastapi import HTTPException, status
from app.services.budget import budget_service


async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60,
    retry_after_seconds: Optional[int] = None,
) -> None:
    """Check and increment rate limit for a given key.

    Raises HTTPException(429) with Retry-After header if limit exceeded.
    """
    try:
        r = await budget_service.get_redis()
        current_time = int(time.time())
        window_bucket = current_time // window_seconds
        redis_key = f"apf:ratelimit:{key}:{window_bucket}"

        # Increment count in the window
        count = await r.incr(redis_key)
        if count == 1:
            await r.expire(redis_key, window_seconds + 5)

        if count > limit:
            remaining_seconds = window_seconds - (current_time % window_seconds)
            retry_after = retry_after_seconds or max(1, remaining_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except Exception:
        # In case Redis is unreachable or in non-critical error, fail open on rate limits
        return
