"""Operational script to execute a test sandbox payout using configured PayPal credentials."""
import asyncio
from pathlib import Path
import sys
import uuid

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.config import settings
from app.paypal.exceptions import PayPalAPIError
from app.paypal.payouts import create_payout


async def run_test_payout() -> None:
    """Create one sandbox payout to PAYPAL_TEST_RECEIVER_EMAIL and print batch details."""
    idempotency_key = str(uuid.uuid4())
    receiver = settings.PAYPAL_TEST_RECEIVER_EMAIL
    amount = 1.00
    currency = "USD"
    note = "Sandbox test payout from Agent Payment Firewall"

    print("=== Agent Payment Firewall: Sandbox Payout Test ===")
    print(f"Receiver:        {receiver}")
    print(f"Amount:          {amount:.2f} {currency}")
    print(f"Idempotency Key: {idempotency_key}")

    try:
        response = await create_payout(
            idempotency_key=idempotency_key,
            receiver=receiver,
            amount=amount,
            currency=currency,
            note=note,
        )
        print("\n--- Payout Submission Success ---")
        print(f"Batch ID:     {response.batch_id}")
        print(f"Batch Status: {response.batch_status}")
    except PayPalAPIError as err:
        print(f"\n--- Payout Submission Failed ---")
        print(f"Status Code:  {err.status_code}")
        print(f"Error Name:   {err.error_name}")
        print(f"Debug ID:     {err.debug_id}")
        print(f"Message:      {err.message}")
        sys.exit(1)


def main() -> None:
    asyncio.run(run_test_payout())


if __name__ == "__main__":
    main()
