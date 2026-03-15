"""Ingestion service for processing uploaded files."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ingestion import IngestionJob, IngestionJobStatus, IngestionJobType, RawRecord
from app.models.source import SourceSystem, SourceSchemaMapping
from app.models.transaction import CanonicalRecord, ValidationResult as ValidationResultModel
from app.utils.csv_tools import (
    compute_file_hash,
    compute_row_hash,
    parse_file,
    count_rows,
)
from app.services.validation_service import RecordValidator, ValidationResult


class IngestionService:
    """Service for handling file ingestion."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(
        self,
        source_system_id: uuid.UUID,
        triggered_by: uuid.UUID,
        job_type: IngestionJobType = IngestionJobType.MANUAL_UPLOAD,
        file_name: str | None = None,
    ) -> IngestionJob:
        """Create a new ingestion job.

        Args:
            source_system_id: ID of the source system
            triggered_by: ID of the user who triggered the job
            job_type: Type of ingestion job
            file_name: Original file name

        Returns:
            Created IngestionJob
        """
        job = IngestionJob(
            source_system_id=source_system_id,
            job_type=job_type,
            status=IngestionJobStatus.PENDING,
            file_name=file_name,
            triggered_by=triggered_by,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def save_uploaded_file(
        self,
        job: IngestionJob,
        file_content: bytes,
        file_name: str,
    ) -> str:
        """Save uploaded file to storage.

        Args:
            job: The ingestion job
            file_content: Raw file bytes
            file_name: Original file name

        Returns:
            Path where file was saved
        """
        # Compute file hash
        file_hash = compute_file_hash(file_content)

        # Check for duplicate file
        existing = await self.db.execute(
            select(IngestionJob).where(
                IngestionJob.file_hash == file_hash,
                IngestionJob.source_system_id == job.source_system_id,
                IngestionJob.status == IngestionJobStatus.COMPLETED,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("This file has already been ingested")

        # Create storage path
        storage_dir = Path(settings.UPLOAD_DIR) / str(job.source_system_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        ext = Path(file_name).suffix
        storage_path = storage_dir / f"{job.id}{ext}"

        # Write file
        with open(storage_path, "wb") as f:
            f.write(file_content)

        # Update job with file info
        job.file_hash = file_hash
        job.storage_path = str(storage_path)
        job.file_name = file_name

        return str(storage_path)

    async def get_source_with_mapping(
        self,
        source_system_id: uuid.UUID,
    ) -> tuple[SourceSystem, SourceSchemaMapping]:
        """Get source system and its active schema mapping.

        Args:
            source_system_id: ID of the source system

        Returns:
            Tuple of (SourceSystem, active SourceSchemaMapping)

        Raises:
            ValueError: If source or mapping not found
        """
        result = await self.db.execute(
            select(SourceSystem).where(SourceSystem.id == source_system_id)
        )
        source = result.scalar_one_or_none()

        if not source:
            raise ValueError("Source system not found")

        if not source.is_active:
            raise ValueError("Source system is inactive")

        # Get active schema mapping
        mapping_result = await self.db.execute(
            select(SourceSchemaMapping).where(
                SourceSchemaMapping.source_system_id == source_system_id,
                SourceSchemaMapping.is_active == True,
            )
        )
        mapping = mapping_result.scalar_one_or_none()

        if not mapping:
            raise ValueError("No active schema mapping found for source system")

        return source, mapping

    async def process_file(
        self,
        job: IngestionJob,
        file_content: bytes,
        file_name: str,
    ) -> dict[str, Any]:
        """Process an uploaded file through the ingestion pipeline.

        Args:
            job: The ingestion job
            file_content: Raw file bytes
            file_name: Original file name

        Returns:
            Processing statistics
        """
        # Update job status
        job.status = IngestionJobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        try:
            # Get source and mapping
            source, mapping = await self.get_source_with_mapping(job.source_system_id)

            # Get mapping configuration
            field_mappings = mapping.field_mappings
            date_format = mapping.date_format
            skip_rows = mapping.skip_rows
            config = source.config_json or {}

            # Create validator
            validator = RecordValidator(
                field_mappings=field_mappings,
                date_format=date_format,
            )

            # Count total rows
            total_rows = count_rows(file_content, file_name, skip_rows=skip_rows)
            job.rows_received = total_rows

            # Process rows
            rows_valid = 0
            rows_invalid = 0
            row_number = 0

            for row_data in parse_file(
                file_content,
                file_name,
                encoding=config.get("file_encoding", "utf-8"),
                skip_rows=skip_rows,
            ):
                row_number += 1

                # Compute row hash
                row_hash = compute_row_hash(row_data)

                # Create raw record
                raw_record = RawRecord(
                    ingestion_job_id=job.id,
                    source_system_id=source.id,
                    source_row_number=row_number,
                    source_record_hash=row_hash,
                    raw_payload=row_data,
                    ingested_at=datetime.now(timezone.utc),
                )
                self.db.add(raw_record)
                await self.db.flush()

                # Validate record
                validation = validator.validate_record(row_data)

                # Create validation result
                validation_result = ValidationResultModel(
                    raw_record_id=raw_record.id,
                    is_valid=validation.is_valid,
                    error_codes=[e.to_dict() for e in validation.errors],
                    warning_codes=[w.to_dict() for w in validation.warnings],
                    validated_at=datetime.now(timezone.utc),
                )
                self.db.add(validation_result)

                if validation.is_valid:
                    rows_valid += 1

                    # Prepare JSON-safe payload (convert dates and decimals to strings)
                    json_payload = {}
                    for key, value in validation.normalized_data.items():
                        if hasattr(value, 'isoformat'):  # date/datetime
                            json_payload[key] = value.isoformat()
                        elif hasattr(value, '__str__') and type(value).__name__ == 'Decimal':
                            json_payload[key] = str(value)
                        else:
                            json_payload[key] = value

                    # Create canonical record
                    canonical = CanonicalRecord(
                        raw_record_id=raw_record.id,
                        source_system_id=source.id,
                        record_type=config.get("record_type", "transaction"),
                        external_record_id=validation.normalized_data.get("external_record_id"),
                        account_id=validation.normalized_data.get("account_id"),
                        entity_id=validation.normalized_data.get("entity_id"),
                        record_date=validation.normalized_data.get("record_date"),
                        settlement_date=validation.normalized_data.get("settlement_date"),
                        currency=validation.normalized_data.get("currency", "USD"),
                        amount=validation.normalized_data.get("amount"),
                        reference_code=validation.normalized_data.get("reference_code"),
                        description=validation.normalized_data.get("description"),
                        counterparty=validation.normalized_data.get("counterparty"),
                        record_hash=row_hash,
                        normalized_payload=json_payload,
                    )
                    self.db.add(canonical)
                else:
                    rows_invalid += 1

                # Flush periodically to avoid memory issues
                if row_number % 100 == 0:
                    await self.db.flush()

            # Final flush
            await self.db.flush()

            # Update job completion
            job.status = IngestionJobStatus.COMPLETED
            job.rows_valid = rows_valid
            job.rows_invalid = rows_invalid
            job.completed_at = datetime.now(timezone.utc)

            return {
                "rows_received": total_rows,
                "rows_valid": rows_valid,
                "rows_invalid": rows_invalid,
            }

        except Exception as e:
            job.status = IngestionJobStatus.FAILED
            job.error_summary = str(e)[:2000]
            job.completed_at = datetime.now(timezone.utc)
            raise

    async def get_job(self, job_id: uuid.UUID) -> IngestionJob | None:
        """Get ingestion job by ID."""
        result = await self.db.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def cancel_job(self, job: IngestionJob) -> None:
        """Cancel a pending or processing job."""
        if job.status not in (IngestionJobStatus.PENDING, IngestionJobStatus.PROCESSING):
            raise ValueError("Can only cancel pending or processing jobs")

        job.status = IngestionJobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)

    async def process_job(self, job_id: str) -> dict[str, Any]:
        """Process an ingestion job by ID (for Celery task).

        Reads the stored file and processes it through the pipeline.

        Args:
            job_id: String UUID of the job

        Returns:
            Processing statistics
        """
        job = await self.get_job(uuid.UUID(job_id))
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if not job.storage_path:
            raise ValueError("Job has no stored file")

        # Read file from storage
        with open(job.storage_path, "rb") as f:
            file_content = f.read()

        # Process the file
        return await self.process_file(job, file_content, job.file_name or "unknown")
