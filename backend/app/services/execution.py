"""Payout execution service communicating with PayPal API."""
from decimal import Decimal
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import PaymentIntent, PaymentIntentStatus
from app.paypal.exceptions import PayPalAPIError
from app.paypal.payouts import create_payout
from app.services.audit import append_event
from app.services.budget import budget_service

logger = logging.getLogger(__name__)


async def execute_intent(intent: PaymentIntent, session: AsyncSession) -> PaymentIntent:
    """
    Execute an approved payment intent via PayPal Payouts API.
    - Transitions intent status to EXECUTING
    - Calls PayPal create_payout
    - On success: stores payout batch_id in paypal_ref and audits execution
    - On failure: releases budget reservation, transitions status to FAILED, audits failure
    """
    intent.status = PaymentIntentStatus.EXECUTING
    await session.commit()
    await session.refresh(intent)

    await append_event(
        session,
        intent_id=intent.id,
        event="intent.executing",
        payload={
            "idempotency_key": intent.idempotency_key,
            "amount_cents": intent.amount,
            "receiver": intent.merchant,
        },
    )

    amount_decimal = Decimal(intent.amount) / 100

    try:
        payout_res = await create_payout(
            idempotency_key=intent.idempotency_key,
            receiver=intent.merchant,
            amount=amount_decimal,
            currency=intent.currency,
            note=intent.description or "Agent Payment Firewall Disbursement",
        )

        intent.paypal_ref = payout_res.batch_id
        await session.commit()
        await session.refresh(intent)

        await append_event(
            session,
            intent_id=intent.id,
            event="intent.payout_created",
            payload={
                "batch_id": payout_res.batch_id,
                "batch_status": payout_res.batch_status,
            },
        )
        return intent

    except Exception as exc:
        logger.error("PayPal payout execution failed for intent_id=%s: %s", intent.id, exc)

        # Release budget reservation on failure
        await budget_service.release(intent.id)

        intent.status = PaymentIntentStatus.FAILED
        intent.decision_reasons = (intent.decision_reasons or []) + [f"Payout execution error: {str(exc)}"]
        await session.commit()
        await session.refresh(intent)

        await append_event(
            session,
            intent_id=intent.id,
            event="intent.failed",
            payload={"error": str(exc), "stage": "execution"},
        )
        return intent
