"""Background scheduler tasks: escalation expiry and executing-payout polling."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import PaymentIntent, PaymentIntentStatus
from app.paypal.payouts import get_payout_status
from app.services.audit import append_event
from app.services.budget import budget_service

logger = logging.getLogger(__name__)


async def _expire_escalated_intents() -> None:
    """Mark timed-out escalated intents as expired and release their budget reservations."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.ESCALATION_TIMEOUT_SECONDS)
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(PaymentIntent).where(
                PaymentIntent.status == PaymentIntentStatus.ESCALATED,
                PaymentIntent.created_at < cutoff,
            )
            intents = (await session.execute(stmt)).scalars().all()
            for intent in intents:
                logger.info("Expiring escalated intent id=%s (created_at=%s)", intent.id, intent.created_at)
                await budget_service.release(intent.id)
                intent.status = PaymentIntentStatus.EXPIRED
                intent.decision_reasons = (intent.decision_reasons or []) + [
                    {"code": "ESCALATION_TIMEOUT", "message": "Escalation window expired without operator action"}
                ]
                await session.commit()
                await append_event(
                    session,
                    intent_id=intent.id,
                    event="intent.expired",
                    payload={"timeout_seconds": settings.ESCALATION_TIMEOUT_SECONDS},
                )
        except Exception as exc:
            logger.warning("Error in escalation expiry loop: %s", exc)


async def escalation_expiry_loop() -> None:
    """Run escalation expiry check every 30 seconds until cancelled."""
    logger.info("Escalation expiry loop started")
    while True:
        try:
            await _expire_escalated_intents()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Unhandled error in escalation_expiry_loop: %s", exc)
        await asyncio.sleep(30)


EXECUTING_STALENESS_SECONDS = 60  # poll PayPal if still 'executing' after this long


async def _poll_executing_intents() -> None:
    """Check stale 'executing' intents against PayPal and update status accordingly."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=EXECUTING_STALENESS_SECONDS)
    async with AsyncSessionLocal() as session:
        try:
            stmt = select(PaymentIntent).where(
                PaymentIntent.status == PaymentIntentStatus.EXECUTING,
                PaymentIntent.updated_at < cutoff,
                PaymentIntent.paypal_ref.isnot(None),
            )
            intents = (await session.execute(stmt)).scalars().all()
            for intent in intents:
                logger.info("Polling PayPal status for intent id=%s paypal_ref=%s", intent.id, intent.paypal_ref)
                try:
                    payout_details = await get_payout_status(intent.paypal_ref)
                    # get_payout_status returns a PayoutBatchDetails model
                    batch_status = payout_details.batch_status or ""

                    SUCCESS_STATUSES = {"SUCCESS"}
                    FAILURE_STATUSES = {"DENIED", "CANCELED", "FAILED"}

                    if batch_status in SUCCESS_STATUSES:
                        if intent.status != PaymentIntentStatus.EXECUTED:
                            intent.status = PaymentIntentStatus.EXECUTED
                            await session.commit()
                            await budget_service.commit(intent.id)
                            await append_event(
                                session,
                                intent_id=intent.id,
                                event="intent.executed",
                                payload={"via": "polling", "batch_status": batch_status},
                            )
                    elif batch_status in FAILURE_STATUSES:
                        if intent.status != PaymentIntentStatus.FAILED:
                            intent.status = PaymentIntentStatus.FAILED
                            intent.decision_reasons = (intent.decision_reasons or []) + [
                                {"code": "PAYOUT_FAILED", "message": f"PayPal batch_status={batch_status}"}
                            ]
                            await session.commit()
                            await budget_service.release(intent.id)
                            await append_event(
                                session,
                                intent_id=intent.id,
                                event="intent.failed",
                                payload={"via": "polling", "batch_status": batch_status},
                            )
                    else:
                        logger.info(
                            "Intent id=%s still in PayPal status=%s, will check again",
                            intent.id, batch_status,
                        )
                except Exception as exc:
                    logger.warning("Failed to poll PayPal for intent id=%s: %s", intent.id, exc)
        except Exception as exc:
            logger.warning("Error in payout polling loop: %s", exc)


async def payout_polling_loop() -> None:
    """Run PayPal payout status polling every 30 seconds until cancelled."""
    logger.info("Payout polling loop started")
    while True:
        try:
            await _poll_executing_intents()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Unhandled error in payout_polling_loop: %s", exc)
        await asyncio.sleep(30)
