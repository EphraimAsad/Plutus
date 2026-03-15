"""Celery tasks for ingestion processing."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def process_ingestion_job(self, job_id: str) -> dict:
    """Process an ingestion job.

    This task:
    1. Reads the uploaded file
    2. Parses CSV/XLSX
    3. Creates raw records
    4. Runs validation
    5. Updates job status
    """
    logger.info(f"Processing ingestion job: {job_id}")

    try:
        # Import here to avoid circular imports
        from app.services.ingestion_service import IngestionService
        from app.core.database import async_session_maker
        import asyncio

        async def run_ingestion():
            async with async_session_maker() as session:
                service = IngestionService(session)
                result = await service.process_job(job_id)
                await session.commit()
                return result

        result = asyncio.run(run_ingestion())
        return {"status": "completed", "job_id": job_id, "result": result}

    except Exception as exc:
        logger.error(f"Ingestion job {job_id} failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


@shared_task
def cleanup_old_uploads(days_old: int = 30) -> dict:
    """Clean up old upload files."""
    logger.info(f"Cleaning up uploads older than {days_old} days")

    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.exists():
        return {"status": "no_upload_dir", "deleted": 0}

    cutoff = datetime.now(timezone.utc).timestamp() - (days_old * 24 * 60 * 60)
    deleted_count = 0

    for file_path in upload_dir.glob("*"):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff:
            try:
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

    return {"status": "completed", "deleted": deleted_count}
