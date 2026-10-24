"""Deterministic policy and risk rules evaluation engine."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional, Union


@dataclass
class RuleFailure:
    code: str
    message: str


@dataclass
class RuleResult:
    passed: bool
    escalate: bool = False
    failures: list[dict[str, str]] = field(default_factory=list)


def to_cents(val: Union[int, float, str, Decimal, None]) -> Optional[int]:
    """Convert a dollar/currency amount to integer cents, rejecting >2 decimal places."""
    if val is None:
        return None
    if isinstance(val, int):
        return val * 100
    d = Decimal(str(val))
    if d.as_tuple().exponent < -2:
        raise ValueError("Amount has more than 2 decimal places")
    return int((d * 100).to_integral_value())


def evaluate_rules(
    mandate: Any,
    intent_fields: Mapping[str, Any],
    now: Optional[datetime] = None,
) -> RuleResult:
    """
    Evaluate deterministic rules for an incoming payment intent against a mandate.
    Pure function: no I/O, no database/network calls.
    Evaluates ALL rules without short-circuiting so all failures are reported together.

    Rules:
    1. Mandate active (frozen/revoked/expired codes)
    2. Within valid_from/valid_until
    3. Currency allowed
    4. Amount > 0
    5. Amount <= per_transaction_cap
    6. Merchant in allowlist (case-insensitive email matching)
    7. Amount > escalation_threshold sets escalate=True (not a failure)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    failures: list[dict[str, str]] = []
    escalate = False

    # 1. Mandate active check
    mandate_status = getattr(mandate, "status", None)
    if isinstance(mandate_status, str):
        mandate_status = mandate_status.lower()
    else:
        mandate_status = str(mandate_status).lower() if mandate_status else "unknown"

    if mandate_status == "frozen":
        failures.append({"code": "MANDATE_FROZEN", "message": "Mandate is currently frozen"})
    elif mandate_status == "revoked":
        failures.append({"code": "MANDATE_REVOKED", "message": "Mandate has been revoked"})
    elif mandate_status == "expired":
        failures.append({"code": "MANDATE_EXPIRED", "message": "Mandate is marked as expired"})
    elif mandate_status != "active":
        failures.append({"code": "MANDATE_INACTIVE", "message": f"Mandate status '{mandate_status}' is not active"})

    # 2. Validity window check
    valid_from = getattr(mandate, "valid_from", None)
    valid_until = getattr(mandate, "valid_until", None)

    if valid_from:
        vf = valid_from if valid_from.tzinfo else valid_from.replace(tzinfo=timezone.utc)
        if now < vf:
            failures.append({
                "code": "MANDATE_NOT_YET_VALID",
                "message": f"Intent timestamp {now.isoformat()} is before mandate valid_from {vf.isoformat()}",
            })

    if valid_until:
        vu = valid_until if valid_until.tzinfo else valid_until.replace(tzinfo=timezone.utc)
        if now > vu:
            failures.append({
                "code": "MANDATE_VALIDITY_EXPIRED",
                "message": f"Intent timestamp {now.isoformat()} is after mandate valid_until {vu.isoformat()}",
            })

    # 3. Currency allowed
    currency = intent_fields.get("currency")
    if currency:
        currency = str(currency).upper()
    allowed_currencies = getattr(mandate, "allowed_currencies", None) or ["USD"]
    allowed_upper = [str(c).upper() for c in allowed_currencies]

    if not currency or currency not in allowed_upper:
        failures.append({
            "code": "CURRENCY_NOT_ALLOWED",
            "message": f"Currency '{currency}' is not in allowed currencies: {allowed_upper}",
        })

    # 4 & 5. Amount check (amount > 0 and amount <= per_transaction_cap)
    amount_raw = intent_fields.get("amount")
    amount_cents: Optional[int] = None
    try:
        if isinstance(amount_raw, int) and "amount_cents" in intent_fields:
            amount_cents = amount_raw
        elif isinstance(amount_raw, int) and amount_raw > 1000 and "cents" in str(intent_fields):
            amount_cents = amount_raw
        else:
            # Check if intent_fields explicitly provided amount_cents
            if "amount_cents" in intent_fields:
                amount_cents = int(intent_fields["amount_cents"])
            else:
                amount_cents = to_cents(amount_raw)
    except Exception as e:
        failures.append({"code": "INVALID_AMOUNT", "message": f"Invalid amount format: {e}"})

    per_cap = getattr(mandate, "per_transaction_cap", None)
    # per_cap is in cents
    if amount_cents is not None:
        if amount_cents <= 0:
            failures.append({"code": "AMOUNT_NOT_POSITIVE", "message": "Transaction amount must be strictly greater than 0"})
        elif per_cap is not None and amount_cents > per_cap:
            failures.append({
                "code": "PER_TRANSACTION_CAP_EXCEEDED",
                "message": f"Amount {amount_cents} cents exceeds per-transaction cap of {per_cap} cents",
            })

    # 6. Merchant allowlist check (case-insensitive email/domain matching)
    merchant = intent_fields.get("merchant")
    merchant_clean = str(merchant).strip().lower() if merchant else ""
    allowlist = getattr(mandate, "allowlist_merchants", None) or []
    allowlist_clean = [str(m).strip().lower() for m in allowlist]

    if not merchant_clean or merchant_clean not in allowlist_clean:
        failures.append({
            "code": "MERCHANT_NOT_ALLOWLISTED",
            "message": f"Merchant '{merchant}' is not in mandate allowlist",
        })

    # 7. Escalation threshold check (amount > escalation_threshold sets escalate=True, NOT a failure)
    escalation_thresh = getattr(mandate, "escalation_threshold", None)
    if escalation_thresh is not None and amount_cents is not None:
        if amount_cents > escalation_thresh:
            escalate = True

    passed = len(failures) == 0
    return RuleResult(passed=passed, escalate=escalate, failures=failures)
