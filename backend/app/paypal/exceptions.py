"""Custom exceptions for PayPal API interactions."""
from typing import Any, Optional


class PayPalAPIError(Exception):
    """Exception raised when a PayPal API call returns a non-2xx status code."""

    def __init__(
        self,
        status_code: int,
        message: str,
        debug_id: Optional[str] = None,
        error_name: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.debug_id = debug_id
        self.error_name = error_name
        self.details = details

        parts = [f"PayPal API error HTTP {status_code}"]
        if error_name:
            parts.append(f"[{error_name}]")
        parts.append(f"- {message}")
        if debug_id:
            parts.append(f"(PayPal-Debug-ID: {debug_id})")

        super().__init__(" ".join(parts))


class PayPalAuthError(PayPalAPIError):
    """Exception raised when authentication fails with PayPal."""
    pass
