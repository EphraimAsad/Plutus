"""Reconciliation service for matching records across sources."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationStatus,
    MatchCandidate,
    MatchType as MatchTypeModel,
    MatchDecisionStatus,
    ReconciledMatch,
    ReconciledMatchItem,
    ResolutionType,
    UnmatchedRecord,
)
from app.models.transaction import CanonicalRecord
from app.models.source import SourceSystem
from app.services.matching_service import MatchingService, MatchingConfig, MatchType
from app.services.exception_service import ExceptionService

logger = get_logger(__name__)


class ReconciliationService:
    """Service for orchestrating reconciliation between record sets."""

    def __init__(self, db: AsyncSession, config: MatchingConfig | None = None):
        """Initialize reconciliation service.

        Args:
            db: Database session
            config: Optional matching configuration
        """
        self.db = db
        self.config = config or MatchingConfig()
        self.matcher = MatchingService(self.config)

    async def run_reconciliation(
        self,
        run_id: uuid.UUID,
        left_source_id: uuid.UUID,
        right_source_id: uuid.UUID,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a reconciliation run.

        Args:
            run_id: ID of the reconciliation run
            left_source_id: ID of the left source system
            right_source_id: ID of the right source system
            parameters: Optional parameters for the run

        Returns:
            Dictionary with reconciliation statistics
        """
        # Get the run record
        run = await self._get_run(run_id)
        if not run:
            raise ValueError(f"Reconciliation run not found: {run_id}")

        # Update status to processing
        run.status = ReconciliationStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Update matching config from run parameters
        run_params = run.parameters_json or {}
        if run_params.get("date_tolerance_days") is not None:
            self.config.date_tolerance_days = int(run_params["date_tolerance_days"])
        if run_params.get("amount_tolerance_percent") is not None:
            # Frontend sends as percentage (e.g., 1 for 1%), convert to decimal
            self.config.amount_tolerance_percent = float(run_params["amount_tolerance_percent"]) / 100.0

        # Recreate matcher with updated config
        self.matcher = MatchingService(self.config)

        logger.info(
            f"Reconciliation {run_id} config: date_tolerance={self.config.date_tolerance_days} days, "
            f"amount_tolerance={self.config.amount_tolerance_percent * 100}%"
        )

        try:
            # Get canonical records from both sources
            left_records = await self._get_records_for_source(left_source_id)
            right_records = await self._get_records_for_source(right_source_id)

            run.total_left_records = len(left_records)
            run.total_right_records = len(right_records)

            logger.info(
                f"Reconciliation {run_id}: {len(left_records)} left records, "
                f"{len(right_records)} right records"
            )

            # Phase 1: Find exact matches
            matched_left: set[uuid.UUID] = set()
            matched_right: set[uuid.UUID] = set()
            candidates: list[tuple[CanonicalRecord, CanonicalRecord, Any]] = []

            # First pass: exact matches
            for left in left_records:
                if left.id in matched_left:
                    continue

                for right in right_records:
                    if right.id in matched_right:
                        continue

                    left_data = self._record_to_dict(left)
                    right_data = self._record_to_dict(right)

                    if self.matcher.exact_match(left_data, right_data):
                        # Create confirmed match
                        await self._create_confirmed_match(
                            run, left, right, MatchType.EXACT, 1.0
                        )
                        matched_left.add(left.id)
                        matched_right.add(right.id)
                        break

            # Phase 2: Tolerance and fuzzy matches for remaining records
            unmatched_left = [r for r in left_records if r.id not in matched_left]
            unmatched_right = [r for r in right_records if r.id not in matched_right]

            for left in unmatched_left:
                left_data = self._record_to_dict(left)
                best_match = None
                best_result = None

                for right in unmatched_right:
                    if right.id in matched_right:
                        continue

                    right_data = self._record_to_dict(right)
                    result = self.matcher.match_records(left_data, right_data)

                    if result.is_match:
                        if best_result is None or result.score > best_result.score:
                            best_match = right
                            best_result = result

                if best_match and best_result:
                    # Create match candidate for review if not high confidence
                    if best_result.score >= self.config.high_confidence_score:
                        await self._create_confirmed_match(
                            run, left, best_match, best_result.match_type, best_result.score
                        )
                        matched_left.add(left.id)
                        matched_right.add(best_match.id)
                    else:
                        # Create candidate for manual review
                        await self._create_match_candidate(
                            run, left, best_match, best_result
                        )
                        candidates.append((left, best_match, best_result))

            # Phase 3: Create unmatched records
            final_unmatched_left = [r for r in left_records if r.id not in matched_left]
            final_unmatched_right = [r for r in right_records if r.id not in matched_right]

            for record in final_unmatched_left:
                # Check if it's in a candidate pair
                in_candidate = any(c[0].id == record.id for c in candidates)
                if not in_candidate:
                    await self._create_unmatched_record(run, record, "no_match_found")

            for record in final_unmatched_right:
                in_candidate = any(c[1].id == record.id for c in candidates)
                if not in_candidate:
                    await self._create_unmatched_record(run, record, "no_match_found")

            # Phase 4: Create exceptions for candidates requiring review
            exception_service = ExceptionService(self.db)
            exceptions_created = 0

            for left, right, result in candidates:
                candidate_result = await self.db.execute(
                    select(MatchCandidate).where(
                        MatchCandidate.reconciliation_run_id == run.id,
                        MatchCandidate.left_record_id == left.id,
                        MatchCandidate.right_record_id == right.id,
                    )
                )
                candidate = candidate_result.scalar_one_or_none()
                if candidate:
                    await exception_service.create_from_match_candidate(candidate)
                    exceptions_created += 1

            # Update run statistics
            run.total_matched = len(matched_left)
            run.total_unmatched = len(final_unmatched_left) + len(final_unmatched_right) - len(candidates)
            run.total_exceptions = exceptions_created
            run.status = ReconciliationStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)

            await self.db.flush()

            return {
                "run_id": str(run_id),
                "total_left": len(left_records),
                "total_right": len(right_records),
                "total_matched": run.total_matched,
                "total_candidates": len(candidates),
                "total_unmatched": run.total_unmatched,
                "total_exceptions": exceptions_created,
                "match_rate": run.match_rate,
            }

        except Exception as e:
            run.status = ReconciliationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
            logger.error(f"Reconciliation {run_id} failed: {e}")
            raise

    async def run_reconciliation_single_source(
        self,
        run_id: uuid.UUID,
        source_id: uuid.UUID,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute reconciliation for records within a single source.

        Useful for detecting duplicates and anomalies within one data set.
        """
        run = await self._get_run(run_id)
        if not run:
            raise ValueError(f"Reconciliation run not found: {run_id}")

        run.status = ReconciliationStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        try:
            records = await self._get_records_for_source(source_id)
            run.total_left_records = len(records)
            run.total_right_records = len(records)

            # Find potential duplicates
            duplicate_candidates: list[tuple] = []
            checked_pairs: set[tuple] = set()

            for i, record1 in enumerate(records):
                for record2 in records[i + 1:]:
                    pair_key = tuple(sorted([str(record1.id), str(record2.id)]))
                    if pair_key in checked_pairs:
                        continue
                    checked_pairs.add(pair_key)

                    data1 = self._record_to_dict(record1)
                    data2 = self._record_to_dict(record2)

                    result = self.matcher.match_records(data1, data2)

                    if result.score >= self.config.min_match_score:
                        await self._create_match_candidate(
                            run, record1, record2, result,
                            decision_status=MatchDecisionStatus.DUPLICATE_CANDIDATE
                        )
                        duplicate_candidates.append((record1, record2, result))

            run.total_matched = 0
            run.total_unmatched = len(records)
            run.total_exceptions = len(duplicate_candidates)
            run.status = ReconciliationStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)

            await self.db.flush()

            return {
                "run_id": str(run_id),
                "total_records": len(records),
                "duplicate_candidates": len(duplicate_candidates),
            }

        except Exception as e:
            run.status = ReconciliationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
            raise

    async def _get_run(self, run_id: uuid.UUID) -> ReconciliationRun | None:
        """Get reconciliation run by ID."""
        result = await self.db.execute(
            select(ReconciliationRun).where(ReconciliationRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def _get_records_for_source(
        self,
        source_id: uuid.UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[CanonicalRecord]:
        """Get canonical records for a source system."""
        query = select(CanonicalRecord).where(
            CanonicalRecord.source_system_id == source_id
        )

        if start_date:
            query = query.where(CanonicalRecord.record_date >= start_date.date())

        if end_date:
            query = query.where(CanonicalRecord.record_date <= end_date.date())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _record_to_dict(self, record: CanonicalRecord) -> dict[str, Any]:
        """Convert canonical record to dictionary for matching."""
        return {
            "external_record_id": record.external_record_id,
            "account_id": record.account_id,
            "entity_id": record.entity_id,
            "record_date": record.record_date,
            "settlement_date": record.settlement_date,
            "currency": record.currency,
            "amount": record.amount,
            "reference_code": record.reference_code,
            "description": record.description,
            "counterparty": record.counterparty,
        }

    async def _create_confirmed_match(
        self,
        run: ReconciliationRun,
        left: CanonicalRecord,
        right: CanonicalRecord,
        match_type: MatchType,
        score: float,
    ) -> ReconciledMatch:
        """Create a confirmed reconciled match."""
        match = ReconciledMatch(
            reconciliation_run_id=run.id,
            match_group_id=uuid.uuid4(),  # Generate unique group ID
            resolution_type=ResolutionType.ONE_TO_ONE,
            confidence_score=score,
            resolved_at=datetime.now(timezone.utc),
        )
        self.db.add(match)
        await self.db.flush()

        # Add items to the match
        left_item = ReconciledMatchItem(
            reconciled_match_id=match.id,
            canonical_record_id=left.id,
            side="left",
        )
        right_item = ReconciledMatchItem(
            reconciled_match_id=match.id,
            canonical_record_id=right.id,
            side="right",
        )
        self.db.add(left_item)
        self.db.add(right_item)

        return match

    async def _create_match_candidate(
        self,
        run: ReconciliationRun,
        left: CanonicalRecord,
        right: CanonicalRecord,
        result: Any,
        decision_status: MatchDecisionStatus = MatchDecisionStatus.REQUIRES_REVIEW,
    ) -> MatchCandidate:
        """Create a match candidate for review."""
        # Map match type
        match_type_map = {
            MatchType.EXACT: MatchTypeModel.EXACT,
            MatchType.TOLERANCE: MatchTypeModel.TOLERANCE,
            MatchType.FUZZY: MatchTypeModel.FUZZY,
            MatchType.SCORED: MatchTypeModel.SCORED,
            MatchType.NONE: MatchTypeModel.SCORED,
        }

        candidate = MatchCandidate(
            reconciliation_run_id=run.id,
            left_record_id=left.id,
            right_record_id=right.id,
            match_type=match_type_map.get(result.match_type, MatchTypeModel.SCORED),
            score=result.score,
            feature_payload=result.features.to_dict(),
            decision_status=decision_status,
        )
        self.db.add(candidate)

        return candidate

    async def _create_unmatched_record(
        self,
        run: ReconciliationRun,
        record: CanonicalRecord,
        reason: str,
    ) -> UnmatchedRecord:
        """Create an unmatched record entry."""
        unmatched = UnmatchedRecord(
            reconciliation_run_id=run.id,
            canonical_record_id=record.id,
            reason_code=reason,
        )
        self.db.add(unmatched)

        return unmatched

    async def resolve_candidate(
        self,
        candidate_id: uuid.UUID,
        decision: MatchDecisionStatus,
        resolved_by: uuid.UUID,
        note: str | None = None,
    ) -> MatchCandidate:
        """Resolve a match candidate.

        Args:
            candidate_id: ID of the candidate to resolve
            decision: The resolution decision
            resolved_by: ID of the user resolving
            note: Optional resolution note

        Returns:
            Updated match candidate
        """
        result = await self.db.execute(
            select(MatchCandidate).where(MatchCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            raise ValueError(f"Match candidate not found: {candidate_id}")

        candidate.decision_status = decision

        # If confirmed as match, create reconciled match
        if decision == MatchDecisionStatus.MATCHED:
            left_record = await self.db.get(CanonicalRecord, candidate.left_record_id)
            right_record = await self.db.get(CanonicalRecord, candidate.right_record_id)

            if left_record and right_record:
                match = ReconciledMatch(
                    reconciliation_run_id=candidate.reconciliation_run_id,
                    match_group_id=uuid.uuid4(),
                    resolution_type=ResolutionType.ONE_TO_ONE,
                    confidence_score=candidate.score,
                    resolved_by=resolved_by,
                    resolved_at=datetime.now(timezone.utc),
                )
                self.db.add(match)
                await self.db.flush()

                left_item = ReconciledMatchItem(
                    reconciled_match_id=match.id,
                    canonical_record_id=left_record.id,
                    side="left",
                )
                right_item = ReconciledMatchItem(
                    reconciled_match_id=match.id,
                    canonical_record_id=right_record.id,
                    side="right",
                )
                self.db.add(left_item)
                self.db.add(right_item)

        return candidate


async def get_reconciliation_service(db: AsyncSession) -> ReconciliationService:
    """Factory function to create reconciliation service."""
    return ReconciliationService(db)
