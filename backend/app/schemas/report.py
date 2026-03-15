"""Report schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    """Schema for creating a report."""

    report_type: str = Field(..., description="reconciliation_summary, unmatched_items, exception_backlog, etc.")
    title: str = Field(..., min_length=1, max_length=500)
    filters: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    file_format: str = Field(default="csv", description="csv, excel, pdf, json")


class ReportResponse(BaseModel):
    """Report response schema."""

    id: str
    report_type: str
    title: str
    filters_json: dict[str, Any]
    status: str
    file_path: str | None
    file_format: str | None
    generated_at: str | None
    error_message: str | None
    created_at: str

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Paginated report list response."""

    items: list[ReportResponse]
    total: int
    limit: int
    offset: int


class ReportSnapshotResponse(BaseModel):
    """Report snapshot response schema."""

    id: str
    report_id: str
    snapshot_json: dict[str, Any]
    created_at: str

    class Config:
        from_attributes = True
