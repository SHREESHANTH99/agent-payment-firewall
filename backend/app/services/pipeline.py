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
from app.core.metrics import (
    INTENT_DECISIONS_TOTAL,
    PIPELINE_LATENCY_SECONDS,
    RISK_CHECKS_TOTAL,
)
from app.models.models import Mandate, PaymentIntent, PaymentIntentStatus
from app.risk.canary import canary_scan
from app.risk.judge import judge
from app.risk.rules import RuleResult, evaluate_rules, to_cents
from app.services.audit import append_event
from app.services.budget import budget_service
from app.services.circuit_breaker import trip as trip_circuit_breaker
from app.services.events import event_publisher
from app.services.execution import execute_intent
from app.services.idempotency import compute_payload_hash, idempotency_service
from app.services.risk_config import risk_config_state

logger = logging.getLogger(__name__)


async def evaluate_canary(source_context: str) -> Any:
    """Compatibility wrapper used by tests to patch canary evaluation."""
    return await canary_scan(source_context)


async def evaluate_judge(
    mandate_summary: dict[str, Any],
    intent_summary: dict[str, Any],
    source_context: Optional[str],
) -> Union[tuple[Any, str], Any]:
    """Compatibility wrapper used by tests to patch judge evaluation."""
    return await judge(mandate_summary, intent_summary, source_context)


@dataclass
class RiskResult:
    verdict: str  # allow | escalate | deny
    details: dict[str, Any] = field(default_factory=dict)


def _denial_payload(risk_details: dict[str, Any], cause: str) -> dict[str, Any]:
    """Attach machine-readable denial attribution before persisting/auditing it."""
    risk_details["denial_cause"] = cause
    return risk_details


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _as_float(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def _as_int(value: Any, default: int = 0) -> int:
    return int(value) if isinstance(value, int) else default


def _as_optional_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


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
    import time
    start_time = time.time()
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
    user_task = request_data.get("user_task")
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
        user_task=user_task,
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
            "user_task": user_task,
        },
    )

    # Publish intent_created event
    await event_publisher.publish("intent_created", {
        "intent_id": intent.id,
        "mandate_id": mandate_id,
        "agent_id": agent_id,
        "amount": amount_cents,
        "currency": currency,
        "merchant": merchant,
    })

    reservation_made = False

    try:
        # b. Load and verify mandate
        stmt = select(Mandate).where(Mandate.mandate_id == mandate_id)
        mandate = (await session.execute(stmt)).scalar_one_or_none()

        if not mandate:
            intent.status = PaymentIntentStatus.DENIED
            intent.decision_reasons = [{"code": "MANDATE_NOT_FOUND", "message": f"Mandate '{mandate_id}' not found"}]
            await session.commit()
            intent.risk_details = _denial_payload({}, "rules")
            await append_event(session, intent.id, "intent.denied", {"reasons": intent.decision_reasons, "denial_cause": "rules"})
            await event_publisher.publish("intent_status_changed", {
                "intent_id": intent.id, "old_status": "pending", "new_status": "denied",
                "amount": amount_cents, "merchant": merchant,
            })
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
            intent.risk_details = _denial_payload({}, "rules")
            await append_event(session, intent.id, "intent.denied", {"reasons": intent.decision_reasons, "denial_cause": "rules"})
            await event_publisher.publish("intent_status_changed", {
                "intent_id": intent.id, "old_status": "pending", "new_status": "denied",
                "amount": amount_cents, "merchant": merchant,
            })
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
            intent.risk_details = _denial_payload({}, "rules")
            await append_event(session, intent.id, "intent.denied", {"reasons": rule_result.failures, "denial_cause": "rules"})
            await event_publisher.publish("intent_status_changed", {
                "intent_id": intent.id, "old_status": "pending", "new_status": "denied",
                "amount": amount_cents, "merchant": merchant,
            })
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
            intent.risk_details = _denial_payload({}, "budget")
            await append_event(session, intent.id, "intent.denied", {"reasons": intent.decision_reasons, "denial_cause": "budget"})
            await event_publisher.publish("intent_status_changed", {
                "intent_id": intent.id, "old_status": "pending", "new_status": "denied",
                "amount": amount_cents, "merchant": merchant,
            })
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

        # e. AI Risk checks (Canary & Judge)
        risk_cfg = risk_config_state.get_config()
        risk_details: dict[str, Any] = {}
        risk_escalate = False

        # 1. Canary Scan (if enabled)
        if risk_cfg.canary_enabled and source_context:
            canary_res = await evaluate_canary(source_context)
            canary_meta = _as_dict(getattr(canary_res, "meta", {}))
            risk_details["canary"] = {
                "tripped": _as_bool(getattr(canary_res, "tripped", False)),
                "honeypot_calls": _as_list(getattr(canary_res, "honeypot_calls", [])),
                "segments": _as_int(getattr(canary_res, "segments", 0)),
                "error": _as_optional_str(getattr(canary_res, "error", None)),
                "meta": canary_meta,
                "llm_error": _as_bool(canary_meta.get("llm_error"), False),
                "fail_mode_applied": _as_bool(canary_meta.get("fail_mode_applied"), False),
                "cached": _as_bool(canary_meta.get("cached"), False),
                "provider": _as_optional_str(canary_meta.get("provider")),
                "model": _as_optional_str(canary_meta.get("model")),
                "retries": _as_int(canary_meta.get("retries"), 0),
            }

            if risk_details["canary"]["tripped"]:
                # Canary tripped -> audit event, freeze mandate via circuit breaker, deny intent
                logger.warning("Canary scan tripped for intent %s!", intent.id)
                await append_event(session, intent.id, "canary_tripped", risk_details["canary"])
                await trip_circuit_breaker(
                    mandate_id=mandate.mandate_id,
                    intent_id=intent.id,
                    cause="canary",
                    details=risk_details["canary"],
                    session=session,
                )

                # Release budget reservation
                await budget_service.release(intent.id)
                reservation_made = False

                intent.status = PaymentIntentStatus.DENIED
                intent.risk_details = _denial_payload(risk_details, "llm_error_fail_mode" if canary_meta.get("llm_error") else "canary")
                # Agent-facing reason is strictly generic
                intent.decision_reasons = [{"code": "RISK_POLICY_VIOLATION", "message": "blocked by risk policy"}]
                await session.commit()
                await append_event(session, intent.id, "intent.denied", {"risk": intent.risk_details, "denial_cause": intent.risk_details["denial_cause"]})
                await event_publisher.publish("intent_status_changed", {
                    "intent_id": intent.id, "old_status": "pending", "new_status": "denied",
                    "amount": amount_cents, "merchant": merchant,
                })

                res = {
                    "intent_id": intent.id,
                    "decision": "denied",
                    "status": intent.status.value,
                    "reasons": intent.decision_reasons,
                    "risk": intent.risk_details,
                }
                await idempotency_service.store_response(idempotency_key, res)
                return res

        # 2. Judge Evaluation (if enabled and rules did not deny)
        if risk_cfg.judge_enabled:
            mandate_summary = {
                "mandate_id": mandate.mandate_id,
                "agent_id": mandate.agent_id,
                "budget_total": str(mandate.budget_total),
                "per_transaction_cap": str(mandate.per_transaction_cap),
                "allowlist_merchants": mandate.allowlist_merchants,
            }
            intent_summary = {
                "amount": str(amount_cents / 100),
                "currency": currency,
                "merchant": merchant,
                "description": description,
                "reasoning": reasoning,
                "user_task": user_task,
            }

            judge_eval = await evaluate_judge(mandate_summary, intent_summary, source_context)
            if isinstance(judge_eval, tuple):
                judge_res, judge_verdict = judge_eval
            else:
                judge_res = judge_eval
                judge_verdict = str(getattr(judge_res, "verdict", "escalate"))
            judge_meta = _as_dict(getattr(judge_res, "meta", {}))
            risk_details["judge"] = {
                "safe": _as_bool(getattr(judge_res, "safe", False)),
                "confidence": _as_float(getattr(judge_res, "confidence", 0.0)),
                "injection_suspected": _as_bool(getattr(judge_res, "injection_suspected", False)),
                "reasons": _as_list(getattr(judge_res, "reasons", [])),
                "mismatch_reasons": _as_list(getattr(judge_res, "mismatch_reasons", [])),
                "verdict": judge_verdict,
                "meta": judge_meta,
                "llm_error": _as_bool(judge_meta.get("llm_error"), False),
                "fail_mode_applied": _as_bool(judge_meta.get("fail_mode_applied"), False),
                "cached": _as_bool(judge_meta.get("cached"), False),
                "provider": _as_optional_str(judge_meta.get("provider")),
                "model": _as_optional_str(judge_meta.get("model")),
                "retries": _as_int(judge_meta.get("retries"), 0),
            }
            await append_event(session, intent.id, "judge_evaluated", risk_details["judge"])

            # Check circuit breaker trigger: trip ONLY on payment deviation (judge not safe and confidence >= 0.9)
            # Crucially decoupled: do NOT trip on injection_suspected alone when safe=true
            if not judge_res.safe and judge_res.confidence >= 0.9:
                logger.warning("Judge detected high-confidence payment deviation/threat for intent %s", intent.id)
                await trip_circuit_breaker(
                    mandate_id=mandate.mandate_id,
                    intent_id=intent.id,
                    cause="judge_injection",
                    details=risk_details["judge"],
                    session=session,
                )

            if judge_verdict == "deny":
                await budget_service.release(intent.id)
                reservation_made = False

                intent.status = PaymentIntentStatus.DENIED
                denial_cause = "llm_error_fail_mode" if risk_details["judge"].get("fail_mode_applied") else "judge"
                intent.risk_details = _denial_payload(risk_details, denial_cause)
                intent.decision_reasons = [{"code": "RISK_POLICY_VIOLATION", "message": "blocked by risk policy"}]
                await session.commit()
                await append_event(session, intent.id, "intent.denied", {"risk": intent.risk_details, "denial_cause": denial_cause})
                await event_publisher.publish("intent_status_changed", {
                    "intent_id": intent.id, "old_status": "pending", "new_status": "denied",
                    "amount": amount_cents, "merchant": merchant,
                })

                res = {
                    "intent_id": intent.id,
                    "decision": "denied",
                    "status": intent.status.value,
                    "reasons": intent.decision_reasons,
                    "risk": intent.risk_details,
                }
                await idempotency_service.store_response(idempotency_key, res)
                return res

            elif judge_verdict == "escalate":
                risk_escalate = True

        intent.risk_details = risk_details

        # f. Decision evaluation
        if rule_result.escalate or risk_escalate:
            has_merchant_approval = any(f.get("code") == "MERCHANT_REQUIRES_APPROVAL" for f in rule_result.failures)
            if has_merchant_approval:
                escalation_cause = "policy_approval_required_merchant"
                reason_code = "MERCHANT_REQUIRES_APPROVAL"
                reason_msg = "Merchant requires human approval"
            elif rule_result.escalate:
                escalation_cause = "rules_threshold"
                reason_code = "ESCALATED_THRESHOLD"
                reason_msg = "Transaction requires human review"
            elif risk_details.get("judge", {}).get("fail_mode_applied"):
                escalation_cause = "llm_error_fail_mode"
                reason_code = "ESCALATED_THRESHOLD"
                reason_msg = "Transaction requires human review"
            elif risk_details.get("judge", {}).get("injection_suspected") or bool(risk_details.get("judge", {}).get("mismatch_reasons")):
                escalation_cause = "judge_injection_signal"
                reason_code = "ESCALATED_THRESHOLD"
                reason_msg = "Transaction requires human review"
            else:
                escalation_cause = "judge_low_confidence"
                reason_code = "ESCALATED_THRESHOLD"
                reason_msg = "Transaction requires human review"
            intent.status = PaymentIntentStatus.ESCALATED
            intent.decision_reasons = [{"code": reason_code, "message": reason_msg, "escalation_cause": escalation_cause}]
            risk_details["escalation_cause"] = escalation_cause
            await session.commit()

            await append_event(session, intent.id, "intent.escalated", {
                "reasons": intent.decision_reasons,
                "timeout_seconds": settings.ESCALATION_TIMEOUT_SECONDS,
            })

            # Publish via event_publisher (intent_status_changed + intent_escalated)
            await event_publisher.publish("intent_status_changed", {
                "intent_id": intent.id, "old_status": "pending", "new_status": "escalated",
                "amount": amount_cents, "merchant": merchant,
            })
            await event_publisher.publish("intent_escalated", {
                "intent_id": intent.id,
                "agent_id": agent_id,
                "amount": amount_cents,
                "currency": currency,
                "merchant": merchant,
                "mandate_id": mandate.mandate_id,
            })

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
        await event_publisher.publish("intent_status_changed", {
            "intent_id": intent.id, "old_status": "pending", "new_status": "approved",
            "amount": amount_cents, "merchant": merchant,
        })

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
        if getattr(settings, "EXECUTION_MODE", "paypal") == "dry_run":
            res["dry_run"] = True
        # Record metrics before returning
        decision_val = res.get("decision", "unknown")
        stopping_layer = res.get("risk", {}).get("denial_cause") or res.get("risk", {}).get("escalation_cause") or "none"
        INTENT_DECISIONS_TOTAL.labels(decision=decision_val, stopping_layer=stopping_layer).inc()
        PIPELINE_LATENCY_SECONDS.observe(time.time() - start_time)

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
