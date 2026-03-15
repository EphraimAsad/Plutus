"""Ingestion routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.ingestion import IngestionJob, IngestionJobStatus, IngestionJobType
from app.models.source import SourceSystem
from app.schemas.ingestion import IngestionJobResponse, IngestionJobCreate
from app.api.deps import CurrentUser, AnalystUser, AdminUser
from app.services.ingestion_service import IngestionService
from app.workers.ingestion_tasks import process_ingestion_job

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    source_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> dict:
    """Upload a file for ingestion.

    The file will be validated and queued for processing.
    Use GET /ingestion/jobs/{job_id} to check processing status.
    """
    # Verify source exists and is active
    result = await db.execute(select(SourceSystem).where(SourceSystem.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source system is inactive",
        )

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required",
        )

    ext = file.filename.lower().split(".")[-1]
    if ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Supported: csv, xlsx, xls",
        )

    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Create ingestion service
    service = IngestionService(db)

    try:
        # Create job
        job = await service.create_job(
            source_system_id=source_id,
            triggered_by=current_user.id,
            job_type=IngestionJobType.MANUAL_UPLOAD,
            file_name=file.filename,
        )

        # Save file
        await service.save_uploaded_file(job, file_content, file.filename)
        await db.commit()

        # Queue for background processing
        process_ingestion_job.delay(str(job.id))

        return {
            "message": "File uploaded successfully. Processing queued.",
            "job_id": str(job.id),
            "status": job.status.value,
            "file_name": job.file_name,
        }

    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/run/{source_id}", status_code=status.HTTP_202_ACCEPTED)
async def run_ingestion(
    source_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: IngestionJobCreate | None = None,
) -> dict:
    """Trigger an ingestion run for a source system.

    This creates a job that can be used with scheduled or API-based ingestion.
    """
    # Verify source exists
    result = await db.execute(select(SourceSystem).where(SourceSystem.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source system is inactive",
        )

    # Create ingestion service
    service = IngestionService(db)

    # Determine job type
    job_type = IngestionJobType.SCHEDULED
    if request and request.job_type:
        try:
            job_type = IngestionJobType(request.job_type)
        except ValueError:
            pass

    # Create job
    job = await service.create_job(
        source_system_id=source_id,
        triggered_by=current_user.id,
        job_type=job_type,
        file_name=request.file_name if request else None,
    )
    await db.commit()

    return {
        "message": "Ingestion job created",
        "job_id": str(job.id),
        "status": job.status.value,
    }


@router.get("/jobs", response_model=list[IngestionJobResponse])
async def list_ingestion_jobs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    source_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[IngestionJobResponse]:
    """List ingestion jobs with optional filtering."""
    query = select(IngestionJob).order_by(IngestionJob.created_at.desc())

    if source_id:
        query = query.where(IngestionJob.source_system_id == source_id)

    if status_filter:
        try:
            status_enum = IngestionJobStatus(status_filter)
            query = query.where(IngestionJob.status == status_enum)
        except ValueError:
            pass

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        IngestionJobResponse(
            id=str(job.id),
            source_system_id=str(job.source_system_id),
            job_type=job.job_type.value,
            status=job.status.value,
            file_name=job.file_name,
            file_hash=job.file_hash,
            rows_received=job.rows_received,
            rows_valid=job.rows_valid,
            rows_invalid=job.rows_invalid,
            error_summary=job.error_summary,
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            created_at=job.created_at.isoformat(),
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IngestionJobResponse:
    """Get ingestion job details by ID."""
    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    return IngestionJobResponse(
        id=str(job.id),
        source_system_id=str(job.source_system_id),
        job_type=job.job_type.value,
        status=job.status.value,
        file_name=job.file_name,
        file_hash=job.file_hash,
        rows_received=job.rows_received,
        rows_valid=job.rows_valid,
        rows_invalid=job.rows_invalid,
        error_summary=job.error_summary,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        created_at=job.created_at.isoformat(),
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_ingestion_job(
    job_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Cancel a pending or processing ingestion job."""
    service = IngestionService(db)
    job = await service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    try:
        await service.cancel_job(job)
        await db.commit()
        return {"message": "Job cancelled", "status": job.status.value}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/jobs/{job_id}/records")
async def get_job_records(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    valid_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Get raw records from an ingestion job."""
    from app.models.ingestion import RawRecord
    from app.models.transaction import ValidationResult as ValidationResultModel

    # Verify job exists
    job_result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    # Query records with validation results
    query = (
        select(RawRecord, ValidationResultModel)
        .outerjoin(ValidationResultModel, RawRecord.id == ValidationResultModel.raw_record_id)
        .where(RawRecord.ingestion_job_id == job_id)
        .order_by(RawRecord.source_row_number)
    )

    if valid_only:
        query = query.where(ValidationResultModel.is_valid == True)

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    records = []
    for raw_record, validation in rows:
        records.append({
            "id": str(raw_record.id),
            "row_number": raw_record.source_row_number,
            "raw_payload": raw_record.raw_payload,
            "is_valid": validation.is_valid if validation else None,
            "errors": validation.error_codes if validation else [],
            "warnings": validation.warning_codes if validation else [],
        })

    return {
        "job_id": str(job_id),
        "total_records": job.rows_received,
        "records": records,
    }


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ingestion_job(
    job_id: uuid.UUID,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an ingestion job and all related records (admin only)."""
    from sqlalchemy import delete
    from app.models.ingestion import RawRecord
    from app.models.transaction import ValidationResult, CanonicalRecord
    from app.models.reconciliation import MatchCandidate, ReconciledMatchItem, UnmatchedRecord

    result = await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    # Delete related records in order (respecting foreign keys)
    # 1. Get raw record IDs for this job
    raw_record_ids = await db.execute(
        select(RawRecord.id).where(RawRecord.ingestion_job_id == job_id)
    )
    raw_ids = [r[0] for r in raw_record_ids.fetchall()]

    if raw_ids:
        # 2. Get canonical record IDs linked to these raw records
        canonical_ids_result = await db.execute(
            select(CanonicalRecord.id).where(CanonicalRecord.raw_record_id.in_(raw_ids))
        )
        canonical_ids = [r[0] for r in canonical_ids_result.fetchall()]

        if canonical_ids:
            # 3. Delete reconciliation-related records referencing these canonical records
            await db.execute(
                delete(MatchCandidate).where(
                    (MatchCandidate.left_record_id.in_(canonical_ids)) |
                    (MatchCandidate.right_record_id.in_(canonical_ids))
                )
            )
            await db.execute(
                delete(ReconciledMatchItem).where(
                    ReconciledMatchItem.canonical_record_id.in_(canonical_ids)
                )
            )
            await db.execute(
                delete(UnmatchedRecord).where(
                    UnmatchedRecord.canonical_record_id.in_(canonical_ids)
                )
            )

        # 4. Delete canonical records linked to these raw records
        await db.execute(delete(CanonicalRecord).where(CanonicalRecord.raw_record_id.in_(raw_ids)))
        # 5. Delete validation results for these raw records
        await db.execute(delete(ValidationResult).where(ValidationResult.raw_record_id.in_(raw_ids)))
        # 6. Delete the raw records themselves
        await db.execute(delete(RawRecord).where(RawRecord.ingestion_job_id == job_id))

    # 7. Finally delete the job
    await db.delete(job)
    await db.commit()
