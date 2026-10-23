"""PayPal webhook endpoint router."""
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import WebhookEvent
from app.paypal.webhooks import verify_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PAYOUT_EVENT_TYPES = {
    "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
    "PAYMENT.PAYOUTS-ITEM.FAILED",
    "PAYMENT.PAYOUTS-ITEM.BLOCKED",
    "PAYMENT.PAYOUTS-ITEM.DENIED",
    "PAYMENT.PAYOUTS-ITEM.RETURNED",
    "PAYMENT.PAYOUTSBATCH.SUCCESS",
    "PAYMENT.PAYOUTSBATCH.DENIED",
}


def _extract_batch_identifiers(resource: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract payout_batch_id and sender_batch_id from webhook resource."""
    payout_batch_id = resource.get("payout_batch_id")
    if not payout_batch_id and isinstance(resource.get("batch_header"), dict):
        payout_batch_id = resource["batch_header"].get("payout_batch_id")

    sender_batch_id = resource.get("sender_batch_id")
    if not sender_batch_id and isinstance(resource.get("batch_header"), dict):
        sender_batch_header = resource["batch_header"].get("sender_batch_header")
        if isinstance(sender_batch_header, dict):
            sender_batch_id = sender_batch_header.get("sender_batch_id")
    if not sender_batch_id and isinstance(resource.get("sender_batch_header"), dict):
        sender_batch_id = resource["sender_batch_header"].get("sender_batch_id")

    return payout_batch_id, sender_batch_id


@router.post("/paypal")
async def handle_paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Handle PayPal webhook notifications.

    Reads exact raw bytes, verifies cryptographic signature with PayPal,
    deduplicates by event_id, stores the event, and processes payout updates.
    """
    # Read the exact bytes without re-serialization
    raw_body = await request.body()

    # Verify signature with PayPal
    is_valid = await verify_webhook(request.headers, raw_body)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid signature",
        )

    # Parse JSON payload
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid json body",
        )

    event_id = data.get("id")
    event_type = data.get("event_type", "UNKNOWN")
    resource = data.get("resource") or {}

    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing event id",
        )

    # Check if event already exists (deduplication)
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    existing_event = (await db.execute(stmt)).scalar_one_or_none()
    if existing_event:
        logger.info("Duplicate PayPal webhook event received (id=%s), returning duplicate status", event_id)
        return {"status": "duplicate"}

    # Insert new event
    webhook_event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        resource=resource,
        processed=False,
    )
    db.add(webhook_event)

    try:
        await db.commit()
        await db.refresh(webhook_event)
    except IntegrityError:
        await db.rollback()
        logger.info("Concurrent duplicate insertion prevented for event_id=%s", event_id)
        return {"status": "duplicate"}

    # Handle payout event types
    payout_batch_id, sender_batch_id = _extract_batch_identifiers(resource)

    if event_type in PAYOUT_EVENT_TYPES:
        logger.info(
            "Processing PayPal webhook event: type=%s payout_batch_id=%s sender_batch_id=%s",
            event_type,
            payout_batch_id,
            sender_batch_id,
        )
        # TODO: Update PaymentIntent status by paypal_ref (payout_batch_id or sender_batch_id) once the intent pipeline exists.
        webhook_event.processed = True
        await db.commit()
    else:
        logger.info(
            "Received unknown/unhandled PayPal webhook event type: %s (id=%s)",
            event_type,
            event_id,
        )

    return {"status": "ok"}
