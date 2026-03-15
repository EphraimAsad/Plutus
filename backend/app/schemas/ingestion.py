"""Ingestion schemas."""

from typing import Any

from pydantic import BaseModel


class IngestionJobCreate(BaseModel):
    """Schema for creating an ingestion job."""

    file_name: str | None = None
    file_path: str | None = None
    job_type: str | None = None
    parameters: dict[str, Any] | None = None


class IngestionJobResponse(BaseModel):
    """Ingestion job response schema."""

    id: str
    source_system_id: str
    job_type: str
    status: str
    file_name: str | None = None
    file_hash: str | None = None
    rows_received: int
    rows_valid: int
    rows_invalid: int
    error_summary: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class RawRecordResponse(BaseModel):
    """Raw record response schema."""

    id: str
    ingestion_job_id: str
    source_system_id: str
    source_row_number: int
    raw_payload: dict[str, Any]
    ingested_at: str

    class Config:
        from_attributes = True


class ValidationResultResponse(BaseModel):
    """Validation result response schema."""

    id: str
    raw_record_id: str
    is_valid: bool
    error_codes: list[Any]
    warning_codes: list[Any]
    validated_at: str

    class Config:
        from_attributes = True
