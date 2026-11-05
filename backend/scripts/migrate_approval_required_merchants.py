"""Add approval_required_merchants column to mandates table."""
import asyncio
from sqlalchemy import text
from app.core.database import engine


async def main() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE mandates ADD COLUMN IF NOT EXISTS approval_required_merchants JSONB DEFAULT '[]'::jsonb"))


if __name__ == "__main__":
    asyncio.run(main())
