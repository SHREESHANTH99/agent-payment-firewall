"""Budget reservation, commit, release, and rebuild service using Redis Lua scripts."""
from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional, Union

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Mandate, PaymentIntent, PaymentIntentStatus

logger = logging.getLogger(__name__)

# Redis Lua Script for atomic reservation
# Keys:
# KEYS[1] = balance key (hash of mandate:period -> fields: spent, reserved)
# KEYS[2] = reservation key (string/hash of intent reservation record)
# ARGV[1] = intent_id
# ARGV[2] = amount_cents (integer)
# ARGV[3] = budget_cents (integer)
# ARGV[4] = ttl_seconds (integer)
# ARGV[5] = mandate_id
# ARGV[6] = period_key
RESERVE_LUA_SCRIPT = """
local balance_key = KEYS[1]
local res_key = KEYS[2]

local intent_id = ARGV[1]
local amount = tonumber(ARGV[2])
local budget = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local mandate_id = ARGV[5]
local period_key = ARGV[6]

-- Check if reservation already exists (idempotency check)
if redis.call("EXISTS", res_key) == 1 then
    return 1
end

-- Read current spent and reserved balances
local spent = tonumber(redis.call("HGET", balance_key, "spent") or "0")
local reserved = tonumber(redis.call("HGET", balance_key, "reserved") or "0")

if (spent + reserved + amount) <= budget then
    -- Increment reserved
    redis.call("HINCRBY", balance_key, "reserved", amount)
    -- Store reservation record with TTL
    local data = cjson.encode({
        intent_id = intent_id,
        amount = amount,
        mandate_id = mandate_id,
        period_key = period_key
    })
    redis.call("SET", res_key, data, "EX", ttl)
    return 1
else
    return 0
end
"""

# Redis Lua Script for atomic commit (move reserved -> spent)
# KEYS[1] = res_key
COMMIT_LUA_SCRIPT = """
local res_key = KEYS[1]

local data_str = redis.call("GET", res_key)
if not data_str then
    return 0
end

local data = cjson.decode(data_str)
local amount = tonumber(data["amount"])
local mandate_id = data["mandate_id"]
local period_key = data["period_key"]
local balance_key = "mandate:" .. mandate_id .. ":" .. period_key .. ":balance"

-- Decrement reserved and increment spent
redis.call("HINCRBY", balance_key, "reserved", -amount)
redis.call("HINCRBY", balance_key, "spent", amount)
redis.call("DEL", res_key)
return 1
"""

# Redis Lua Script for atomic release (decrement reserved and remove record)
# KEYS[1] = res_key
RELEASE_LUA_SCRIPT = """
local res_key = KEYS[1]

local data_str = redis.call("GET", res_key)
if not data_str then
    -- Safe to call twice, already released or expired
    return 0
end

local data = cjson.decode(data_str)
local amount = tonumber(data["amount"])
local mandate_id = data["mandate_id"]
local period_key = data["period_key"]
local balance_key = "mandate:" .. mandate_id .. ":" .. period_key .. ":balance"

redis.call("HINCRBY", balance_key, "reserved", -amount)
redis.call("DEL", res_key)
return 1
"""


class BudgetService:
    """Manages mandate budget allocations in Redis backed by PostgreSQL."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._redis = redis_client
        self._reserve_sha: Optional[str] = None
        self._commit_sha: Optional[str] = None
        self._release_sha: Optional[str] = None

    async def get_redis(self) -> aioredis.Redis:
        import asyncio
        loop = asyncio.get_running_loop()
        if self._redis is None or getattr(self._redis, "_loop", None) != loop:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            setattr(self._redis, "_loop", loop)
        return self._redis

    @staticmethod
    def get_period_key(period_type: str, dt: Optional[datetime] = None) -> str:
        """
        Compute standard period key:
        - 'lifetime' -> 'lifetime'
        - 'daily' -> 'YYYY-MM-DD'
        - 'weekly' -> 'YYYY-Www' (ISO calendar year and week)
        """
        pt = str(period_type).lower()
        if pt == "lifetime":
            return "lifetime"

        if dt is None:
            dt = datetime.now(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        if pt == "daily":
            return dt.strftime("%Y-%m-%d")
        if pt == "weekly":
            year, week, _ = dt.isocalendar()
            return f"{year}-W{week:02d}"

        return "lifetime"

    def _balance_key(self, mandate_id: str, period_key: str) -> str:
        return f"mandate:{mandate_id}:{period_key}:balance"

    def _res_key(self, intent_id: str) -> str:
        return f"reservation:{intent_id}"

    async def reserve(
        self,
        mandate_id: str,
        period_key: str,
        intent_id: str,
        amount_cents: int,
        budget_cents: int,
        ttl_seconds: int = 660,
    ) -> bool:
        """
        Atomically reserve funds for an intent using a registered Lua script.
        Succeeds only if spent + reserved + amount <= budget.
        Idempotent per intent_id.
        """
        r = await self.get_redis()
        balance_key = self._balance_key(mandate_id, period_key)
        res_key = self._res_key(intent_id)

        try:
            result = await r.eval(
                RESERVE_LUA_SCRIPT,
                2,
                balance_key,
                res_key,
                intent_id,
                amount_cents,
                budget_cents,
                ttl_seconds,
                mandate_id,
                period_key,
            )
            return bool(result == 1)
        except Exception as e:
            logger.error("Error executing reserve Lua script: %s", e)
            raise

    async def commit(self, intent_id: str) -> bool:
        """
        Atomically move reserved funds -> spent and remove reservation record.
        """
        r = await self.get_redis()
        res_key = self._res_key(intent_id)
        try:
            result = await r.eval(COMMIT_LUA_SCRIPT, 1, res_key)
            return bool(result == 1)
        except Exception as e:
            logger.error("Error executing commit Lua script: %s", e)
            raise

    async def release(self, intent_id: str) -> bool:
        """
        Atomically release reserved funds and remove reservation record.
        Safe to call twice (idempotent / no-op if already released).
        """
        r = await self.get_redis()
        res_key = self._res_key(intent_id)
        try:
            result = await r.eval(RELEASE_LUA_SCRIPT, 1, res_key)
            return bool(result == 1)
        except Exception as e:
            logger.error("Error executing release Lua script: %s", e)
            raise

    async def get_balances(self, mandate_id: str, period_key: str) -> dict[str, int]:
        """
        Retrieve spent and reserved balances in integer cents.
        """
        r = await self.get_redis()
        balance_key = self._balance_key(mandate_id, period_key)
        data = await r.hgetall(balance_key)
        spent = int(data.get("spent", 0))
        reserved = int(data.get("reserved", 0))
        # Ensure non-negative counters
        spent = max(0, spent)
        reserved = max(0, reserved)
        return {"spent": spent, "reserved": reserved}

    async def rebuild_from_db(self, session: AsyncSession) -> None:
        """
        Recompute spent (sum of executed intents) and reserved (escalated/approved/executing)
        from PostgreSQL source-of-truth and reset Redis counters on startup.
        """
        r = await self.get_redis()
        logger.info("Rebuilding Redis budget balances from PostgreSQL source of truth...")

        # 1. Fetch all mandates
        stmt_mandates = select(Mandate)
        mandates = (await session.execute(stmt_mandates)).scalars().all()
        mandate_map = {m.mandate_id: m for m in mandates}

        # 2. Fetch all relevant payment intents
        stmt_intents = select(PaymentIntent)
        intents = (await session.execute(stmt_intents)).scalars().all()

        # Map: (mandate_id, period_key) -> {"spent": int, "reserved": int}
        aggregated: dict[tuple[str, str], dict[str, int]] = {}

        for intent in intents:
            if not intent.mandate_id or intent.mandate_id not in mandate_map:
                continue
            mandate = mandate_map[intent.mandate_id]
            period_key = self.get_period_key(mandate.period, intent.created_at)
            key = (intent.mandate_id, period_key)

            if key not in aggregated:
                aggregated[key] = {"spent": 0, "reserved": 0}

            amount_cents = int(intent.amount)

            if intent.status == PaymentIntentStatus.EXECUTED:
                aggregated[key]["spent"] += amount_cents
            elif intent.status in (
                PaymentIntentStatus.ESCALATED,
                PaymentIntentStatus.APPROVED,
                PaymentIntentStatus.EXECUTING,
            ):
                aggregated[key]["reserved"] += amount_cents

        # Reset and write to Redis
        for (m_id, p_key), balances in aggregated.items():
            b_key = self._balance_key(m_id, p_key)
            await r.hset(b_key, mapping={
                "spent": str(balances["spent"]),
                "reserved": str(balances["reserved"]),
            })
            logger.info("Rebuilt balance for mandate=%s period=%s: %s", m_id, p_key, balances)

        logger.info("Redis budget rebuild complete")


budget_service = BudgetService()
