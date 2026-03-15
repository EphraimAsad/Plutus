"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


class TestLogin:
    """Tests for the login endpoint."""

    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login with valid credentials."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "test@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_password(self, client: AsyncClient, test_user):
        """Test login with wrong password."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    async def test_login_invalid_email(self, client: AsyncClient):
        """Test login with non-existent email."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db_session):
        """Test login with inactive user account."""
        import uuid
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        inactive_user = User(
            id=uuid.uuid4(),
            email="inactive@example.com",
            password_hash=hash_password("testpassword123"),
            full_name="Inactive User",
            role=UserRole.OPERATIONS_ANALYST,
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()

        response = await client.post(
            "/auth/login",
            data={
                "username": "inactive@example.com",
                "password": "testpassword123",
            },
        )
        assert response.status_code == 401


class TestGetCurrentUser:
    """Tests for the get current user endpoint."""

    async def test_get_me_authenticated(self, client: AsyncClient, test_user, auth_headers):
        """Test getting current user with valid token."""
        response = await client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert data["role"] == "operations_analyst"

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        """Test getting current user without token."""
        response = await client.get("/auth/me")
        assert response.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        response = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    async def test_get_me_admin(self, client: AsyncClient, admin_user, admin_auth_headers):
        """Test getting admin user info."""
        response = await client.get("/auth/me", headers=admin_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@example.com"
        assert data["role"] == "admin"

    async def test_get_me_manager(self, client: AsyncClient, manager_user, manager_auth_headers):
        """Test getting manager user info."""
        response = await client.get("/auth/me", headers=manager_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "manager@example.com"
        assert data["role"] == "operations_manager"
