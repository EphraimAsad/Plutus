"""Ingestion job and raw record models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class IngestionJobStatus(str, enum.Enum):
    """Status of an ingestion job."""

    PENDING = "pending"
    PROCESSING = "processing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionJobType(str, enum.Enum):
    """Type of ingestion job."""

    MANUAL_UPLOAD = "manual_upload"
    SCHEDULED = "scheduled"
    API_IMPORT = "api_import"


class IngestionJob(BaseModel):
    """Ingestion job tracking."""

    __tablename__ = "ingestion_jobs"

    source_system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_systems.id"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[IngestionJobType] = mapped_column(
        Enum(IngestionJobType, values_callable=lambda x: [e.value for e in x]),
        default=IngestionJobType.MANUAL_UPLOAD,
        nullable=False,
    )
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(IngestionJobStatus, values_callable=lambda x: [e.value for e in x]),
        default=IngestionJobStatus.PENDING,
        nullable=False,
        index=True,
    )
    file_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64),  # SHA-256 hash
        nullable=True,
        index=True,
    )
    storage_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    rows_received: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    rows_valid: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    rows_invalid: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Relationships
    source_system = relationship("SourceSystem", back_populates="ingestion_jobs")
    triggered_by_user = relationship("User", back_populates="ingestion_jobs")
    raw_records = relationship("RawRecord", back_populates="ingestion_job")

    def __repr__(self) -> str:
        return f"<IngestionJob {self.id} status={self.status}>"

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (success or failure)."""
        return self.status in (
            IngestionJobStatus.COMPLETED,
            IngestionJobStatus.FAILED,
            IngestionJobStatus.CANCELLED,
        )

    @property
    def success_rate(self) -> float:
        """Calculate the validation success rate."""
        if self.rows_received == 0:
            return 0.0
        return self.rows_valid / self.rows_received


class RawRecord(BaseModel):
    """Raw ingested record before validation/normalization."""

    __tablename__ = "raw_records"

    ingestion_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id"),
        nullable=False,
        index=True,
    )
    source_system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_systems.id"),
        nullable=False,
        index=True,
    )
    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    source_record_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hash of raw payload
        nullable=False,
        index=True,
    )
    raw_payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    ingestion_job = relationship("IngestionJob", back_populates="raw_records")
    source_system = relationship("SourceSystem", back_populates="raw_records")
    validation_result = relationship(
        "ValidationResult",
        back_populates="raw_record",
        uselist=False,
    )
    canonical_record = relationship(
        "CanonicalRecord",
        back_populates="raw_record",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<RawRecord job={self.ingestion_job_id} row={self.source_row_number}>"
