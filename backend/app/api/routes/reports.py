"""Report generation routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.report import Report, ReportFormat, ReportStatus, ReportType
from app.schemas.report import ReportCreate, ReportResponse, ReportListResponse
from app.api.deps import CurrentUser, ManagerUser

router = APIRouter()


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    request: ReportCreate,
    current_user: ManagerUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    """Create and generate a new report.

    This creates the report record and queues a background task to generate
    the actual report data and file. Poll the GET endpoint to check status.
    """
    # Validate report type
    try:
        report_type = ReportType(request.report_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type. Must be one of: {[t.value for t in ReportType]}",
        )

    # Validate file format
    file_format = request.file_format or "csv"
    try:
        format_enum = ReportFormat(file_format)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Must be one of: {[f.value for f in ReportFormat]}",
        )

    report = Report(
        report_type=report_type,
        title=request.title,
        filters_json=request.filters or {},
        parameters_json=request.parameters or {},
        file_format=format_enum,
        status=ReportStatus.PENDING,
        generated_by=current_user.id,
    )
    db.add(report)
    await db.flush()

    # Trigger Celery task for report generation
    from app.workers.report_tasks import generate_report_task
    generate_report_task.delay(str(report.id), file_format)

    return ReportResponse(
        id=str(report.id),
        report_type=report.report_type.value,
        title=report.title,
        filters_json=report.filters_json,
        status=report.status.value,
        file_path=report.file_path,
        file_format=report.file_format.value if report.file_format else None,
        generated_at=report.generated_at.isoformat() if report.generated_at else None,
        error_message=report.error_message,
        created_at=report.created_at.isoformat(),
    )


@router.get("", response_model=ReportListResponse)
async def list_reports(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    report_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ReportListResponse:
    """List reports."""
    query = select(Report).order_by(Report.created_at.desc())

    if report_type:
        try:
            type_enum = ReportType(report_type)
            query = query.where(Report.report_type == type_enum)
        except ValueError:
            pass

    if status:
        try:
            status_enum = ReportStatus(status)
            query = query.where(Report.status == status_enum)
        except ValueError:
            pass

    # Get total count
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    reports = result.scalars().all()

    return ReportListResponse(
        items=[
            ReportResponse(
                id=str(r.id),
                report_type=r.report_type.value,
                title=r.title,
                filters_json=r.filters_json,
                status=r.status.value,
                file_path=r.file_path,
                file_format=r.file_format.value if r.file_format else None,
                generated_at=r.generated_at.isoformat() if r.generated_at else None,
                error_message=r.error_message,
                created_at=r.created_at.isoformat(),
            )
            for r in reports
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    """Get report by ID."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return ReportResponse(
        id=str(report.id),
        report_type=report.report_type.value,
        title=report.title,
        filters_json=report.filters_json,
        status=report.status.value,
        file_path=report.file_path,
        file_format=report.file_format.value if report.file_format else None,
        generated_at=report.generated_at.isoformat() if report.generated_at else None,
        error_message=report.error_message,
        created_at=report.created_at.isoformat(),
    )


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Download a generated report file."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.status != ReportStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download",
        )

    if not report.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    # Check file exists
    from pathlib import Path
    if not Path(report.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found on disk",
        )

    # Determine media type based on format
    media_types = {
        "csv": "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "json": "application/json",
    }
    format_value = report.file_format.value if report.file_format else "csv"
    media_type = media_types.get(format_value, "application/octet-stream")

    # File extensions
    extensions = {"csv": "csv", "excel": "xlsx", "pdf": "pdf", "json": "json"}
    ext = extensions.get(format_value, "csv")

    return FileResponse(
        path=report.file_path,
        filename=f"{report.title}.{ext}",
        media_type=media_type,
    )


@router.post("/{report_id}/export")
async def export_report_format(
    report_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file_format: str = Query(default="csv", description="csv, excel, pdf, json"),
) -> dict:
    """Re-export an existing report to a different format.

    Uses the stored snapshot data to generate a new file without re-running
    the report query.
    """
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.status != ReportStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report must be completed before re-exporting",
        )

    # Validate format
    try:
        ReportFormat(file_format)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {[f.value for f in ReportFormat]}",
        )

    # Trigger re-export task
    from app.workers.report_tasks import regenerate_report_task
    regenerate_report_task.delay(str(report_id), file_format)

    return {
        "message": f"Report re-export to {file_format} queued",
        "report_id": str(report_id),
        "format": file_format,
    }


@router.get("/types")
async def get_report_types(
    current_user: CurrentUser,
) -> dict:
    """Get available report types and formats."""
    return {
        "report_types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in ReportType
        ],
        "file_formats": [
            {"value": f.value, "label": f.value.upper()}
            for f in ReportFormat
        ],
    }
