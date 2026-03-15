"""Tests for exception management endpoints."""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exception import (
    Exception as ExceptionModel,
    ExceptionStatus,
    ExceptionSeverity,
    ExceptionType,
    ExceptionNote,
)


@pytest.fixture
async def test_exception(db_session: AsyncSession) -> ExceptionModel:
    """Create a test exception."""
    exception = ExceptionModel(
        id=uuid.uuid4(),
        exception_type=ExceptionType.AMOUNT_MISMATCH,
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        title="Amount mismatch between Bank and Ledger",
        description="Transaction TXN001 has $100.00 in bank but $95.00 in ledger",
        related_record_ids=["record-1", "record-2"],
        metadata_json={"bank_amount": 100.00, "ledger_amount": 95.00},
    )
    db_session.add(exception)
    await db_session.commit()
    await db_session.refresh(exception)
    return exception


@pytest.fixture
async def assigned_exception(
    db_session: AsyncSession, test_user
) -> ExceptionModel:
    """Create an exception assigned to test user."""
    exception = ExceptionModel(
        id=uuid.uuid4(),
        exception_type=ExceptionType.DATE_MISMATCH,
        severity=ExceptionSeverity.MEDIUM,
        status=ExceptionStatus.IN_REVIEW,
        title="Date mismatch",
        description="Settlement date differs by 3 days",
        assigned_to=test_user.id,
        related_record_ids=["record-3"],
    )
    db_session.add(exception)
    await db_session.commit()
    await db_session.refresh(exception)
    return exception


class TestListExceptions:
    """Tests for listing exceptions."""

    async def test_list_exceptions(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test listing exceptions."""
        response = await client.get("/exceptions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1

    async def test_list_exceptions_filter_status(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test filtering exceptions by status."""
        response = await client.get(
            "/exceptions?status=open",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["status"] == "open" for e in data["items"])

    async def test_list_exceptions_filter_severity(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test filtering exceptions by severity."""
        response = await client.get(
            "/exceptions?severity=high",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["severity"] == "high" for e in data["items"])

    async def test_list_exceptions_filter_type(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test filtering exceptions by type."""
        response = await client.get(
            "/exceptions?exception_type=amount_mismatch",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["exception_type"] == "amount_mismatch" for e in data["items"])

    async def test_list_exceptions_filter_assigned(
        self, client: AsyncClient, test_user, assigned_exception, auth_headers
    ):
        """Test filtering exceptions by assignee."""
        response = await client.get(
            f"/exceptions?assigned_to={test_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["assigned_to"] == str(test_user.id) for e in data["items"])

    async def test_list_exceptions_pagination(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test exception pagination."""
        response = await client.get(
            "/exceptions?limit=10&offset=0",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0


class TestGetException:
    """Tests for getting individual exceptions."""

    async def test_get_exception(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test getting exception by ID."""
        response = await client.get(
            f"/exceptions/{test_exception.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_exception.id)
        assert data["exception_type"] == "amount_mismatch"
        assert data["severity"] == "high"
        assert data["status"] == "open"

    async def test_get_exception_not_found(self, client: AsyncClient, auth_headers):
        """Test getting non-existent exception."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/exceptions/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestAssignException:
    """Tests for assigning exceptions."""

    async def test_assign_exception(
        self, client: AsyncClient, test_exception, test_user, auth_headers
    ):
        """Test assigning exception to user."""
        response = await client.post(
            f"/exceptions/{test_exception.id}/assign?assignee_id={test_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "assigned" in response.json()["message"].lower()

    async def test_assign_sets_in_review(
        self, client: AsyncClient, db_session, test_exception, test_user, auth_headers
    ):
        """Test that assigning sets status to in_review."""
        response = await client.post(
            f"/exceptions/{test_exception.id}/assign?assignee_id={test_user.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify status changed
        await db_session.refresh(test_exception)
        assert test_exception.status == ExceptionStatus.IN_REVIEW


class TestResolveException:
    """Tests for resolving exceptions."""

    async def test_resolve_exception(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test resolving exception."""
        response = await client.post(
            f"/exceptions/{test_exception.id}/resolve",
            json={"resolution_note": "Verified and corrected in source system"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "resolved" in response.json()["message"].lower()

    async def test_resolve_sets_resolver(
        self, client: AsyncClient, db_session, test_exception, test_user, auth_headers
    ):
        """Test that resolving sets resolved_by and resolved_at."""
        await client.post(
            f"/exceptions/{test_exception.id}/resolve",
            json={"resolution_note": "Fixed"},
            headers=auth_headers,
        )

        await db_session.refresh(test_exception)
        assert test_exception.status == ExceptionStatus.RESOLVED
        assert test_exception.resolved_by == test_user.id
        assert test_exception.resolved_at is not None
        assert test_exception.resolution_note == "Fixed"


class TestDismissException:
    """Tests for dismissing exceptions."""

    async def test_dismiss_exception(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test dismissing exception."""
        response = await client.post(
            f"/exceptions/{test_exception.id}/dismiss",
            json={"resolution_note": "False positive - timing issue"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "dismissed" in response.json()["message"].lower()

    async def test_dismiss_sets_status(
        self, client: AsyncClient, db_session, test_exception, auth_headers
    ):
        """Test that dismiss sets status correctly."""
        await client.post(
            f"/exceptions/{test_exception.id}/dismiss",
            json={"resolution_note": "Not an issue"},
            headers=auth_headers,
        )

        await db_session.refresh(test_exception)
        assert test_exception.status == ExceptionStatus.DISMISSED


class TestEscalateException:
    """Tests for escalating exceptions."""

    async def test_escalate_exception(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test escalating exception."""
        response = await client.post(
            f"/exceptions/{test_exception.id}/escalate",
            json={"resolution_note": "Requires manager approval"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "escalated" in response.json()["message"].lower()

    async def test_escalate_sets_status(
        self, client: AsyncClient, db_session, test_exception, auth_headers
    ):
        """Test that escalate sets status correctly."""
        await client.post(
            f"/exceptions/{test_exception.id}/escalate",
            json={},
            headers=auth_headers,
        )

        await db_session.refresh(test_exception)
        assert test_exception.status == ExceptionStatus.ESCALATED


class TestExceptionNotes:
    """Tests for exception notes."""

    async def test_add_note(
        self, client: AsyncClient, test_exception, auth_headers
    ):
        """Test adding a note to exception."""
        response = await client.post(
            f"/exceptions/{test_exception.id}/notes",
            json={"content": "Investigating this issue"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Investigating this issue"
        assert data["exception_id"] == str(test_exception.id)

    async def test_get_notes(
        self, client: AsyncClient, db_session, test_exception, test_user, auth_headers
    ):
        """Test getting notes for exception."""
        # Add a note first
        note = ExceptionNote(
            exception_id=test_exception.id,
            user_id=test_user.id,
            content="Test note content",
        )
        db_session.add(note)
        await db_session.commit()

        response = await client.get(
            f"/exceptions/{test_exception.id}/notes",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["content"] == "Test note content"

    async def test_add_note_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Test adding note to non-existent exception."""
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/exceptions/{fake_id}/notes",
            json={"content": "This should fail"},
            headers=auth_headers,
        )
        assert response.status_code == 404
