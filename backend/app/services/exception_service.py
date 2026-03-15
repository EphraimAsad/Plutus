"""Exception management service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.exception import (
    Exception as ExceptionModel,
    ExceptionType,
    ExceptionStatus,
    ExceptionSeverity,
    ExceptionNote,
)
from app.models.reconciliation import MatchCandidate, MatchDecisionStatus
from app.models.transaction import CanonicalRecord, ValidationResult

logger = get_logger(__name__)


class ExceptionService:
    """Service for creating and managing exceptions."""

    def __init__(self, db: AsyncSession):
        """Initialize exception service."""
        self.db = db

    async def create_exception(
        self,
        exception_type: ExceptionType,
        title: str,
        description: str | None = None,
        severity: ExceptionSeverity = ExceptionSeverity.MEDIUM,
        reconciliation_run_id: uuid.UUID | None = None,
        related_record_ids: list[str] | None = None,
        related_match_candidate_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExceptionModel:
        """Create a new exception.

        Args:
            exception_type: Type of the exception
            title: Short title describing the exception
            description: Detailed description
            severity: Severity level
            reconciliation_run_id: Related reconciliation run
            related_record_ids: List of related canonical record IDs
            related_match_candidate_ids: List of related match candidate IDs
            metadata: Additional metadata

        Returns:
            Created exception
        """
        exception = ExceptionModel(
            exception_type=exception_type,
            title=title,
            description=description,
            severity=severity,
            status=ExceptionStatus.OPEN,
            reconciliation_run_id=reconciliation_run_id,
            related_record_ids=related_record_ids or [],
            related_match_candidate_ids=related_match_candidate_ids or [],
            metadata_json=metadata or {},
        )
        self.db.add(exception)
        await self.db.flush()

        logger.info(f"Created exception {exception.id}: {title}")
        return exception

    async def create_from_match_candidate(
        self,
        candidate: MatchCandidate,
        exception_type: ExceptionType | None = None,
    ) -> ExceptionModel:
        """Create an exception from a match candidate.

        Args:
            candidate: The match candidate
            exception_type: Override exception type (auto-detected if not provided)

        Returns:
            Created exception
        """
        # Determine exception type based on features
        if exception_type is None:
            exception_type = self._determine_exception_type(candidate)

        # Determine severity based on score and type
        severity = self._determine_severity(candidate, exception_type)

        # Build title and description
        title = self._build_candidate_title(candidate, exception_type)
        description = self._build_candidate_description(candidate)

        exception = await self.create_exception(
            exception_type=exception_type,
            title=title,
            description=description,
            severity=severity,
            reconciliation_run_id=candidate.reconciliation_run_id,
            related_record_ids=[str(candidate.left_record_id), str(candidate.right_record_id)],
            related_match_candidate_ids=[str(candidate.id)],
            metadata={
                "match_score": candidate.score,
                "match_type": candidate.match_type.value,
                "features": candidate.feature_payload,
            },
        )

        return exception

    async def create_from_validation_errors(
        self,
        raw_record_id: uuid.UUID,
        validation_result: ValidationResult,
        source_system_id: uuid.UUID | None = None,
    ) -> list[ExceptionModel]:
        """Create exceptions from validation errors.

        Args:
            raw_record_id: ID of the raw record with errors
            validation_result: The validation result containing errors
            source_system_id: ID of the source system

        Returns:
            List of created exceptions
        """
        exceptions = []

        for error in validation_result.error_codes:
            error_dict = error if isinstance(error, dict) else error.to_dict()

            exception = await self.create_exception(
                exception_type=ExceptionType.VALIDATION_ERROR,
                title=f"Validation error: {error_dict.get('code', 'UNKNOWN')}",
                description=error_dict.get("message", "Validation failed"),
                severity=ExceptionSeverity.MEDIUM,
                related_record_ids=[str(raw_record_id)],
                metadata={
                    "error_code": error_dict.get("code"),
                    "field": error_dict.get("field"),
                    "source_system_id": str(source_system_id) if source_system_id else None,
                },
            )
            exceptions.append(exception)

        return exceptions

    async def create_unmatched_exception(
        self,
        record: CanonicalRecord,
        reconciliation_run_id: uuid.UUID,
        reason: str = "No matching record found",
    ) -> ExceptionModel:
        """Create an exception for an unmatched record.

        Args:
            record: The unmatched canonical record
            reconciliation_run_id: The reconciliation run ID
            reason: Reason for being unmatched

        Returns:
            Created exception
        """
        return await self.create_exception(
            exception_type=ExceptionType.MISSING_COUNTER_ENTRY,
            title=f"Unmatched record: {record.external_record_id or record.id}",
            description=f"{reason}. Amount: {record.amount} {record.currency}, Date: {record.record_date}",
            severity=ExceptionSeverity.MEDIUM,
            reconciliation_run_id=reconciliation_run_id,
            related_record_ids=[str(record.id)],
            metadata={
                "source_system_id": str(record.source_system_id),
                "amount": str(record.amount) if record.amount else None,
                "currency": record.currency,
                "record_date": record.record_date.isoformat() if record.record_date else None,
            },
        )

    async def get_exception_stats(
        self,
        reconciliation_run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Get exception statistics.

        Args:
            reconciliation_run_id: Optional filter by reconciliation run

        Returns:
            Dictionary with exception statistics
        """
        query = select(
            ExceptionModel.status,
            ExceptionModel.severity,
            func.count(ExceptionModel.id),
        ).group_by(ExceptionModel.status, ExceptionModel.severity)

        if reconciliation_run_id:
            query = query.where(ExceptionModel.reconciliation_run_id == reconciliation_run_id)

        result = await self.db.execute(query)
        rows = result.all()

        stats = {
            "by_status": {},
            "by_severity": {},
            "total": 0,
        }

        for status, severity, count in rows:
            status_key = status.value
            severity_key = severity.value

            stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + count
            stats["by_severity"][severity_key] = stats["by_severity"].get(severity_key, 0) + count
            stats["total"] += count

        return stats

    async def bulk_assign(
        self,
        exception_ids: list[uuid.UUID],
        assignee_id: uuid.UUID,
    ) -> int:
        """Bulk assign exceptions to a user.

        Args:
            exception_ids: List of exception IDs
            assignee_id: User to assign to

        Returns:
            Number of exceptions assigned
        """
        count = 0
        for exc_id in exception_ids:
            result = await self.db.execute(
                select(ExceptionModel).where(ExceptionModel.id == exc_id)
            )
            exception = result.scalar_one_or_none()
            if exception and exception.is_open:
                exception.assigned_to = assignee_id
                if exception.status == ExceptionStatus.OPEN:
                    exception.status = ExceptionStatus.IN_REVIEW
                count += 1

        await self.db.flush()
        return count

    async def bulk_resolve(
        self,
        exception_ids: list[uuid.UUID],
        resolved_by: uuid.UUID,
        resolution_note: str | None = None,
    ) -> int:
        """Bulk resolve exceptions.

        Args:
            exception_ids: List of exception IDs
            resolved_by: User resolving the exceptions
            resolution_note: Optional resolution note

        Returns:
            Number of exceptions resolved
        """
        count = 0
        now = datetime.now(timezone.utc)

        for exc_id in exception_ids:
            result = await self.db.execute(
                select(ExceptionModel).where(ExceptionModel.id == exc_id)
            )
            exception = result.scalar_one_or_none()
            if exception and exception.is_open:
                exception.status = ExceptionStatus.RESOLVED
                exception.resolved_by = resolved_by
                exception.resolved_at = now
                exception.resolution_note = resolution_note
                count += 1

        await self.db.flush()
        return count

    def _determine_exception_type(self, candidate: MatchCandidate) -> ExceptionType:
        """Determine exception type from match candidate features."""
        features = candidate.feature_payload or {}

        # Check for specific mismatch types
        if not features.get("amount_within_tolerance", True):
            return ExceptionType.AMOUNT_MISMATCH

        if not features.get("date_within_tolerance", True):
            return ExceptionType.DATE_MISMATCH

        if features.get("description_similarity", 1.0) < 0.5:
            return ExceptionType.DESCRIPTION_MISMATCH

        if features.get("reference_similarity", 1.0) < 0.5:
            return ExceptionType.REFERENCE_MISMATCH

        if candidate.decision_status == MatchDecisionStatus.DUPLICATE_CANDIDATE:
            return ExceptionType.DUPLICATE_SUSPECTED

        # Default to low confidence
        return ExceptionType.LOW_CONFIDENCE_CANDIDATE

    def _determine_severity(
        self,
        candidate: MatchCandidate,
        exception_type: ExceptionType,
    ) -> ExceptionSeverity:
        """Determine severity based on candidate and exception type."""
        # High severity for large amount mismatches
        features = candidate.feature_payload or {}
        amount_diff_pct = features.get("amount_diff_percent")

        if amount_diff_pct and amount_diff_pct > 0.1:  # >10% difference
            return ExceptionSeverity.HIGH

        if amount_diff_pct and amount_diff_pct > 0.05:  # >5% difference
            return ExceptionSeverity.MEDIUM

        # Low confidence matches with very low scores
        if candidate.score < 0.5:
            return ExceptionSeverity.HIGH

        if candidate.score < 0.7:
            return ExceptionSeverity.MEDIUM

        return ExceptionSeverity.LOW

    def _build_candidate_title(
        self,
        candidate: MatchCandidate,
        exception_type: ExceptionType,
    ) -> str:
        """Build exception title from candidate."""
        type_labels = {
            ExceptionType.AMOUNT_MISMATCH: "Amount mismatch",
            ExceptionType.DATE_MISMATCH: "Date mismatch",
            ExceptionType.DESCRIPTION_MISMATCH: "Description mismatch",
            ExceptionType.REFERENCE_MISMATCH: "Reference mismatch",
            ExceptionType.LOW_CONFIDENCE_CANDIDATE: "Low confidence match",
            ExceptionType.DUPLICATE_SUSPECTED: "Potential duplicate",
            ExceptionType.AMBIGUOUS_MULTI_MATCH: "Ambiguous match",
        }

        label = type_labels.get(exception_type, "Review required")
        return f"{label} (score: {candidate.score:.2f})"

    def _build_candidate_description(self, candidate: MatchCandidate) -> str:
        """Build exception description from candidate."""
        features = candidate.feature_payload or {}
        parts = []

        if features.get("amount_diff"):
            parts.append(f"Amount difference: {features['amount_diff']}")

        if features.get("amount_diff_percent"):
            parts.append(f"Amount difference: {features['amount_diff_percent']:.2%}")

        if features.get("date_diff_days"):
            parts.append(f"Date difference: {features['date_diff_days']} days")

        if features.get("description_similarity"):
            parts.append(f"Description similarity: {features['description_similarity']:.2%}")

        if not parts:
            parts.append(f"Match score: {candidate.score:.2f}")

        return ". ".join(parts)


async def get_exception_service(db: AsyncSession) -> ExceptionService:
    """Factory function to create exception service."""
    return ExceptionService(db)
