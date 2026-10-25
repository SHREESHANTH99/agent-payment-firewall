"""WebSocket dashboard endpoint with one-time ticket auth and shared Redis pub/sub fan-out."""
import asyncio
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import operator_auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

TICKET_TTL_SECONDS = 60
PING_INTERVAL_SECONDS = 20
EVENTS_CHANNEL = "apf:events"
TICKET_KEY_PREFIX = "apf:ws:ticket:"

# Shared state: set of client queues and the singleton subscriber task
_clients: set[asyncio.Queue] = set()
_subscriber_task: Optional[asyncio.Task] = None
_redis_sub_client: Optional[aioredis.Redis] = None


class TicketResponse(BaseModel):
    ticket: str
    expires_at: str


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _subscriber_loop() -> None:
    """
    Shared Redis pub/sub subscriber. Subscribes once and fans messages to all connected clients.
    Auto-reconnects on error.
    """
    global _redis_sub_client
    while True:
        try:
            _redis_sub_client = await _get_redis()
            pubsub = _redis_sub_client.pubsub()
            await pubsub.subscribe(EVENTS_CHANNEL)
            logger.info("WebSocket fan-out: subscribed to channel %s", EVENTS_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    dead = set()
                    for q in list(_clients):
                        try:
                            q.put_nowait(data)
                        except asyncio.QueueFull:
                            dead.add(q)
                    _clients.difference_update(dead)
        except asyncio.CancelledError:
            logger.info("WebSocket subscriber task cancelled")
            break
        except Exception as exc:
            logger.warning("WebSocket subscriber error (reconnecting in 2s): %s", exc)
            await asyncio.sleep(2)
        finally:
            if _redis_sub_client:
                try:
                    await _redis_sub_client.close()
                except Exception:
                    pass


def _ensure_subscriber() -> None:
    """Start the shared subscriber task if not already running."""
    global _subscriber_task
    if _subscriber_task is None or _subscriber_task.done():
        _subscriber_task = asyncio.ensure_future(_subscriber_loop())
        logger.info("Started shared WebSocket fan-out subscriber task")


@router.post("/ws/ticket", response_model=TicketResponse, status_code=201)
async def create_ws_ticket(_: bool = Depends(operator_auth)) -> TicketResponse:
    """Issue a single-use 60-second WebSocket connection ticket (Operator-only)."""
    ticket = secrets.token_hex(32)
    redis = await _get_redis()
    try:
        key = f"{TICKET_KEY_PREFIX}{ticket}"
        await redis.set(key, "1", ex=TICKET_TTL_SECONDS)
    finally:
        await redis.close()

    expires_at = datetime.now(timezone.utc).isoformat()
    return TicketResponse(ticket=ticket, expires_at=expires_at)


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, ticket: str) -> None:
    """
    WebSocket endpoint for the real-time dashboard.
    Validates single-use ticket, then streams apf:events messages to the client.
    """
    # Validate + consume ticket
    redis = await _get_redis()
    key = f"{TICKET_KEY_PREFIX}{ticket}"
    try:
        deleted = await redis.delete(key)
    finally:
        await redis.close()

    if not deleted:
        await websocket.close(code=4003, reason="Invalid or expired ticket")
        return

    await websocket.accept()
    _ensure_subscriber()

    client_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _clients.add(client_queue)
    logger.info("WebSocket client connected. Total clients: %d", len(_clients))

    try:
        ping_task = asyncio.create_task(_ping_loop(websocket))
        while True:
            try:
                # Wait for next event with 1s timeout to check connection
                msg = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                await websocket.send_text(msg)
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        _clients.discard(client_queue)
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass
        logger.info("WebSocket client removed. Total clients: %d", len(_clients))


async def _ping_loop(websocket: WebSocket) -> None:
    """Send a ping message every 20 seconds to keep the connection alive."""
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        try:
            await websocket.send_text(json.dumps({"type": "ping"}))
        except Exception:
            break
