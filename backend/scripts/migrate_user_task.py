"""Add the trusted-context retention column to existing development databases."""
import asyncio

from sqlalchemy import text

from app.core.database import engine


async def main() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE payment_intents ADD COLUMN IF NOT EXISTS user_task TEXT"))


if __name__ == "__main__":
    asyncio.run(main())
