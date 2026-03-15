#!/usr/bin/env python3
"""Script to create an admin user."""

import asyncio
import sys
from getpass import getpass

sys.path.insert(0, "/app")

from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.security import hash_password
from app.models.user import User, UserRole


async def create_admin():
    """Create an admin user interactively."""
    print("=== Plutus Admin User Creation ===\n")

    email = input("Email: ").strip()
    full_name = input("Full Name: ").strip()
    password = getpass("Password (min 8 chars): ")
    confirm_password = getpass("Confirm Password: ")

    if password != confirm_password:
        print("Error: Passwords do not match")
        return

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        return

    async with async_session_maker() as session:
        # Check if user exists
        result = await session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"Error: User with email {email} already exists")
            return

        # Create admin user
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(user)
        await session.commit()

        print(f"\nAdmin user created successfully!")
        print(f"  Email: {email}")
        print(f"  Name: {full_name}")
        print(f"  Role: admin")


def main():
    asyncio.run(create_admin())


if __name__ == "__main__":
    main()
