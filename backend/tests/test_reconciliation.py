"""Tests for reconciliation endpoints."""

import pytest
import uuid
from decimal import Decimal
from datetime import date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import SourceSystem, SourceSchemaMapping, SourceType
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationStatus,
    MatchCandidate,
    MatchType,
    MatchDecisionStatus,
    UnmatchedRecord,
)
from app.models.transaction import CanonicalRecord


@pytest.fixture
async def left_source(db_session: AsyncSession, admin_user) -> SourceSystem:
    """Create left source system (Bank)."""
    source = SourceSystem(
        id=uuid.uuid4(),
        name="Test Bank Left",
        source_type=SourceType.BANK,
        is_active=True,
        created_by=admin_user.id,
    )
    db_session.add(source)
    mapping = SourceSchemaMapping(
        source_system_id=source.id,
        version=1,
        mapping_json={"amount": "amt"},
        is_active=True,
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest.fixture
async def right_source(db_session: AsyncSession, admin_user) -> SourceSystem:
    """Create right source system (Ledger)."""
    source = SourceSystem(
        id=uuid.uuid4(),
        name="Test Ledger Right",
        source_type=SourceType.LEDGER,
        is_active=True,
        created_by=admin_user.id,
    )
    db_session.add(source)
    mapping = SourceSchemaMapping(
        source_system_id=source.id,
        version=1,
        mapping_json={"amount": "amt"},
        is_active=True,
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest.fixture
async def test_reconciliation_run(
    db_session: AsyncSession, left_source, right_source, test_user
) -> ReconciliationRun:
    """Create a test reconciliation run."""
    run = ReconciliationRun(
        id=uuid.uuid4(),
        name="Test Reconciliation Run",
        status=ReconciliationStatus.COMPLETED,
        parameters_json={
            "left_source_id": str(left_source.id),
            "right_source_id": str(right_source.id),
        },
        triggered_by=test_user.id,
        total_left_records=100,
        total_right_records=100,
        total_matched=90,
        total_unmatched=10,
        total_exceptions=5,
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run


@pytest.fixture
async def test_records(
    db_session: AsyncSession, left_source, right_source
) -> tuple[CanonicalRecord, CanonicalRecord]:
    """Create test canonical records."""
    left_record = CanonicalRecord(
        id=uuid.uuid4(),
        source_system_id=left_source.id,
        record_type="transaction",
        external_record_id="TXN001",
        record_date=date(2024, 1, 15),
        currency="USD",
        amount=Decimal("1000.00"),
        counterparty="ACME Corp",
        description="Payment",
        record_hash="hash123",
    )
    right_record = CanonicalRecord(
        id=uuid.uuid4(),
        source_system_id=right_source.id,
        record_type="transaction",
        external_record_id="LED001",
        record_date=date(2024, 1, 15),
        currency="USD",
        amount=Decimal("1000.00"),
        counterparty="ACME Corp",
        description="Payment",
        record_hash="hash456",
    )
    db_session.add(left_record)
    db_session.add(right_record)
    await db_session.commit()
    return left_record, right_record


@pytest.fixture
async def test_match_candidate(
    db_session: AsyncSession, test_reconciliation_run, test_records
) -> MatchCandidate:
    """Create a test match candidate."""
    left_record, right_record = test_records
    candidate = MatchCandidate(
        id=uuid.uuid4(),
        reconciliation_run_id=test_reconciliation_run.id,
        left_record_id=left_record.id,
        right_record_id=right_record.id,
        match_type=MatchType.EXACT,
        score=1.0,
        feature_payload={"amount_match": True, "date_match": True},
        decision_status=MatchDecisionStatus.MATCHED,
    )
    db_session.add(candidate)
    await db_session.commit()
    await db_session.refresh(candidate)
    return candidate


class TestCreateReconciliationRun:
    """Tests for creating reconciliation runs."""

    async def test_create_run(
        self, client: AsyncClient, left_source, right_source, auth_headers
    ):
        """Test creating a reconciliation run."""
        response = await client.post(
            "/reconciliation/runs",
            json={
                "name": "New Reconciliation",
                "left_source_id": str(left_source.id),
                "right_source_id": str(right_source.id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Reconciliation"
        assert data["status"] == "pending"

    async def test_create_run_with_parameters(
        self, client: AsyncClient, left_source, right_source, auth_headers
    ):
        """Test creating run with custom parameters."""
        response = await client.post(
            "/reconciliation/runs",
            json={
                "name": "Custom Reconciliation",
                "left_source_id": str(left_source.id),
                "right_source_id": str(right_source.id),
                "parameters": {
                    "date_tolerance_days": 5,
                    "amount_tolerance_percent": 0.02,
                },
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["parameters_json"]["date_tolerance_days"] == 5

    async def test_create_run_invalid_source(
        self, client: AsyncClient, left_source, auth_headers
    ):
        """Test creating run with invalid source."""
        fake_id = str(uuid.uuid4())
        response = await client.post(
            "/reconciliation/runs",
            json={
                "name": "Invalid Run",
                "left_source_id": str(left_source.id),
                "right_source_id": fake_id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestDuplicateDetection:
    """Tests for duplicate detection runs."""

    async def test_create_duplicate_detection(
        self, client: AsyncClient, left_source, auth_headers
    ):
        """Test creating duplicate detection run."""
        response = await client.post(
            "/reconciliation/duplicate-detection",
            json={
                "name": "Duplicate Detection Run",
                "source_id": str(left_source.id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "duplicate_detection" in data["parameters_json"]["run_type"]

    async def test_duplicate_detection_invalid_source(
        self, client: AsyncClient, auth_headers
    ):
        """Test duplicate detection with invalid source."""
        fake_id = str(uuid.uuid4())
        response = await client.post(
            "/reconciliation/duplicate-detection",
            json={
                "name": "Invalid Detection",
                "source_id": fake_id,
            },
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestListRuns:
    """Tests for listing reconciliation runs."""

    async def test_list_runs(
        self, client: AsyncClient, test_reconciliation_run, auth_headers
    ):
        """Test listing reconciliation runs."""
        response = await client.get(
            "/reconciliation/runs",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_list_runs_filter_status(
        self, client: AsyncClient, test_reconciliation_run, auth_headers
    ):
        """Test filtering runs by status."""
        response = await client.get(
            "/reconciliation/runs?status=completed",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "completed" for r in data)


class TestGetRun:
    """Tests for getting individual runs."""

    async def test_get_run(
        self, client: AsyncClient, test_reconciliation_run, auth_headers
    ):
        """Test getting run by ID."""
        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_reconciliation_run.id)
        assert data["status"] == "completed"

    async def test_get_run_not_found(self, client: AsyncClient, auth_headers):
        """Test getting non-existent run."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/reconciliation/runs/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestRunSummary:
    """Tests for run summary endpoint."""

    async def test_get_summary(
        self, client: AsyncClient, test_reconciliation_run, auth_headers
    ):
        """Test getting run summary."""
        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}/summary",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == str(test_reconciliation_run.id)
        assert data["total_matched"] == 90
        assert data["total_unmatched"] == 10

    async def test_summary_includes_counts(
        self, client: AsyncClient, test_reconciliation_run, test_match_candidate, auth_headers
    ):
        """Test that summary includes status counts."""
        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}/summary",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "candidate_status_counts" in data


class TestGetMatches:
    """Tests for getting match candidates."""

    async def test_get_matches(
        self, client: AsyncClient, test_reconciliation_run, test_match_candidate, auth_headers
    ):
        """Test getting matches for a run."""
        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}/matches",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_matches_filter_status(
        self, client: AsyncClient, test_reconciliation_run, test_match_candidate, auth_headers
    ):
        """Test filtering matches by decision status."""
        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}/matches?decision_status=matched",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(m["decision_status"] == "matched" for m in data)

    async def test_get_matches_filter_min_score(
        self, client: AsyncClient, test_reconciliation_run, test_match_candidate, auth_headers
    ):
        """Test filtering matches by minimum score."""
        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}/matches?min_score=0.9",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(m["score"] >= 0.9 for m in data)


class TestGetUnmatched:
    """Tests for getting unmatched records."""

    async def test_get_unmatched(
        self, client: AsyncClient, db_session, test_reconciliation_run, test_records, auth_headers
    ):
        """Test getting unmatched records."""
        left_record, _ = test_records
        unmatched = UnmatchedRecord(
            reconciliation_run_id=test_reconciliation_run.id,
            canonical_record_id=left_record.id,
            reason_code="no_match_found",
        )
        db_session.add(unmatched)
        await db_session.commit()

        response = await client.get(
            f"/reconciliation/runs/{test_reconciliation_run.id}/unmatched",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestCandidateRecords:
    """Tests for getting candidate record details."""

    async def test_get_candidate_records(
        self, client: AsyncClient, test_match_candidate, auth_headers
    ):
        """Test getting full record details for candidate."""
        response = await client.get(
            f"/reconciliation/candidates/{test_match_candidate.id}/records",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["candidate_id"] == str(test_match_candidate.id)
        assert data["left_record"] is not None
        assert data["right_record"] is not None
        assert "amount" in data["left_record"]

    async def test_get_candidate_records_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Test getting records for non-existent candidate."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/reconciliation/candidates/{fake_id}/records",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestUnauthenticated:
    """Tests for unauthenticated access."""

    async def test_list_runs_unauthenticated(self, client: AsyncClient):
        """Test listing runs without auth."""
        response = await client.get("/reconciliation/runs")
        assert response.status_code == 401

    async def test_create_run_unauthenticated(
        self, client: AsyncClient, left_source, right_source
    ):
        """Test creating run without auth."""
        response = await client.post(
            "/reconciliation/runs",
            json={
                "name": "Unauthorized Run",
                "left_source_id": str(left_source.id),
                "right_source_id": str(right_source.id),
            },
        )
        assert response.status_code == 401
