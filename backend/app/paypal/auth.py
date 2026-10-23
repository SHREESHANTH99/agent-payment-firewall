"""PayPal OAuth2 authentication and token management with in-memory caching."""
import asyncio
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.paypal.exceptions import PayPalAuthError
from app.paypal.models import OAuthTokenResponse

logger = logging.getLogger(__name__)

# In-memory token cache
_cached_token: Optional[str] = None
_token_expires_at: float = 0.0
_cache_lock = asyncio.Lock()


def get_oauth_url() -> str:
    """Return the PayPal OAuth2 token endpoint URL based on environment settings."""
    if settings.PAYPAL_MODE.lower() == "live":
        return "https://api-m.paypal.com/v1/oauth2/token"
    return "https://api-m.sandbox.paypal.com/v1/oauth2/token"


def clear_token_cache() -> None:
    """Clear cached token and expiry (useful for testing and token invalidation)."""
    global _cached_token, _token_expires_at
    _cached_token = None
    _token_expires_at = 0.0


async def get_access_token(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
    force_refresh: bool = False,
) -> str:
    """
    Retrieve an OAuth2 bearer access token from PayPal.

    Caches the token in memory until 60 seconds before its declared expiry.
    Raises PayPalAuthError on non-2xx responses, extracting PayPal-Debug-Id.
    Never logs client secrets or raw sensitive credentials.
    """
    global _cached_token, _token_expires_at

    cid = client_id or settings.PAYPAL_CLIENT_ID
    secret = client_secret or settings.PAYPAL_CLIENT_SECRET
    now = time.time()

    async with _cache_lock:
        # Cache until 60 seconds before expiry
        if not force_refresh and _cached_token and now < (_token_expires_at - 60):
            return _cached_token

        url = get_oauth_url()
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {"grant_type": "client_credentials"}

        logger.info("Requesting fresh PayPal OAuth2 access token")

        async def _execute_post(http_client: httpx.AsyncClient) -> httpx.Response:
            return await http_client.post(
                url,
                auth=httpx.BasicAuth(cid, secret),
                headers=headers,
                data=data,
                timeout=30.0,
            )

        if client is not None:
            response = await _execute_post(client)
        else:
            async with httpx.AsyncClient() as default_client:
                response = await _execute_post(default_client)

        debug_id = response.headers.get("paypal-debug-id") or response.headers.get("Paypal-Debug-Id")

        if response.is_error:
            error_details = {}
            error_name = None
            error_message = response.text
            try:
                error_details = response.json()
                error_name = error_details.get("error") or error_details.get("name")
                error_message = (
                    error_details.get("error_description")
                    or error_details.get("message")
                    or response.text
                )
                if not debug_id and "debug_id" in error_details:
                    debug_id = error_details["debug_id"]
            except Exception:
                pass

            logger.error(
                "PayPal OAuth failed with HTTP %s (debug_id=%s)",
                response.status_code,
                debug_id,
            )
            raise PayPalAuthError(
                status_code=response.status_code,
                message=error_message,
                debug_id=debug_id,
                error_name=error_name,
                details=error_details,
            )

        token_data = response.json()
        token_response = OAuthTokenResponse.model_validate(token_data)

        _cached_token = token_response.access_token
        _token_expires_at = time.time() + token_response.expires_in

        logger.info(
            "Acquired PayPal access token (expires in %ds, cached until %ds before expiry)",
            token_response.expires_in,
            60,
        )
        return _cached_token
