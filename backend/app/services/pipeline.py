"""Core payment intent pipeline orchestrating idempotency, policy rules, budget, and execution."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any, Callable, Coroutine, Optional, Union

from fastapi import HTTPException, status
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Mandate, PaymentIntent, PaymentIntentStatus
from app.risk.rules import RuleResult, evaluate_rules, to_cents
from app.services.audit import append_event
from app.services.budget import budget_service
from app.services.execution import execute_intent
from app.services.idempotency import compute_payload_hash, idempotency_service

logger = logging.getLogger(__name__)


@dataclass
class RiskResult:
    verdict: str  # allow | escalate | deny
    details: dict[str, Any] = field(default_factory=dict)


# Risk check hook registry
RiskCheck = Callable[[PaymentIntent, Mandate], Coroutine[Any, Any, RiskResult]]
RISK_CHECKS: list[RiskCheck] = []


def register_risk_check(check: RiskCheck) -> None:
    RISK_CHECKS.append(check)


async def process_intent(
    agent_id: str,
    request_data: dict[str, Any],
    session: AsyncSession,
) -> dict[str, Any]:
    """
    Execute full intent processing pipeline with audit logging at every step:
    a. Idempotency claim (replay returns stored decision; conflict raises 409)
    b. Mandate verification (must exist and belong to agent_id)
    c. Rules evaluation (pure rules engine; failure -> denied with reasons)
    d. Budget reservation (reserve via Redis; failure -> denied BUDGET_EXCEEDED)
    e. Risk checks (canary/judge hooks -> stored in risk_details)
    f. Decision:
       - deny -> release reservation, mark denied, audit
       - escalate -> mark escalated, keep reservation with TTL, publish Redis pub/sub event
       - approve -> execute payout via execute_intent
    Fail-closed: Any unhandled exception releases reservation, marks intent failed, and audits.
    """
    idempotency_key = request_data.get("idempotency_key")
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing idempotency_key")

    payload_hash = compute_payload_hash(request_data)

    # a. Idempotency claim
    cached_response = await idempotency_service.check_and_claim(idempotency_key, payload_hash)
    if cached_response and cached_response.get("status") != "in_progress":
        logger.info("Idempotency replay for key=%s", idempotency_key)
        return cached_response

    mandate_id = request_data.get("mandate_id")
    raw_amount = request_data.get("amount")
    currency = request_data.get("currency", "USD").upper()
    merchant = request_data.get("merchant", "").strip().lower()
    description = request_data.get("description")
    reasoning = request_data.get("reasoning")
    source_context = request_data.get("source_context")

    try:
        amount_cents = to_cents(raw_amount)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid amount: {e}")

    if amount_cents is None or amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")

    # Create intent record in DB
    intent = PaymentIntent(
        mandate_id=mandate_id,
        idempotency_key=idempotency_key,
        amount=amount_cents,
        currency=currency,
        merchant=merchant,
        description=description,
        reasoning=reasoning,
        source_context=source_context,
        status=PaymentIntentStatus.PENDING,
        decision_reasons=[],
        risk_details={},
    )
    session.add(intent)
    await session.commit()
    await session.refresh(intent)

    await append_event(
        session,
        intent_id=intent.id,
        event="intent.created",
        payload={
            "agent_id": agent_id,
            "mandate_id": mandate_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "merchant": merchant,
        },
    )

    reservation_made = False

    try:
        # b. Load and verify mandate
        stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
        mandate = (await session.execute(stmt)).scalar_one_or_none()

        if not mandate:
            intent.status = PaymentIntentStatus.DENIED
            intent.decision_reasons = [{"code": "MANDATE_NOT_FOUND", "message": f"Mandate '{mandate_id}' not found"}]
            await session.commit()
            await append_event(session, intent.id, "intent.denied", {"reasons": intent.decision_reasons})
            res = {
                "intent_id": intent.id,
                "decision": "denied",
                "status": intent.status.value,
                "reasons": intent.decision_reasons,
                "risk": intent.risk_details,
            }
            await idempotency_service.store_response(idempotency_key, res)
            return res

        if mandate.agent_id != agent_id:
            intent.status = PaymentIntentStatus.DENIED
            intent.decision_reasons = [{
                "code": "MANDATE_AGENT_MISMATCH",
                "message": f"Mandate belongs to agent '{mandate.agent_id}', not '{agent_id}'",
            }]
            await session.commit()
            await append_event(session, intent.id, "intent.denied", {"reasons": intent.decision_reasons})
            res = {
                "intent_id": intent.id,
                "decision": "denied",
                "status": intent.status.value,
                "reasons": intent.decision_reasons,
                "risk": intent.risk_details,
            }
            await idempotency_service.store_response(idempotency_key, res)
            return res

        # c. Rules evaluation (pure function)
        rule_result: RuleResult = evaluate_rules(mandate, {
            "amount": Decimal(amount_cents) / 100,
            "amount_cents": amount_cents,
            "currency": currency,
            "merchant": merchant,
        })

        if not rule_result.passed:
            intent.status = PaymentIntentStatus.DENIED
            intent.decision_reasons = rule_result.failures
            await session.commit()
            await append_event(session, intent.id, "intent.denied", {"reasons": rule_result.failures})
            res = {
                "intent_id": intent.id,
                "decision": "denied",
                "status": intent.status.value,
                "reasons": intent.decision_reasons,
                "risk": intent.risk_details,
            }
            await idempotency_service.store_response(idempotency_key, res)
            return res

        # d. Budget reservation
        period_key = budget_service.get_period_key(mandate.period)
        reservation_ttl = settings.ESCALATION_TIMEOUT_SECONDS + 60

        reserved = await budget_service.reserve(
            mandate_id=mandate.mandate_id,
            period_key=period_key,
            intent_id=intent.id,
            amount_cents=amount_cents,
            budget_cents=int(mandate.budget_total),
            ttl_seconds=reservation_ttl,
        )

        if not reserved:
            intent.status = PaymentIntentStatus.DENIED
            intent.decision_reasons = [{"code": "BUDGET_EXCEEDED", "message": "Insufficient mandate budget"}]
            await session.commit()
            await append_event(session, intent.id, "intent.denied", {"reasons": intent.decision_reasons})
            res = {
                "intent_id": intent.id,
                "decision": "denied",
                "status": intent.status.value,
                "reasons": intent.decision_reasons,
                "risk": intent.risk_details,
            }
            await idempotency_service.store_response(idempotency_key, res)
            return res

        reservation_made = True
        await append_event(session, intent.id, "budget.reserved", {
            "mandate_id": mandate.mandate_id,
            "period_key": period_key,
            "amount_cents": amount_cents,
        })

        # e. Risk checks hooks
        risk_escalate = False
        risk_deny = False
        collected_risk: dict[str, Any] = {}

        for check in RISK_CHECKS:
            r_res: RiskResult = await check(intent, mandate)
            collected_risk[check.__name__] = r_res.details
            if r_res.verdict == "deny":
                risk_deny = True
            elif r_res.verdict == "escalate":
                risk_escalate = True

        intent.risk_details = collected_risk

        # f. Decision evaluation
        if risk_deny:
            await budget_service.release(intent.id)
            reservation_made = False
            intent.status = PaymentIntentStatus.DENIED
            intent.decision_reasons = [{"code": "RISK_DENIED", "message": "Denied by risk policy check"}]
            await session.commit()
            await append_event(session, intent.id, "intent.denied", {"risk": collected_risk})
            res = {
                "intent_id": intent.id,
                "decision": "denied",
                "status": intent.status.value,
                "reasons": intent.decision_reasons,
                "risk": intent.risk_details,
            }
            await idempotency_service.store_response(idempotency_key, res)
            return res

        if rule_result.escalate or risk_escalate:
            intent.status = PaymentIntentStatus.ESCALATED
            intent.decision_reasons = [{"code": "ESCALATED_THRESHOLD", "message": "Transaction exceeded escalation threshold"}]
            await session.commit()

            await append_event(session, intent.id, "intent.escalated", {
                "reasons": intent.decision_reasons,
                "timeout_seconds": settings.ESCALATION_TIMEOUT_SECONDS,
            })

            # Publish Redis pub/sub event "intent_escalated" on channel "apf:events"
            try:
                r = await budget_service.get_redis()
                await r.publish("apf:events", json.dumps({
                    "event": "intent_escalated",
                    "intent_id": intent.id,
                    "agent_id": agent_id,
                    "amount_cents": amount_cents,
                    "merchant": merchant,
                    "mandate_id": mandate.mandate_id,
                }))
            except Exception as pe:
                logger.warning("Failed to publish pub/sub intent_escalated event: %s", pe)

            res = {
                "intent_id": intent.id,
                "decision": "escalated",
                "status": intent.status.value,
                "reasons": intent.decision_reasons,
                "risk": intent.risk_details,
            }
            await idempotency_service.store_response(idempotency_key, res)
            return res

        # Approve -> Execute
        intent.status = PaymentIntentStatus.APPROVED
        await session.commit()
        await append_event(session, intent.id, "intent.approved", {"amount_cents": amount_cents})

        # Hardening 1a: Remove reservation TTL so slow payout in executing never loses reservation
        await budget_service.persist(intent.id)

        # Execute payout
        await execute_intent(intent, session)

        res = {
            "intent_id": intent.id,
            "decision": "approved",
            "status": intent.status.value,
            "reasons": intent.decision_reasons or [],
            "risk": intent.risk_details,
        }
        await idempotency_service.store_response(idempotency_key, res)
        return res

    except Exception as exc:
        logger.exception("Unexpected error in pipeline for intent_id=%s: %s", intent.id, exc)
        if reservation_made:
            await budget_service.release(intent.id)

        intent.status = PaymentIntentStatus.FAILED
        intent.decision_reasons = (intent.decision_reasons or []) + [f"Pipeline exception: {str(exc)}"]
        try:
            await session.commit()
            await append_event(session, intent.id, "intent.failed", {"error": str(exc), "stage": "pipeline"})
        except Exception:
            pass

        # Clean up or update idempotency claim on failure
        try:
            await idempotency_service.delete_claim(idempotency_key)
        except Exception:
            pass

        raise
