"""Standalone seed script for reproducible demo setup.

Run: python scripts/seed.py

Actions:
  1. Creates all database tables
  2. Seeds the admin user
  3. Seeds a demo customer user
  4. Prints credentials for the jury demonstration

Documents are seeded separately in Phase 2 via: python scripts/seed_documents.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make sure the backend root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, create_tables
from app.core.security import hash_password
from app.models.user import User

logger = structlog.get_logger("seed")


DEMO_CUSTOMER = {
    "email": "customer@demo.com",
    "full_name": "Demo Customer",
    "password": "Customer@123",
    "role": "customer",
}


async def seed_user(db, email: str, full_name: str, password: str, role: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("User already exists", email=email)
        return existing

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    logger.info("Created user", email=email, role=role)
    return user


async def main() -> None:
    logger.info("Seeding database", url=settings.database_url[:40])

    # Import models so metadata is populated
    import app.models.user          # noqa: F401
    import app.models.document      # noqa: F401
    import app.models.conversation  # noqa: F401
    import app.models.resolution    # noqa: F401

    await create_tables()
    logger.info("Tables created / verified")

    async with AsyncSessionLocal() as db:
        await seed_user(
            db,
            email=settings.admin_email,
            full_name=settings.admin_name,
            password=settings.admin_password,
            role="admin",
        )
        await seed_user(
            db,
            email=DEMO_CUSTOMER["email"],
            full_name=DEMO_CUSTOMER["full_name"],
            password=DEMO_CUSTOMER["password"],
            role=DEMO_CUSTOMER["role"],
        )
        await db.commit()

    print("\n" + "=" * 55)
    print("  TruthGuard v2 — Demo Credentials")
    print("=" * 55)
    print(f"  Admin     : {settings.admin_email}")
    print(f"  Password  : {settings.admin_password}")
    print(f"  Customer  : {DEMO_CUSTOMER['email']}")
    print(f"  Password  : {DEMO_CUSTOMER['password']}")
    print("=" * 55)
    print("  Next: python scripts/seed_documents.py")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
