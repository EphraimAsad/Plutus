"""Tests for ingestion endpoints."""

import pytest
import uuid
import io
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import SourceSystem, SourceSchemaMapping, SourceType
from app.models.ingestion import IngestionJob, IngestionJobStatus, IngestionJobType


@pytest.fixture
async def test_source(db_session: AsyncSession, admin_user) -> SourceSystem:
    """Create a test source system with schema mapping."""
    source = SourceSystem(
        id=uuid.uuid4(),
        name="Test Bank for Ingestion",
        source_type=SourceType.BANK,
        description="Test bank source for ingestion tests",
        is_active=True,
        config_json={},
        created_by=admin_user.id,
    )
    db_session.add(source)
    await db_session.flush()

    mapping = SourceSchemaMapping(
        source_system_id=source.id,
        version=1,
        mapping_json={
            "external_record_id": "transaction_id",
            "amount": "amount",
            "currency": "currency",
            "record_date": "date",
            "counterparty": "counterparty",
            "description": "description",
        },
        is_active=True,
    )
    db_session.add(mapping)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest.fixture
async def test_ingestion_job(
    db_session: AsyncSession, test_source, test_user
) -> IngestionJob:
    """Create a test ingestion job."""
    job = IngestionJob(
        id=uuid.uuid4(),
        source_system_id=test_source.id,
        job_type=IngestionJobType.MANUAL_UPLOAD,
        status=IngestionJobStatus.PENDING,
        file_name="test_file.csv",
        triggered_by=test_user.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


def create_csv_content(rows: list[dict]) -> bytes:
    """Create CSV content from rows."""
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(row.get(h, "")) for h in headers))
    return "\n".join(lines).encode("utf-8")


class TestFileUpload:
    """Tests for file upload endpoint."""

    async def test_upload_csv_success(
        self, client: AsyncClient, test_source, auth_headers
    ):
        """Test successful CSV upload."""
        csv_content = create_csv_content([
            {
                "transaction_id": "TXN001",
                "amount": "100.00",
                "currency": "USD",
                "date": "2024-01-15",
                "counterparty": "ACME Corp",
                "description": "Payment",
            },
            {
                "transaction_id": "TXN002",
                "amount": "250.50",
                "currency": "USD",
                "date": "2024-01-16",
                "counterparty": "Widget Inc",
                "description": "Invoice",
            },
        ])

        response = await client.post(
            f"/ingestion/upload?source_id={test_source.id}",
            files={"file": ("test_data.csv", io.BytesIO(csv_content), "text/csv")},
            headers=auth_headers,
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["file_name"] == "test_data.csv"

    async def test_upload_invalid_source(self, client: AsyncClient, auth_headers):
        """Test upload to non-existent source."""
        fake_source_id = uuid.uuid4()
        csv_content = b"col1,col2\nval1,val2"

        response = await client.post(
            f"/ingestion/upload?source_id={fake_source_id}",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_upload_invalid_file_type(
        self, client: AsyncClient, test_source, auth_headers
    ):
        """Test upload with invalid file type."""
        response = await client.post(
            f"/ingestion/upload?source_id={test_source.id}",
            files={"file": ("test.txt", io.BytesIO(b"test content"), "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    async def test_upload_unauthenticated(self, client: AsyncClient, test_source):
        """Test upload without authentication."""
        csv_content = b"col1,col2\nval1,val2"
        response = await client.post(
            f"/ingestion/upload?source_id={test_source.id}",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 401


class TestRunIngestion:
    """Tests for triggering ingestion runs."""

    async def test_run_ingestion(
        self, client: AsyncClient, test_source, auth_headers
    ):
        """Test triggering an ingestion run."""
        response = await client.post(
            f"/ingestion/run/{test_source.id}",
            headers=auth_headers,
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    async def test_run_ingestion_inactive_source(
        self, client: AsyncClient, db_session, admin_user, auth_headers
    ):
        """Test running ingestion on inactive source."""
        inactive_source = SourceSystem(
            name="Inactive Test Source",
            source_type=SourceType.LEDGER,
            is_active=False,
            created_by=admin_user.id,
        )
        db_session.add(inactive_source)
        await db_session.commit()

        response = await client.post(
            f"/ingestion/run/{inactive_source.id}",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "inactive" in response.json()["detail"].lower()


class TestListJobs:
    """Tests for listing ingestion jobs."""

    async def test_list_jobs(
        self, client: AsyncClient, test_ingestion_job, auth_headers
    ):
        """Test listing ingestion jobs."""
        response = await client.get("/ingestion/jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(j["id"] == str(test_ingestion_job.id) for j in data)

    async def test_list_jobs_filter_by_source(
        self, client: AsyncClient, test_source, test_ingestion_job, auth_headers
    ):
        """Test filtering jobs by source."""
        response = await client.get(
            f"/ingestion/jobs?source_id={test_source.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(j["source_system_id"] == str(test_source.id) for j in data)

    async def test_list_jobs_filter_by_status(
        self, client: AsyncClient, test_ingestion_job, auth_headers
    ):
        """Test filtering jobs by status."""
        response = await client.get(
            "/ingestion/jobs?status_filter=pending",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(j["status"] == "pending" for j in data)


class TestGetJob:
    """Tests for getting individual jobs."""

    async def test_get_job(
        self, client: AsyncClient, test_ingestion_job, auth_headers
    ):
        """Test getting job by ID."""
        response = await client.get(
            f"/ingestion/jobs/{test_ingestion_job.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_ingestion_job.id)
        assert data["status"] == "pending"
        assert data["file_name"] == "test_file.csv"

    async def test_get_job_not_found(self, client: AsyncClient, auth_headers):
        """Test getting non-existent job."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/ingestion/jobs/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestCancelJob:
    """Tests for cancelling jobs."""

    async def test_cancel_pending_job(
        self, client: AsyncClient, test_ingestion_job, auth_headers
    ):
        """Test cancelling a pending job."""
        response = await client.post(
            f"/ingestion/jobs/{test_ingestion_job.id}/cancel",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    async def test_cancel_completed_job(
        self, client: AsyncClient, db_session, test_ingestion_job, auth_headers
    ):
        """Test cancelling a completed job fails."""
        test_ingestion_job.status = IngestionJobStatus.COMPLETED
        await db_session.commit()

        response = await client.post(
            f"/ingestion/jobs/{test_ingestion_job.id}/cancel",
            headers=auth_headers,
        )
        assert response.status_code == 400


class TestGetJobRecords:
    """Tests for getting job records."""

    async def test_get_job_records_empty(
        self, client: AsyncClient, test_ingestion_job, auth_headers
    ):
        """Test getting records from job with no records."""
        response = await client.get(
            f"/ingestion/jobs/{test_ingestion_job.id}/records",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == str(test_ingestion_job.id)
        assert data["records"] == []

    async def test_get_job_records_with_data(
        self, client: AsyncClient, db_session, test_ingestion_job, auth_headers
    ):
        """Test getting records from job with data."""
        from app.models.ingestion import RawRecord

        # Add raw records
        record = RawRecord(
            ingestion_job_id=test_ingestion_job.id,
            source_system_id=test_ingestion_job.source_system_id,
            source_row_number=1,
            raw_payload={"amount": "100.00", "date": "2024-01-15"},
            row_hash="abc123",
        )
        db_session.add(record)
        test_ingestion_job.rows_received = 1
        await db_session.commit()

        response = await client.get(
            f"/ingestion/jobs/{test_ingestion_job.id}/records",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["records"]) == 1
        assert data["records"][0]["raw_payload"]["amount"] == "100.00"
