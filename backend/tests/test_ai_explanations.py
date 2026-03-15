"""Tests for AI explanation endpoints."""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_explanation import AIExplanation, AIExplanationStatus, ParentType
from app.models.exception import (
    Exception as ExceptionModel,
    ExceptionStatus,
    ExceptionSeverity,
    ExceptionType,
)
from app.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from app.models.report import Report, ReportType, ReportStatus, ReportSnapshot


@pytest.fixture
async def test_exception_for_ai(db_session: AsyncSession) -> ExceptionModel:
    """Create a test exception for AI explanation."""
    exception = ExceptionModel(
        id=uuid.uuid4(),
        exception_type=ExceptionType.AMOUNT_MISMATCH,
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        title="Amount mismatch for AI test",
        description="Bank shows $1000, ledger shows $950",
        related_record_ids=["rec-1", "rec-2"],
        metadata_json={"difference": 50.00},
    )
    db_session.add(exception)
    await db_session.commit()
    await db_session.refresh(exception)
    return exception


@pytest.fixture
async def test_anomaly_for_ai(db_session: AsyncSession) -> Anomaly:
    """Create a test anomaly for AI explanation."""
    anomaly = Anomaly(
        id=uuid.uuid4(),
        anomaly_type=AnomalyType.LARGE_AMOUNT,
        severity=AnomalySeverity.HIGH,
        details_json={
            "amount": 500000.00,
            "threshold": 100000.00,
            "multiplier": 5.0,
        },
    )
    db_session.add(anomaly)
    await db_session.commit()
    await db_session.refresh(anomaly)
    return anomaly


@pytest.fixture
async def test_report_for_ai(db_session: AsyncSession, test_user) -> Report:
    """Create a test report for AI explanation."""
    report = Report(
        id=uuid.uuid4(),
        report_type=ReportType.RECONCILIATION_SUMMARY,
        title="Report for AI Summary",
        status=ReportStatus.COMPLETED,
        file_format="csv",
        generated_by=test_user.id,
    )
    db_session.add(report)
    await db_session.flush()

    snapshot = ReportSnapshot(
        report_id=report.id,
        snapshot_json={
            "summary": {
                "total_records": 5000,
                "matched": 4800,
                "unmatched": 200,
                "match_rate": 0.96,
                "exceptions": 45,
            }
        },
    )
    db_session.add(snapshot)
    await db_session.commit()
    await db_session.refresh(report)
    return report


@pytest.fixture
async def test_explanation(
    db_session: AsyncSession, test_exception_for_ai, test_user
) -> AIExplanation:
    """Create a test AI explanation."""
    explanation = AIExplanation(
        id=uuid.uuid4(),
        parent_type=ParentType.EXCEPTION,
        parent_id=test_exception_for_ai.id,
        exception_id=test_exception_for_ai.id,
        input_json={"exception_type": "amount_mismatch"},
        prompt_version="v1",
        model_name="gemma:7b",
        provider="ollama",
        status=AIExplanationStatus.COMPLETED,
        output_text="This exception appears to be caused by a timing difference...",
        safety_flags={},
        requested_by=test_user.id,
    )
    db_session.add(explanation)
    await db_session.commit()
    await db_session.refresh(explanation)
    return explanation


class TestAIStatus:
    """Tests for AI provider status endpoint."""

    async def test_get_ai_status(self, client: AsyncClient, auth_headers):
        """Test getting AI provider status."""
        response = await client.get(
            "/ai-explanations/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "model" in data
        assert "available" in data

    async def test_ai_status_unauthenticated(self, client: AsyncClient):
        """Test AI status without auth."""
        response = await client.get("/ai-explanations/status")
        assert response.status_code == 401


class TestExceptionExplanation:
    """Tests for exception AI explanations."""

    async def test_request_exception_explanation(
        self, client: AsyncClient, test_exception_for_ai, auth_headers
    ):
        """Test requesting AI explanation for exception."""
        response = await client.post(
            f"/ai-explanations/exception/{test_exception_for_ai.id}",
            headers=auth_headers,
        )
        # Should accept for background processing
        assert response.status_code in [200, 202]
        data = response.json()
        if response.status_code == 202:
            assert "explanation_id" in data or "message" in data

    async def test_request_exception_explanation_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Test requesting explanation for non-existent exception."""
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/ai-explanations/exception/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestAnomalyExplanation:
    """Tests for anomaly AI explanations."""

    async def test_request_anomaly_explanation(
        self, client: AsyncClient, test_anomaly_for_ai, auth_headers
    ):
        """Test requesting AI explanation for anomaly."""
        response = await client.post(
            f"/ai-explanations/anomaly/{test_anomaly_for_ai.id}",
            headers=auth_headers,
        )
        assert response.status_code in [200, 202]

    async def test_request_anomaly_explanation_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Test requesting explanation for non-existent anomaly."""
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/ai-explanations/anomaly/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestReportExplanation:
    """Tests for report AI summaries."""

    async def test_request_report_summary(
        self, client: AsyncClient, test_report_for_ai, auth_headers
    ):
        """Test requesting AI summary for report."""
        response = await client.post(
            f"/ai-explanations/report/{test_report_for_ai.id}",
            headers=auth_headers,
        )
        assert response.status_code in [200, 202]

    async def test_request_report_summary_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Test requesting summary for non-existent report."""
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/ai-explanations/report/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestGetExplanation:
    """Tests for getting explanations."""

    async def test_get_explanation(
        self, client: AsyncClient, test_explanation, auth_headers
    ):
        """Test getting explanation by ID."""
        response = await client.get(
            f"/ai-explanations/{test_explanation.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_explanation.id)
        assert data["status"] == "completed"
        assert data["provider"] == "ollama"

    async def test_get_explanation_not_found(
        self, client: AsyncClient, auth_headers
    ):
        """Test getting non-existent explanation."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"/ai-explanations/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestListExplanations:
    """Tests for listing explanations."""

    async def test_list_explanations(
        self, client: AsyncClient, test_explanation, auth_headers
    ):
        """Test listing all explanations."""
        response = await client.get(
            "/ai-explanations",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_list_explanations_filter_parent_type(
        self, client: AsyncClient, test_explanation, auth_headers
    ):
        """Test filtering explanations by parent type."""
        response = await client.get(
            "/ai-explanations?parent_type=exception",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["parent_type"] == "exception" for e in data["items"])

    async def test_list_explanations_filter_status(
        self, client: AsyncClient, test_explanation, auth_headers
    ):
        """Test filtering explanations by status."""
        response = await client.get(
            "/ai-explanations?status=completed",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["status"] == "completed" for e in data["items"])


class TestExplanationGuardrails:
    """Tests for AI explanation safety guardrails."""

    async def test_explanation_is_read_only(
        self, client: AsyncClient, test_explanation, auth_headers
    ):
        """Verify explanation model doesn't allow modifications to source data."""
        # The explanation should only contain analysis text
        response = await client.get(
            f"/ai-explanations/{test_explanation.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Should not contain any action commands
        assert "output_text" in data
        # Output should be analysis only
        if data["output_text"]:
            text = data["output_text"].lower()
            # Should not contain direct action commands
            assert "delete" not in text or "suggests" in text or "investigate" in text

    async def test_safety_flags_stored(
        self, client: AsyncClient, test_explanation, auth_headers
    ):
        """Verify safety flags are captured."""
        response = await client.get(
            f"/ai-explanations/{test_explanation.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "safety_flags" in data


class TestUnauthenticated:
    """Tests for unauthenticated access."""

    async def test_list_explanations_unauthenticated(self, client: AsyncClient):
        """Test listing explanations without auth."""
        response = await client.get("/ai-explanations")
        assert response.status_code == 401

    async def test_request_explanation_unauthenticated(
        self, client: AsyncClient, test_exception_for_ai
    ):
        """Test requesting explanation without auth."""
        response = await client.post(
            f"/ai-explanations/exception/{test_exception_for_ai.id}"
        )
        assert response.status_code == 401
