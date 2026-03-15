"""Reconciliation schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ReconciliationRunCreate(BaseModel):
    """Schema for creating a reconciliation run."""

    name: str = Field(..., min_length=1, max_length=255)
    left_source_id: str = Field(..., description="UUID of the left/primary source system")
    right_source_id: str = Field(..., description="UUID of the right/secondary source system")
    parameters: dict[str, Any] | None = Field(
        default=None,
        description="Optional matching parameters (date_tolerance_days, amount_tolerance_percent)",
    )


class DuplicateDetectionCreate(BaseModel):
    """Schema for creating a duplicate detection run."""

    name: str = Field(..., min_length=1, max_length=255)
    source_id: str = Field(..., description="UUID of the source system to check for duplicates")
    parameters: dict[str, Any] | None = None


class ReconciliationRunResponse(BaseModel):
    """Reconciliation run response schema."""

    id: str
    name: str
    status: str
    parameters_json: dict[str, Any]
    started_at: str | None
    completed_at: str | None
    total_left_records: int | None
    total_right_records: int | None
    total_matched: int | None
    total_unmatched: int | None
    total_exceptions: int | None
    created_at: str

    class Config:
        from_attributes = True


class ReconciliationSummary(BaseModel):
    """Reconciliation run summary."""

    run_id: str
    run_name: str
    status: str
    total_left_records: int
    total_right_records: int
    total_matched: int
    total_unmatched: int
    total_exceptions: int
    match_rate: float
    candidate_status_counts: dict[str, int]


class MatchCandidateResponse(BaseModel):
    """Match candidate response schema."""

    id: str
    reconciliation_run_id: str
    left_record_id: str
    right_record_id: str
    match_type: str
    score: float
    feature_payload: dict[str, Any]
    decision_status: str
    created_at: str

    class Config:
        from_attributes = True


class MatchCandidateUpdate(BaseModel):
    """Schema for updating a match candidate decision."""

    decision_status: str = Field(..., description="auto_matched, manually_matched, manually_rejected")
    resolution_note: str | None = None


class UnmatchedRecordResponse(BaseModel):
    """Unmatched record response schema."""

    id: str
    reconciliation_run_id: str
    canonical_record_id: str
    reason_code: str
    created_at: str

    class Config:
        from_attributes = True


class CanonicalRecordResponse(BaseModel):
    """Canonical record response schema."""

    id: str
    source_system_id: str
    record_type: str | None
    external_record_id: str | None
    account_id: str | None
    entity_id: str | None
    record_date: str | None
    settlement_date: str | None
    currency: str | None
    amount: str | None
    reference_code: str | None
    description: str | None
    counterparty: str | None
    record_hash: str
    created_at: str

    class Config:
        from_attributes = True
