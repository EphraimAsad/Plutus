"""Reconciliation routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.reconciliation import (
    ReconciliationRun,
    ReconciliationStatus,
    MatchCandidate,
    MatchDecisionStatus,
    ReconciledMatch,
    ReconciledMatchItem,
    UnmatchedRecord,
)
from app.schemas.reconciliation import (
    ReconciliationRunCreate,
    ReconciliationRunResponse,
    ReconciliationSummary,
    MatchCandidateResponse,
    UnmatchedRecordResponse,
    DuplicateDetectionCreate,
)
from app.api.deps import CurrentUser, AnalystUser, AdminUser
from app.models.source import SourceSystem
from app.workers.reconciliation_tasks import run_reconciliation, run_duplicate_detection
from app.services.audit_service import AuditService

router = APIRouter()


@router.post("/runs", response_model=ReconciliationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_reconciliation_run(
    request: ReconciliationRunCreate,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconciliationRunResponse:
    """Create and start a new reconciliation run.

    Compares records from left_source against right_source.
    The reconciliation job runs asynchronously in the background.
    """
    # Validate source IDs
    left_source = await db.execute(
        select(SourceSystem).where(SourceSystem.id == uuid.UUID(request.left_source_id))
    )
    if not left_source.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Left source system not found",
        )

    right_source = await db.execute(
        select(SourceSystem).where(SourceSystem.id == uuid.UUID(request.right_source_id))
    )
    if not right_source.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Right source system not found",
        )

    # Create the run record
    parameters = request.parameters or {}
    parameters["left_source_id"] = request.left_source_id
    parameters["right_source_id"] = request.right_source_id

    run = ReconciliationRun(
        name=request.name,
        status=ReconciliationStatus.PENDING,
        parameters_json=parameters,
        triggered_by=current_user.id,
    )
    db.add(run)
    await db.flush()

    # Audit log
    audit = AuditService(db)
    await audit.log_create("reconciliation_run", run.id, current_user.id, entity_name=run.name)

    await db.commit()

    # Trigger Celery task for reconciliation
    run_reconciliation.delay(
        str(run.id),
        request.left_source_id,
        request.right_source_id,
    )

    return ReconciliationRunResponse(
        id=str(run.id),
        name=run.name,
        status=run.status.value,
        parameters_json=run.parameters_json,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        total_left_records=run.total_left_records,
        total_right_records=run.total_right_records,
        total_matched=run.total_matched,
        total_unmatched=run.total_unmatched,
        total_exceptions=run.total_exceptions,
        created_at=run.created_at.isoformat(),
    )


@router.post("/duplicate-detection", response_model=ReconciliationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_duplicate_detection_run(
    request: DuplicateDetectionCreate,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconciliationRunResponse:
    """Create a duplicate detection run for a single source.

    Finds potential duplicate records within the same source system.
    """
    # Validate source ID
    source = await db.execute(
        select(SourceSystem).where(SourceSystem.id == uuid.UUID(request.source_id))
    )
    if not source.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    parameters = request.parameters or {}
    parameters["source_id"] = request.source_id
    parameters["run_type"] = "duplicate_detection"

    run = ReconciliationRun(
        name=request.name,
        status=ReconciliationStatus.PENDING,
        parameters_json=parameters,
        triggered_by=current_user.id,
    )
    db.add(run)
    await db.commit()

    # Trigger Celery task for duplicate detection
    run_duplicate_detection.delay(str(run.id), request.source_id)

    return ReconciliationRunResponse(
        id=str(run.id),
        name=run.name,
        status=run.status.value,
        parameters_json=run.parameters_json,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        total_left_records=run.total_left_records,
        total_right_records=run.total_right_records,
        total_matched=run.total_matched,
        total_unmatched=run.total_unmatched,
        total_exceptions=run.total_exceptions,
        created_at=run.created_at.isoformat(),
    )


@router.get("/runs", response_model=list[ReconciliationRunResponse])
async def list_reconciliation_runs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReconciliationRunResponse]:
    """List reconciliation runs."""
    query = select(ReconciliationRun).order_by(ReconciliationRun.created_at.desc())

    if status:
        try:
            status_enum = ReconciliationStatus(status)
            query = query.where(ReconciliationRun.status == status_enum)
        except ValueError:
            pass

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    runs = result.scalars().all()

    return [
        ReconciliationRunResponse(
            id=str(run.id),
            name=run.name,
            status=run.status.value,
            parameters_json=run.parameters_json,
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            total_left_records=run.total_left_records,
            total_right_records=run.total_right_records,
            total_matched=run.total_matched,
            total_unmatched=run.total_unmatched,
            total_exceptions=run.total_exceptions,
            created_at=run.created_at.isoformat(),
        )
        for run in runs
    ]


@router.get("/runs/{run_id}", response_model=ReconciliationRunResponse)
async def get_reconciliation_run(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconciliationRunResponse:
    """Get reconciliation run by ID."""
    result = await db.execute(select(ReconciliationRun).where(ReconciliationRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation run not found",
        )

    return ReconciliationRunResponse(
        id=str(run.id),
        name=run.name,
        status=run.status.value,
        parameters_json=run.parameters_json,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        total_left_records=run.total_left_records,
        total_right_records=run.total_right_records,
        total_matched=run.total_matched,
        total_unmatched=run.total_unmatched,
        total_exceptions=run.total_exceptions,
        created_at=run.created_at.isoformat(),
    )


@router.get("/runs/{run_id}/summary", response_model=ReconciliationSummary)
async def get_reconciliation_summary(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReconciliationSummary:
    """Get summary statistics for a reconciliation run."""
    result = await db.execute(select(ReconciliationRun).where(ReconciliationRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation run not found",
        )

    # Get match candidate counts by status
    candidate_counts = await db.execute(
        select(MatchCandidate.decision_status, func.count(MatchCandidate.id))
        .where(MatchCandidate.reconciliation_run_id == run_id)
        .group_by(MatchCandidate.decision_status)
    )
    status_counts = {row[0].value: row[1] for row in candidate_counts}

    return ReconciliationSummary(
        run_id=str(run.id),
        run_name=run.name,
        status=run.status.value,
        total_left_records=run.total_left_records or 0,
        total_right_records=run.total_right_records or 0,
        total_matched=run.total_matched or 0,
        total_unmatched=run.total_unmatched or 0,
        total_exceptions=run.total_exceptions or 0,
        match_rate=run.match_rate,
        candidate_status_counts=status_counts,
    )


@router.get("/runs/{run_id}/matches", response_model=list[MatchCandidateResponse])
async def get_reconciliation_matches(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    decision_status: str | None = None,
    min_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MatchCandidateResponse]:
    """Get match candidates for a reconciliation run."""
    query = (
        select(MatchCandidate)
        .where(MatchCandidate.reconciliation_run_id == run_id)
        .order_by(MatchCandidate.score.desc())
    )

    if decision_status:
        query = query.where(MatchCandidate.decision_status == decision_status)

    if min_score is not None:
        query = query.where(MatchCandidate.score >= min_score)

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    candidates = result.scalars().all()

    return [
        MatchCandidateResponse(
            id=str(c.id),
            reconciliation_run_id=str(c.reconciliation_run_id),
            left_record_id=str(c.left_record_id),
            right_record_id=str(c.right_record_id),
            match_type=c.match_type.value,
            score=c.score,
            feature_payload=c.feature_payload,
            decision_status=c.decision_status.value,
            created_at=c.created_at.isoformat(),
        )
        for c in candidates
    ]


@router.get("/runs/{run_id}/unmatched", response_model=list[UnmatchedRecordResponse])
async def get_unmatched_records(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[UnmatchedRecordResponse]:
    """Get unmatched records for a reconciliation run."""
    from app.models.transaction import CanonicalRecord

    result = await db.execute(
        select(UnmatchedRecord, CanonicalRecord)
        .join(CanonicalRecord, UnmatchedRecord.canonical_record_id == CanonicalRecord.id)
        .where(UnmatchedRecord.reconciliation_run_id == run_id)
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    return [
        {
            "id": str(ur.id),
            "reconciliation_run_id": str(ur.reconciliation_run_id),
            "canonical_record_id": str(ur.canonical_record_id),
            "reason_code": ur.reason_code,
            "created_at": ur.created_at.isoformat(),
            "external_record_id": cr.external_record_id,
            "amount": str(cr.amount) if cr.amount else None,
            "record_date": cr.record_date.isoformat() if cr.record_date else None,
            "reference_code": cr.reference_code,
            "description": cr.description,
        }
        for ur, cr in rows
    ]


@router.get("/runs/{run_id}/confirmed-matches")
async def get_confirmed_matches(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get confirmed reconciled matches with full record details."""
    from app.models.transaction import CanonicalRecord

    # Get reconciled matches with their items
    result = await db.execute(
        select(ReconciledMatch)
        .where(ReconciledMatch.reconciliation_run_id == run_id)
        .limit(limit)
        .offset(offset)
    )
    matches = result.scalars().all()

    response = []
    for match in matches:
        # Get left and right items
        items_result = await db.execute(
            select(ReconciledMatchItem, CanonicalRecord)
            .join(CanonicalRecord, ReconciledMatchItem.canonical_record_id == CanonicalRecord.id)
            .where(ReconciledMatchItem.reconciled_match_id == match.id)
        )
        items = items_result.all()

        left_record = None
        right_record = None
        for item, record in items:
            record_data = {
                "external_record_id": record.external_record_id,
                "amount": str(record.amount) if record.amount else None,
                "record_date": record.record_date.isoformat() if record.record_date else None,
                "reference_code": record.reference_code,
                "description": record.description,
            }
            if item.side == "left":
                left_record = record_data
            else:
                right_record = record_data

        response.append({
            "id": str(match.id),
            "match_type": "exact",  # Confirmed matches are typically exact
            "confidence_score": match.confidence_score,
            "left_record": left_record,
            "right_record": right_record,
        })

    return response


@router.post("/candidates/{candidate_id}/resolve")
async def resolve_match_candidate(
    candidate_id: uuid.UUID,
    decision: str,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    resolution_note: str | None = None,
) -> dict:
    """Resolve a match candidate.

    Args:
        candidate_id: ID of the match candidate
        decision: Resolution decision (matched, rejected, duplicate_candidate)
        resolution_note: Optional note about the resolution
    """
    from app.services.reconciliation_service import ReconciliationService

    # Validate decision
    try:
        decision_status = MatchDecisionStatus(decision)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision. Must be one of: {[s.value for s in MatchDecisionStatus]}",
        )

    service = ReconciliationService(db)

    try:
        candidate = await service.resolve_candidate(
            candidate_id=candidate_id,
            decision=decision_status,
            resolved_by=current_user.id,
            note=resolution_note,
        )
        await db.commit()

        return {
            "message": f"Candidate resolved as {decision}",
            "candidate_id": str(candidate_id),
            "decision": decision,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/candidates/{candidate_id}/records")
async def get_candidate_records(
    candidate_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get the full record details for a match candidate (both left and right)."""
    from app.models.transaction import CanonicalRecord
    from app.schemas.reconciliation import CanonicalRecordResponse

    # Get the candidate
    result = await db.execute(
        select(MatchCandidate).where(MatchCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match candidate not found",
        )

    # Get both records
    left_result = await db.execute(
        select(CanonicalRecord).where(CanonicalRecord.id == candidate.left_record_id)
    )
    left_record = left_result.scalar_one_or_none()

    right_result = await db.execute(
        select(CanonicalRecord).where(CanonicalRecord.id == candidate.right_record_id)
    )
    right_record = right_result.scalar_one_or_none()

    def record_to_response(r: CanonicalRecord) -> dict:
        return {
            "id": str(r.id),
            "source_system_id": str(r.source_system_id),
            "record_type": r.record_type,
            "external_record_id": r.external_record_id,
            "account_id": r.account_id,
            "entity_id": r.entity_id,
            "record_date": r.record_date.isoformat() if r.record_date else None,
            "settlement_date": r.settlement_date.isoformat() if r.settlement_date else None,
            "currency": r.currency,
            "amount": str(r.amount) if r.amount else None,
            "reference_code": r.reference_code,
            "description": r.description,
            "counterparty": r.counterparty,
            "record_hash": r.record_hash,
            "created_at": r.created_at.isoformat(),
        }

    return {
        "candidate_id": str(candidate_id),
        "match_type": candidate.match_type.value,
        "score": candidate.score,
        "features": candidate.feature_payload,
        "decision_status": candidate.decision_status.value,
        "left_record": record_to_response(left_record) if left_record else None,
        "right_record": record_to_response(right_record) if right_record else None,
    }


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reconciliation_run(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a reconciliation run and all related data."""
    from sqlalchemy import delete
    from app.models.exception import Exception as ExceptionModel, ExceptionNote
    from app.models.anomaly import Anomaly
    from app.models.ai_explanation import AIExplanation

    result = await db.execute(
        select(ReconciliationRun).where(ReconciliationRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation run not found",
        )

    # Delete related records in order (respecting foreign keys)
    # 1. Delete match candidates
    await db.execute(
        delete(MatchCandidate).where(MatchCandidate.reconciliation_run_id == run_id)
    )

    # 2. Delete reconciled match items (must delete before reconciled matches)
    await db.execute(
        delete(ReconciledMatchItem).where(
            ReconciledMatchItem.reconciled_match_id.in_(
                select(ReconciledMatch.id).where(ReconciledMatch.reconciliation_run_id == run_id)
            )
        )
    )

    # 3. Delete reconciled matches
    await db.execute(
        delete(ReconciledMatch).where(ReconciledMatch.reconciliation_run_id == run_id)
    )

    # 4. Delete unmatched records
    await db.execute(
        delete(UnmatchedRecord).where(UnmatchedRecord.reconciliation_run_id == run_id)
    )

    # 5. Delete exceptions linked to this run (first delete related AI explanations and notes)
    exception_ids_result = await db.execute(
        select(ExceptionModel.id).where(ExceptionModel.reconciliation_run_id == run_id)
    )
    exception_ids = [r[0] for r in exception_ids_result.fetchall()]
    if exception_ids:
        await db.execute(delete(AIExplanation).where(AIExplanation.exception_id.in_(exception_ids)))
        await db.execute(delete(ExceptionNote).where(ExceptionNote.exception_id.in_(exception_ids)))
    await db.execute(
        delete(ExceptionModel).where(ExceptionModel.reconciliation_run_id == run_id)
    )

    # 6. Delete anomalies linked to this run
    await db.execute(
        delete(Anomaly).where(Anomaly.reconciliation_run_id == run_id)
    )

    # 7. Finally delete the run
    await db.delete(run)
    await db.commit()
