"""PayPal constants fixed strictly to Sandbox.

Live endpoints must never be used in this project.
"""

PAYPAL_SANDBOX_BASE_URL: str = "https://api-m.sandbox.paypal.com"
PAYPAL_OAUTH_URL: str = f"{PAYPAL_SANDBOX_BASE_URL}/v1/oauth2/token"
PAYPAL_PAYOUTS_URL: str = f"{PAYPAL_SANDBOX_BASE_URL}/v1/payments/payouts"
PAYPAL_VERIFY_SIGNATURE_URL: str = f"{PAYPAL_SANDBOX_BASE_URL}/v1/notifications/verify-webhook-signature"
