"""Cryptographically chained immutable audit log service."""
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
ADVISORY_LOCK_ID = 987654321


def canonical_json(intent_id: Optional[str], event: str, payload: Any, timestamp: str) -> str:
    """Produce deterministic, sorted-keys, compact JSON representation."""
    doc = {
        "event": event,
        "intent_id": intent_id,
        "payload": payload,
        "timestamp": timestamp,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


async def append_event(
    session: AsyncSession,
    intent_id: Optional[str],
    event: str,
    payload: Any,
) -> AuditLog:
    """
    Append an immutable event to the cryptographic audit chain.
    Takes pg_advisory_xact_lock to ensure chain linearity under concurrent transactions.
    """
    # Take transaction-level advisory lock in PostgreSQL (no-op on sqlite)
    try:
        await session.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})"))
    except Exception:
        # SQLite/in-memory test fallback
        pass

    # Read latest row's hash
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
    result = await session.execute(stmt)
    latest_row = result.scalar_one_or_none()

    prev_hash = latest_row.hash if latest_row else GENESIS_HASH

    now = datetime.now(timezone.utc)
    ts_str = now.isoformat()

    c_json = canonical_json(intent_id, event, payload, ts_str)
    content_to_hash = (prev_hash + c_json).encode("utf-8")
    row_hash = hashlib.sha256(content_to_hash).hexdigest()

    log_entry = AuditLog(
        intent_id=intent_id,
        event=event,
        payload=payload if isinstance(payload, dict) else {"data": payload},
        prev_hash=prev_hash,
        hash=row_hash,
        created_at=now,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return log_entry


async def verify_chain(session: AsyncSession) -> dict[str, Any]:
    """
    Verify the complete cryptographic integrity of the audit log chain from genesis.
    Returns {valid: bool, checked: int, first_broken_index: int|None}.
    """
    stmt = select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    rows = (await session.execute(stmt)).scalars().all()

    if not rows:
        return {"valid": True, "checked": 0, "first_broken_index": None}

    expected_prev = GENESIS_HASH

    for idx, row in enumerate(rows):
        # 1. Verify prev_hash link
        if row.prev_hash != expected_prev:
            return {"valid": False, "checked": idx, "first_broken_index": idx}

        # 2. Recompute row hash
        ts_str = row.created_at.isoformat() if row.created_at else ""
        c_json = canonical_json(row.intent_id, row.event, row.payload, ts_str)
        expected_hash = hashlib.sha256((expected_prev + c_json).encode("utf-8")).hexdigest()

        if row.hash != expected_hash:
            return {"valid": False, "checked": idx, "first_broken_index": idx}

        expected_prev = row.hash

    return {"valid": True, "checked": len(rows), "first_broken_index": None}
