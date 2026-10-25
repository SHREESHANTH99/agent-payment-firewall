"""Operator API endpoints for inspecting and verifying the audit log."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import operator_auth
from app.models.models import AuditLog
from app.services.audit import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    intent_id: Optional[str] = None
    event: str
    payload: dict[str, Any]
    prev_hash: Optional[str] = None
    hash: str
    created_at: str


class PaginatedAuditResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int


@router.get("", response_model=PaginatedAuditResponse)
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> PaginatedAuditResponse:
    """Get paginated audit logs with total count (Operator-only)."""
    count_stmt = select(func.count(AuditLog.id))
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(AuditLog)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        AuditLogResponse(
            id=row.id,
            intent_id=row.intent_id,
            event=row.event,
            payload=row.payload or {},
            prev_hash=row.prev_hash,
            hash=row.hash,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]
    return PaginatedAuditResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/verify")
async def verify_audit_log_chain(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(operator_auth),
) -> dict[str, Any]:
    """Verify cryptographic hash-chain integrity from genesis (Operator-only)."""
    return await verify_chain(db)
