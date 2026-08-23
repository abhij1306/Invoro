"""Apply migrations and perform the explicitly enabled one-shot admin bootstrap."""

import asyncio

from app.core.migrations import apply_pending_migrations_async
from app.core.database import SessionLocal, dispose_engine
from app.services.auth_service import bootstrap_admin_user


async def init_database():
    """Upgrade the schema, then bootstrap the configured admin when enabled."""
    try:
        await apply_pending_migrations_async()
        async with SessionLocal() as session:
            admin = await bootstrap_admin_user(session)
        print("Database migrations applied successfully!")
        print(
            "Admin bootstrap completed."
            if admin is not None
            else "Admin bootstrap skipped."
        )
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(init_database())
