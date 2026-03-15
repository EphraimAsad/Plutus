"""Exception management routes."""

from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.exception import Exception as ExceptionModel, ExceptionStatus, ExceptionNote
from app.schemas.exception import (
    ExceptionResponse,
    ExceptionListResponse,
    ExceptionUpdate,
    ExceptionNoteCreate,
    ExceptionNoteResponse,
)
from app.api.deps import CurrentUser, AnalystUser
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("", response_model=ExceptionListResponse)
async def list_exceptions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = None,
    severity: str | None = None,
    exception_type: str | None = None,
    assigned_to: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ExceptionListResponse:
    """List exceptions with filtering."""
    query = select(ExceptionModel).order_by(
        ExceptionModel.severity.desc(),
        ExceptionModel.created_at.desc()
    )

    if status:
        try:
            status_enum = ExceptionStatus(status)
            query = query.where(ExceptionModel.status == status_enum)
        except ValueError:
            pass

    if severity:
        query = query.where(ExceptionModel.severity == severity)

    if exception_type:
        query = query.where(ExceptionModel.exception_type == exception_type)

    if assigned_to:
        query = query.where(ExceptionModel.assigned_to == assigned_to)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    exceptions = result.scalars().all()

    return ExceptionListResponse(
        items=[
            ExceptionResponse(
                id=str(e.id),
                reconciliation_run_id=str(e.reconciliation_run_id) if e.reconciliation_run_id else None,
                exception_type=e.exception_type.value,
                severity=e.severity.value,
                status=e.status.value,
                title=e.title,
                description=e.description,
                related_record_ids=e.related_record_ids,
                related_match_candidate_ids=e.related_match_candidate_ids,
                assigned_to=str(e.assigned_to) if e.assigned_to else None,
                resolved_by=str(e.resolved_by) if e.resolved_by else None,
                resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
                resolution_note=e.resolution_note,
                created_at=e.created_at.isoformat(),
                updated_at=e.updated_at.isoformat(),
            )
            for e in exceptions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{exception_id}", response_model=ExceptionResponse)
async def get_exception(
    exception_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExceptionResponse:
    """Get exception by ID."""
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    return ExceptionResponse(
        id=str(exception.id),
        reconciliation_run_id=str(exception.reconciliation_run_id) if exception.reconciliation_run_id else None,
        exception_type=exception.exception_type.value,
        severity=exception.severity.value,
        status=exception.status.value,
        title=exception.title,
        description=exception.description,
        related_record_ids=exception.related_record_ids,
        related_match_candidate_ids=exception.related_match_candidate_ids,
        assigned_to=str(exception.assigned_to) if exception.assigned_to else None,
        resolved_by=str(exception.resolved_by) if exception.resolved_by else None,
        resolved_at=exception.resolved_at.isoformat() if exception.resolved_at else None,
        resolution_note=exception.resolution_note,
        created_at=exception.created_at.isoformat(),
        updated_at=exception.updated_at.isoformat(),
    )


@router.post("/{exception_id}/assign")
async def assign_exception(
    exception_id: uuid.UUID,
    assignee_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Assign exception to a user."""
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    exception.assigned_to = assignee_id
    if exception.status == ExceptionStatus.OPEN:
        exception.status = ExceptionStatus.IN_REVIEW

    await db.flush()

    # Audit log
    audit = AuditService(db)
    await audit.log_exception_action(exception_id, current_user.id, "assign", {"assignee_id": str(assignee_id)})

    return {"message": "Exception assigned successfully"}


@router.post("/{exception_id}/resolve")
async def resolve_exception(
    exception_id: uuid.UUID,
    request: ExceptionUpdate,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Resolve an exception."""
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    exception.status = ExceptionStatus.RESOLVED
    exception.resolved_by = current_user.id
    exception.resolved_at = datetime.now(timezone.utc)
    exception.resolution_note = request.resolution_note

    await db.flush()

    # Audit log
    audit = AuditService(db)
    await audit.log_exception_action(exception_id, current_user.id, "resolve")

    return {"message": "Exception resolved successfully"}


@router.post("/{exception_id}/dismiss")
async def dismiss_exception(
    exception_id: uuid.UUID,
    request: ExceptionUpdate,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Dismiss an exception."""
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    exception.status = ExceptionStatus.DISMISSED
    exception.resolved_by = current_user.id
    exception.resolved_at = datetime.now(timezone.utc)
    exception.resolution_note = request.resolution_note

    await db.flush()

    # Audit log
    audit = AuditService(db)
    await audit.log_exception_action(exception_id, current_user.id, "dismiss")

    return {"message": "Exception dismissed"}


@router.post("/{exception_id}/escalate")
async def escalate_exception(
    exception_id: uuid.UUID,
    request: ExceptionUpdate,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Escalate an exception."""
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    exception.status = ExceptionStatus.ESCALATED
    if request.resolution_note:
        exception.resolution_note = request.resolution_note

    await db.flush()

    # Audit log
    audit = AuditService(db)
    await audit.log_exception_action(exception_id, current_user.id, "escalate")

    return {"message": "Exception escalated"}


@router.get("/{exception_id}/notes", response_model=list[ExceptionNoteResponse])
async def get_exception_notes(
    exception_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ExceptionNoteResponse]:
    """Get notes for an exception."""
    result = await db.execute(
        select(ExceptionNote)
        .where(ExceptionNote.exception_id == exception_id)
        .order_by(ExceptionNote.created_at)
    )
    notes = result.scalars().all()

    return [
        ExceptionNoteResponse(
            id=str(note.id),
            exception_id=str(note.exception_id),
            user_id=str(note.user_id),
            content=note.content,
            created_at=note.created_at.isoformat(),
        )
        for note in notes
    ]


@router.post("/{exception_id}/notes", response_model=ExceptionNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_exception_note(
    exception_id: uuid.UUID,
    request: ExceptionNoteCreate,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExceptionNoteResponse:
    """Add a note to an exception."""
    # Verify exception exists
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    note = ExceptionNote(
        exception_id=exception_id,
        user_id=current_user.id,
        content=request.content,
    )
    db.add(note)
    await db.flush()

    return ExceptionNoteResponse(
        id=str(note.id),
        exception_id=str(note.exception_id),
        user_id=str(note.user_id),
        content=note.content,
        created_at=note.created_at.isoformat(),
    )
