"""PayPal Payouts v1 API integration for autonomous agent disbursements."""
from decimal import Decimal
import logging
from typing import Any, Optional, Union

import httpx

from app.core.config import settings
from app.paypal.auth import get_access_token
from app.paypal.exceptions import PayPalAPIError
from app.paypal.models import (
    CreatePayoutRequest,
    PayoutBatchDetails,
    PayoutBatchHeader,
    PayoutItem,
    PayoutItemAmount,
    PayoutResponse,
    SenderBatchHeader,
)

logger = logging.getLogger(__name__)


def get_payouts_base_url() -> str:
    """Return the PayPal Payouts API base URL according to mode."""
    if settings.PAYPAL_MODE.lower() == "live":
        return "https://api-m.paypal.com/v1/payments/payouts"
    return "https://api-m.sandbox.paypal.com/v1/payments/payouts"


def _format_amount(amount: Union[str, float, int, Decimal]) -> str:
    """Format amount as a 2-decimal-place string suitable for PayPal."""
    if isinstance(amount, Decimal):
        return f"{amount:.2f}"
    if isinstance(amount, (int, float)):
        return f"{float(amount):.2f}"
    # Try parsing string to float or Decimal to ensure consistent 2-decimal formatting
    try:
        val = float(amount)
        return f"{val:.2f}"
    except (ValueError, TypeError):
        return str(amount)


def _extract_error_details(response: httpx.Response) -> tuple[str, Optional[str], Optional[str], dict[str, Any]]:
    """Extract message, debug_id, name, and details dictionary from a PayPal error response."""
    debug_id = response.headers.get("paypal-debug-id") or response.headers.get("Paypal-Debug-Id")
    error_details: dict[str, Any] = {}
    error_name: Optional[str] = None
    error_message: str = response.text

    try:
        error_details = response.json()
        error_name = error_details.get("name") or error_details.get("error")
        error_message = (
            error_details.get("message")
            or error_details.get("error_description")
            or response.text
        )
        if not debug_id and "debug_id" in error_details:
            debug_id = error_details["debug_id"]
    except Exception:
        pass

    return error_message, debug_id, error_name, error_details


async def create_payout(
    idempotency_key: str,
    receiver: str,
    amount: Union[str, float, int, Decimal],
    currency: str = "USD",
    note: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> PayoutResponse:
    """
    Create a single-recipient payout batch via PayPal Payouts API.

    Args:
        idempotency_key: Unique identifier used for sender_batch_id and PayPal-Request-Id header.
        receiver: Target email address of the recipient.
        amount: Payment amount (formatted to 2 decimal places).
        currency: 3-letter currency code (default: 'USD').
        note: Optional note to the receiver or batch reference.
        client: Optional httpx.AsyncClient instance for testing or connection reuse.

    Returns:
        PayoutResponse with batch_id and batch_status (supports tuple unpacking).

    Raises:
        PayPalAPIError: On non-2xx responses, extracting PayPal-Debug-Id.
    """
    token = await get_access_token(client=client)
    formatted_amount = _format_amount(amount)

    payout_request = CreatePayoutRequest(
        sender_batch_header=SenderBatchHeader(
            sender_batch_id=idempotency_key,
            email_subject="Payment disbursement from Agent Payment Firewall",
            email_message=note or "Autonomous agent authorized disbursement",
            recipient_type="EMAIL",
        ),
        items=[
            PayoutItem(
                recipient_type="EMAIL",
                amount=PayoutItemAmount(value=formatted_amount, currency=currency),
                receiver=receiver,
                note=note,
                sender_item_id=idempotency_key,
            )
        ],
    )

    url = get_payouts_base_url()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "PayPal-Request-Id": idempotency_key,
    }

    logger.info(
        "Creating payout with idempotency_key=%s, receiver=%s, amount=%s %s",
        idempotency_key,
        receiver,
        formatted_amount,
        currency,
    )

    async def _post(http_client: httpx.AsyncClient) -> httpx.Response:
        return await http_client.post(
            url,
            headers=headers,
            json=payout_request.model_dump(exclude_none=True),
            timeout=30.0,
        )

    if client is not None:
        response = await _post(client)
    else:
        async with httpx.AsyncClient() as default_client:
            response = await _post(default_client)

    if response.is_error:
        error_message, debug_id, error_name, error_details = _extract_error_details(response)
        logger.error(
            "PayPal create_payout failed with HTTP %s (debug_id=%s)",
            response.status_code,
            debug_id,
        )
        raise PayPalAPIError(
            status_code=response.status_code,
            message=error_message,
            debug_id=debug_id,
            error_name=error_name,
            details=error_details,
        )

    data = response.json()
    batch_header = data.get("batch_header", {})
    batch_id = batch_header.get("payout_batch_id", "")
    batch_status = batch_header.get("batch_status", "")

    logger.info("Successfully created payout batch_id=%s status=%s", batch_id, batch_status)

    header_model = PayoutBatchHeader.model_validate(batch_header) if batch_header else None
    return PayoutResponse(
        batch_id=batch_id,
        batch_status=batch_status,
        batch_header=header_model,
        links=data.get("links"),
    )


async def get_payout_status(
    batch_id: str,
    client: Optional[httpx.AsyncClient] = None,
) -> PayoutBatchDetails:
    """
    Retrieve payout batch details and item statuses by batch_id.

    Args:
        batch_id: PayPal payout batch identifier.
        client: Optional httpx.AsyncClient instance.

    Returns:
        PayoutBatchDetails with status, timestamps, and item array.

    Raises:
        PayPalAPIError: On non-2xx responses, extracting PayPal-Debug-Id.
    """
    token = await get_access_token(client=client)
    url = f"{get_payouts_base_url()}/{batch_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    logger.info("Fetching payout status for batch_id=%s", batch_id)

    async def _get(http_client: httpx.AsyncClient) -> httpx.Response:
        return await http_client.get(url, headers=headers, timeout=30.0)

    if client is not None:
        response = await _get(client)
    else:
        async with httpx.AsyncClient() as default_client:
            response = await _get(default_client)

    if response.is_error:
        error_message, debug_id, error_name, error_details = _extract_error_details(response)
        logger.error(
            "PayPal get_payout_status failed with HTTP %s (debug_id=%s)",
            response.status_code,
            debug_id,
        )
        raise PayPalAPIError(
            status_code=response.status_code,
            message=error_message,
            debug_id=debug_id,
            error_name=error_name,
            details=error_details,
        )

    data = response.json()
    batch_header = data.get("batch_header", {})
    sender_header = batch_header.get("sender_batch_header", {})

    return PayoutBatchDetails(
        batch_id=batch_header.get("payout_batch_id", batch_id),
        batch_status=batch_header.get("batch_status", "UNKNOWN"),
        time_created=batch_header.get("time_created"),
        time_completed=batch_header.get("time_completed"),
        sender_batch_id=sender_header.get("sender_batch_id"),
        items=data.get("items", []),
        raw_response=data,
    )
