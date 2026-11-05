"""Test for cold Redis startup toleration and PostgreSQL budget rebuild."""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from app.models.models import Mandate, MandateStatus, MandatePeriod, PaymentIntent, PaymentIntentStatus
from app.services.budget import budget_service
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_cold_redis_rebuild_from_postgres():
    """Verify that if Redis counters are completely wiped (cold start),

    budget_service.rebuild_from_db reconstructs the active counters from PostgreSQL.
    """
    async with AsyncSessionLocal() as session:
        # Create a mandate with $100 budget
        mandate_id = "cold-rebuild-mandate-test"
        await session.execute(delete(PaymentIntent).where(PaymentIntent.mandate_id == mandate_id))
        await session.execute(delete(Mandate).where(Mandate.mandate_id == mandate_id))
        await session.commit()

        mandate = Mandate(
            mandate_id=mandate_id,
            agent_id="agent-cold-test",
            budget_total=10000,
            per_transaction_cap=5000,
            escalation_threshold=2000,
            period=MandatePeriod.LIFETIME,
            status=MandateStatus.ACTIVE,
            valid_from=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
            allowlist_merchants=["vendor@example.com"],
        )
        session.add(mandate)

        # Add an executed intent of $30 (3000 cents)
        intent = PaymentIntent(
            id="intent-cold-1",
            mandate_id=mandate_id,
            idempotency_key="cold-key-1",
            amount=3000,
            currency="USD",
            merchant="vendor@example.com",
            status=PaymentIntentStatus.EXECUTED,
        )
        session.add(intent)
        await session.commit()

        # Simulate cold Redis: wipe Redis completely
        r = await budget_service.get_redis()
        await r.flushdb()

        # Counter before rebuild is empty
        balance_before = await budget_service.get_balances(mandate_id, "lifetime")
        assert balance_before["spent"] == 0

        # Execute rebuild_from_db
        await budget_service.rebuild_from_db(session)

        # Counter after rebuild reflects PostgreSQL truth ($30 spent)
        balance_after = await budget_service.get_balances(mandate_id, "lifetime")
        assert balance_after["spent"] == 3000

        # Clean up
        await session.execute(delete(PaymentIntent).where(PaymentIntent.mandate_id == mandate_id))
        await session.execute(delete(Mandate).where(Mandate.mandate_id == mandate_id))
        await session.commit()
