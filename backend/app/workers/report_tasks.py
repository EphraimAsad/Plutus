"""Celery tasks for report generation."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path

from celery import shared_task

from app.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=2)
def generate_report_task(self, report_id: str, file_format: str = "csv") -> dict:
    """Generate a report.

    This task:
    1. Loads report configuration
    2. Queries data based on filters
    3. Creates report snapshot
    4. Generates output file (CSV/Excel/PDF)
    5. Updates report status
    """
    logger.info(f"Generating report: {report_id} in format: {file_format}")

    try:
        from app.services.reporting_service import ReportingService
        from app.models.report import ReportFormat
        from app.core.database import async_session_maker
        import asyncio

        # Parse format
        try:
            format_enum = ReportFormat(file_format)
        except ValueError:
            format_enum = ReportFormat.CSV

        async def run():
            async with async_session_maker() as session:
                service = ReportingService(session)
                result = await service.generate_report(
                    uuid.UUID(report_id),
                    file_format=format_enum
                )
                await session.commit()
                return result

        result = asyncio.run(run())
        return {
            "status": "completed",
            "report_id": report_id,
            "file_path": result.get("file_path"),
            "record_count": result.get("record_count", 0),
        }

    except Exception as exc:
        logger.error(f"Report generation {report_id} failed: {exc}")
        # Update status to failed
        try:
            from app.core.database import async_session_maker
            from app.models.report import Report, ReportStatus
            from sqlalchemy import select
            import asyncio

            async def mark_failed():
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(Report).where(Report.id == uuid.UUID(report_id))
                    )
                    report = result.scalar_one_or_none()
                    if report:
                        report.status = ReportStatus.FAILED
                        report.error_message = str(exc)[:2000]
                        await session.commit()

            asyncio.run(mark_failed())
        except Exception as inner_exc:
            logger.error(f"Failed to mark report as failed: {inner_exc}")

        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def regenerate_report_task(report_id: str, new_format: str) -> dict:
    """Re-export an existing report to a different format.

    Uses the stored snapshot data to generate a new file.
    """
    logger.info(f"Re-exporting report {report_id} to {new_format}")

    try:
        from app.services.export_service import ExportService
        from app.models.report import Report, ReportFormat, ReportSnapshot
        from app.core.database import async_session_maker
        from sqlalchemy import select
        import asyncio

        try:
            format_enum = ReportFormat(new_format)
        except ValueError:
            return {"status": "failed", "error": f"Invalid format: {new_format}"}

        async def run():
            async with async_session_maker() as session:
                # Get report and snapshot
                result = await session.execute(
                    select(Report).where(Report.id == uuid.UUID(report_id))
                )
                report = result.scalar_one_or_none()
                if not report:
                    return {"status": "failed", "error": "Report not found"}

                # Get latest snapshot
                snapshot_result = await session.execute(
                    select(ReportSnapshot)
                    .where(ReportSnapshot.report_id == report.id)
                    .order_by(ReportSnapshot.created_at.desc())
                    .limit(1)
                )
                snapshot = snapshot_result.scalar_one_or_none()
                if not snapshot:
                    return {"status": "failed", "error": "No snapshot data found"}

                # Export with new format
                export_service = ExportService()
                file_path = export_service.export(
                    report_id=report.id,
                    data=snapshot.snapshot_json,
                    format=format_enum,
                    title=report.title,
                )

                # Update report with new file path
                report.file_path = file_path
                report.file_format = format_enum
                await session.commit()

                return {"status": "completed", "file_path": file_path}

        return asyncio.run(run())

    except Exception as exc:
        logger.error(f"Report re-export failed: {exc}")
        return {"status": "failed", "error": str(exc)}


@shared_task
def cleanup_old_reports(days_old: int = 90) -> dict:
    """Clean up old report files."""
    logger.info(f"Cleaning up reports older than {days_old} days")

    try:
        from app.core.database import async_session_maker
        from app.models.report import Report, ReportStatus
        from app.core.config import settings
        from sqlalchemy import select, and_
        import asyncio

        cutoff_date = datetime.now() - timedelta(days=days_old)
        deleted_files = 0
        deleted_records = 0

        async def run():
            nonlocal deleted_files, deleted_records
            async with async_session_maker() as session:
                # Find old completed reports
                result = await session.execute(
                    select(Report).where(
                        and_(
                            Report.created_at < cutoff_date,
                            Report.status == ReportStatus.COMPLETED,
                        )
                    )
                )
                reports = result.scalars().all()

                for report in reports:
                    # Delete file if exists
                    if report.file_path:
                        file_path = Path(report.file_path)
                        if file_path.exists():
                            file_path.unlink()
                            deleted_files += 1

                    # Optionally delete record (or just clear file_path)
                    report.file_path = None
                    deleted_records += 1

                await session.commit()

        asyncio.run(run())
        return {
            "status": "completed",
            "deleted_files": deleted_files,
            "cleaned_records": deleted_records,
        }

    except Exception as exc:
        logger.error(f"Report cleanup failed: {exc}")
        return {"status": "failed", "error": str(exc)}
