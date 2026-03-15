#!/usr/bin/env python3
"""Script to seed initial admin user for Plutus."""

import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User, UserRole


async def seed_admin():
    """Create the admin user if not exists."""
    print("=== Plutus Initial Setup ===\n")

    async with async_session_maker() as session:
        # Check if admin already exists
        result = await session.execute(
            select(User).where(User.email == "admin@plutus-app.com")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("Admin user already exists.")
            return

        # Create admin user
        print("Creating admin user...")
        admin = User(
            email="admin@plutus-app.com",
            full_name="System Administrator",
            password_hash=hash_password("admin123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()

        print("\n=== Setup Complete ===")
        print("\nAdmin credentials:")
        print("  Email: admin@plutus-app.com")
        print("  Password: admin123!")
        print("\nPlease change the password after first login.")


def main():
    asyncio.run(seed_admin())


if __name__ == "__main__":
    main()
