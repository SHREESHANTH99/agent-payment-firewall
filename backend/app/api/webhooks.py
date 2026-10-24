"""PayPal webhook endpoint router."""
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Mandate, PaymentIntent, PaymentIntentStatus, WebhookEvent
from app.paypal.webhooks import verify_webhook
from app.services.audit import append_event
from app.services.budget import budget_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Events that signal a successful payout
PAYOUT_SUCCESS_EVENTS = {
    "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
    "PAYMENT.PAYOUTSBATCH.SUCCESS",
}

# Events that signal a failed payout
PAYOUT_FAILURE_EVENTS = {
    "PAYMENT.PAYOUTS-ITEM.FAILED",
    "PAYMENT.PAYOUTS-ITEM.BLOCKED",
    "PAYMENT.PAYOUTS-ITEM.DENIED",
    "PAYMENT.PAYOUTS-ITEM.RETURNED",
    "PAYMENT.PAYOUTSBATCH.DENIED",
}

ALL_PAYOUT_EVENT_TYPES = PAYOUT_SUCCESS_EVENTS | PAYOUT_FAILURE_EVENTS


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


async def _resolve_intent(
    db: AsyncSession,
    payout_batch_id: str | None,
    sender_batch_id: str | None,
) -> PaymentIntent | None:
    """Find the PaymentIntent matching by paypal_ref or idempotency_key."""
    filters = []
    if payout_batch_id:
        filters.append(PaymentIntent.paypal_ref == payout_batch_id)
    if sender_batch_id:
        filters.append(PaymentIntent.idempotency_key == sender_batch_id)

    if not filters:
        return None

    stmt = select(PaymentIntent).where(or_(*filters))
    return (await db.execute(stmt)).scalar_one_or_none()


@router.post("/paypal")
async def handle_paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Handle PayPal webhook notifications.

    Reads exact raw bytes, verifies cryptographic signature with PayPal,
    deduplicates by event_id, stores the event, links it to a PaymentIntent,
    and updates budget (commit on success / release on failure).
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

    # Deduplicate by event_id
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    existing_event = (await db.execute(stmt)).scalar_one_or_none()
    if existing_event:
        logger.info("Duplicate PayPal webhook event received (id=%s), skipping", event_id)
        return {"status": "duplicate"}

    # Persist new event
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

    # Route to intent handler for payout events
    if event_type not in ALL_PAYOUT_EVENT_TYPES:
        logger.info("Unhandled PayPal event type=%s (id=%s)", event_type, event_id)
        return {"status": "ok"}

    payout_batch_id, sender_batch_id = _extract_batch_identifiers(resource)
    logger.info(
        "Processing PayPal webhook: type=%s payout_batch_id=%s sender_batch_id=%s",
        event_type, payout_batch_id, sender_batch_id,
    )

    intent = await _resolve_intent(db, payout_batch_id, sender_batch_id)
    if not intent:
        logger.info(
            "No PaymentIntent found for event type=%s payout_batch_id=%s sender_batch_id=%s",
            event_type, payout_batch_id, sender_batch_id,
        )
        webhook_event.processed = True
        await db.commit()
        return {"status": "ok"}

    if event_type in PAYOUT_SUCCESS_EVENTS:
        if intent.status not in (PaymentIntentStatus.EXECUTED,):
            # Idempotent: only commit budget if not already executed
            intent.status = PaymentIntentStatus.EXECUTED
            await db.commit()

            # Retrieve mandate to calculate fallback period key
            stmt_m = select(Mandate).where(Mandate.mandate_id == intent.mandate_id)
            mandate_obj = (await db.execute(stmt_m)).scalar_one_or_none()
            p_key = budget_service.get_period_key(mandate_obj.period, intent.created_at) if mandate_obj else "lifetime"

            await budget_service.commit(
                intent.id,
                fallback_amount=int(intent.amount),
                fallback_mandate_id=intent.mandate_id,
                fallback_period_key=p_key,
            )
            await append_event(
                db,
                intent_id=intent.id,
                event="intent.executed",
                payload={"via": "webhook", "event_type": event_type, "event_id": event_id},
            )
            logger.info("Intent id=%s marked executed via webhook %s", intent.id, event_type)
        else:
            logger.info("Intent id=%s already executed, skipping re-commit", intent.id)

    elif event_type in PAYOUT_FAILURE_EVENTS:
        if intent.status not in (PaymentIntentStatus.FAILED,):
            intent.status = PaymentIntentStatus.FAILED
            intent.decision_reasons = (intent.decision_reasons or []) + [
                {"code": "PAYOUT_FAILED", "message": f"PayPal event: {event_type}"}
            ]
            await db.commit()

            stmt_m = select(Mandate).where(Mandate.mandate_id == intent.mandate_id)
            mandate_obj = (await db.execute(stmt_m)).scalar_one_or_none()
            p_key = budget_service.get_period_key(mandate_obj.period, intent.created_at) if mandate_obj else "lifetime"

            await budget_service.release(
                intent.id,
                fallback_amount=int(intent.amount),
                fallback_mandate_id=intent.mandate_id,
                fallback_period_key=p_key,
            )
            await append_event(
                db,
                intent_id=intent.id,
                event="intent.failed",
                payload={"via": "webhook", "event_type": event_type, "event_id": event_id},
            )
            logger.info("Intent id=%s marked failed via webhook %s", intent.id, event_type)
        else:
            logger.info("Intent id=%s already failed, skipping re-release", intent.id)

    webhook_event.processed = True
    await db.commit()

    return {"status": "ok"}
