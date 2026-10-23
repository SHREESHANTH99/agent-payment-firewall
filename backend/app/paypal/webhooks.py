"""PayPal webhook signature verification."""
import json
import logging
from collections.abc import Mapping
from typing import Optional

import httpx

from app.core.config import settings
from app.paypal.auth import get_access_token

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = (
    "paypal-auth-algo",
    "paypal-cert-url",
    "paypal-transmission-id",
    "paypal-transmission-sig",
    "paypal-transmission-time",
)


def get_verify_signature_url() -> str:
    """Return the PayPal verify-webhook-signature endpoint URL."""
    if settings.PAYPAL_MODE.lower() == "live":
        return "https://api-m.paypal.com/v1/notifications/verify-webhook-signature"
    return "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"


async def verify_webhook(
    headers: Mapping[str, str],
    raw_body: bytes,
    client: Optional[httpx.AsyncClient] = None,
) -> bool:
    """
    Verify the authenticity of an incoming PayPal webhook event.

    Args:
        headers: Request headers containing PayPal signature headers.
        raw_body: Unmodified raw request body bytes.
        client: Optional httpx.AsyncClient instance for testing.

    Returns:
        bool: True if signature is cryptographically verified by PayPal, False otherwise.
    """
    if not settings.PAYPAL_WEBHOOK_ID:
        logger.warning("PayPal webhook verification skipped: PAYPAL_WEBHOOK_ID is empty")
        return False

    # Read headers case-insensitively
    headers_lower = {k.lower(): v for k, v in headers.items()}
    missing_headers = [h for h in REQUIRED_HEADERS if not headers_lower.get(h)]
    if missing_headers:
        logger.warning("PayPal webhook missing required signature headers: %s", missing_headers)
        return False

    # Parse raw body as JSON for webhook_event
    try:
        webhook_event = json.loads(raw_body.decode("utf-8"))
    except Exception:
        logger.warning("PayPal webhook raw body is not valid JSON")
        return False

    payload = {
        "auth_algo": headers_lower["paypal-auth-algo"],
        "cert_url": headers_lower["paypal-cert-url"],
        "transmission_id": headers_lower["paypal-transmission-id"],
        "transmission_sig": headers_lower["paypal-transmission-sig"],
        "transmission_time": headers_lower["paypal-transmission-time"],
        "webhook_id": settings.PAYPAL_WEBHOOK_ID,
        "webhook_event": webhook_event,
    }

    url = get_verify_signature_url()

    try:
        token = await get_access_token(client=client)
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async def _execute_verify(http_client: httpx.AsyncClient) -> httpx.Response:
            return await http_client.post(url, headers=req_headers, json=payload, timeout=30.0)

        if client is not None:
            response = await _execute_verify(client)
        else:
            async with httpx.AsyncClient() as default_client:
                response = await _execute_verify(default_client)

        if response.is_error:
            logger.warning(
                "PayPal webhook verification API returned HTTP %d",
                response.status_code,
            )
            return False

        data = response.json()
        verification_status = data.get("verification_status")
        if verification_status == "SUCCESS":
            return True

        logger.warning(
            "PayPal webhook verification status: %s",
            verification_status,
        )
        return False

    except Exception as exc:
        logger.warning("PayPal webhook verification failed with error: %s", type(exc).__name__)
        return False
