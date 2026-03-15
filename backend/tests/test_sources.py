"""Tests for source system management endpoints."""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import SourceSystem, SourceSchemaMapping, SourceType


@pytest.fixture
async def test_source(db_session: AsyncSession, admin_user) -> SourceSystem:
    """Create a test source system."""
    source = SourceSystem(
        id=uuid.uuid4(),
        name="Test Bank",
        source_type=SourceType.BANK,
        description="Test bank source",
        is_active=True,
        config_json={"date_format": "MM/DD/YYYY"},
        created_by=admin_user.id,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest.fixture
async def test_source_with_mapping(db_session: AsyncSession, test_source) -> SourceSystem:
    """Create a test source with schema mapping."""
    mapping = SourceSchemaMapping(
        source_system_id=test_source.id,
        version=1,
        mapping_json={
            "amount": "transaction_amount",
            "date": "transaction_date",
            "reference": "ref_number",
        },
        is_active=True,
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(test_source)
    return test_source


class TestListSources:
    """Tests for listing source systems."""

    async def test_list_sources_authenticated(
        self, client: AsyncClient, test_source, auth_headers
    ):
        """Test listing sources as authenticated user."""
        response = await client.get("/sources", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(s["name"] == "Test Bank" for s in data)

    async def test_list_sources_unauthenticated(self, client: AsyncClient):
        """Test listing sources without authentication."""
        response = await client.get("/sources")
        assert response.status_code == 401

    async def test_list_sources_filters_inactive(
        self, client: AsyncClient, db_session, admin_user, auth_headers
    ):
        """Test that inactive sources are filtered by default."""
        inactive = SourceSystem(
            name="Inactive Source",
            source_type=SourceType.LEDGER,
            is_active=False,
            created_by=admin_user.id,
        )
        db_session.add(inactive)
        await db_session.commit()

        response = await client.get("/sources", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert not any(s["name"] == "Inactive Source" for s in data)

    async def test_list_sources_include_inactive(
        self, client: AsyncClient, db_session, admin_user, auth_headers
    ):
        """Test listing including inactive sources."""
        inactive = SourceSystem(
            name="Inactive Source 2",
            source_type=SourceType.LEDGER,
            is_active=False,
            created_by=admin_user.id,
        )
        db_session.add(inactive)
        await db_session.commit()

        response = await client.get("/sources?active_only=false", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert any(s["name"] == "Inactive Source 2" for s in data)


class TestCreateSource:
    """Tests for creating source systems."""

    async def test_create_source_admin(self, client: AsyncClient, admin_auth_headers):
        """Test creating source as admin."""
        response = await client.post(
            "/sources",
            json={
                "name": "New Bank Source",
                "source_type": "bank",
                "description": "A new bank source",
                "config_json": {"timezone": "UTC"},
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Bank Source"
        assert data["source_type"] == "bank"
        assert data["is_active"] is True

    async def test_create_source_non_admin(self, client: AsyncClient, auth_headers):
        """Test creating source as non-admin fails."""
        response = await client.post(
            "/sources",
            json={
                "name": "Unauthorized Source",
                "source_type": "ledger",
            },
            headers=auth_headers,
        )
        assert response.status_code == 403

    async def test_create_source_duplicate_name(
        self, client: AsyncClient, test_source, admin_auth_headers
    ):
        """Test creating source with duplicate name fails."""
        response = await client.post(
            "/sources",
            json={
                "name": "Test Bank",  # Same as test_source
                "source_type": "bank",
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_create_source_invalid_type(
        self, client: AsyncClient, admin_auth_headers
    ):
        """Test creating source with invalid type fails."""
        response = await client.post(
            "/sources",
            json={
                "name": "Invalid Type Source",
                "source_type": "invalid_type",
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 400


class TestGetSource:
    """Tests for getting individual source systems."""

    async def test_get_source(
        self, client: AsyncClient, test_source, auth_headers
    ):
        """Test getting a source by ID."""
        response = await client.get(
            f"/sources/{test_source.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Bank"
        assert data["source_type"] == "bank"

    async def test_get_source_not_found(self, client: AsyncClient, auth_headers):
        """Test getting non-existent source."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/sources/{fake_id}", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateSource:
    """Tests for updating source systems."""

    async def test_update_source_admin(
        self, client: AsyncClient, test_source, admin_auth_headers
    ):
        """Test updating source as admin."""
        response = await client.put(
            f"/sources/{test_source.id}",
            json={
                "name": "Updated Bank",
                "description": "Updated description",
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Bank"
        assert data["description"] == "Updated description"

    async def test_update_source_non_admin(
        self, client: AsyncClient, test_source, auth_headers
    ):
        """Test updating source as non-admin fails."""
        response = await client.put(
            f"/sources/{test_source.id}",
            json={"name": "Unauthorized Update"},
            headers=auth_headers,
        )
        assert response.status_code == 403

    async def test_deactivate_source(
        self, client: AsyncClient, test_source, admin_auth_headers
    ):
        """Test deactivating a source."""
        response = await client.put(
            f"/sources/{test_source.id}",
            json={"is_active": False},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False


class TestSchemaMapping:
    """Tests for schema mapping operations."""

    async def test_create_schema_mapping(
        self, client: AsyncClient, test_source, admin_auth_headers
    ):
        """Test creating a schema mapping."""
        response = await client.post(
            f"/sources/{test_source.id}/schema-mapping",
            json={
                "mapping_json": {
                    "amount": "amt",
                    "date": "txn_date",
                    "reference": "ref_id",
                },
                "is_active": True,
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == 1
        assert data["is_active"] is True
        assert data["mapping_json"]["amount"] == "amt"

    async def test_create_multiple_mappings(
        self, client: AsyncClient, test_source_with_mapping, admin_auth_headers
    ):
        """Test creating additional mapping versions."""
        response = await client.post(
            f"/sources/{test_source_with_mapping.id}/schema-mapping",
            json={
                "mapping_json": {"amount": "new_amt"},
                "is_active": True,
            },
            headers=admin_auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["version"] == 2

    async def test_list_schema_mappings(
        self, client: AsyncClient, test_source_with_mapping, auth_headers
    ):
        """Test listing schema mappings."""
        response = await client.get(
            f"/sources/{test_source_with_mapping.id}/schema-mappings",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_activate_schema_mapping(
        self, client: AsyncClient, test_source_with_mapping, db_session, admin_auth_headers
    ):
        """Test activating a specific schema mapping."""
        # Create a second mapping
        mapping2 = SourceSchemaMapping(
            source_system_id=test_source_with_mapping.id,
            version=2,
            mapping_json={"amount": "v2_amount"},
            is_active=False,
        )
        db_session.add(mapping2)
        await db_session.commit()

        response = await client.post(
            f"/sources/{test_source_with_mapping.id}/schema-mapping/{mapping2.id}/activate",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        assert "v2" in response.json()["message"]
