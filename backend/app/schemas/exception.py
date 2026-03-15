"""Exception schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ExceptionResponse(BaseModel):
    """Exception response schema."""

    id: str
    reconciliation_run_id: str | None
    exception_type: str
    severity: str
    status: str
    title: str
    description: str | None
    related_record_ids: list[Any]
    related_match_candidate_ids: list[Any]
    assigned_to: str | None
    resolved_by: str | None
    resolved_at: str | None
    resolution_note: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ExceptionListResponse(BaseModel):
    """Paginated exception list response."""

    items: list[ExceptionResponse]
    total: int
    limit: int
    offset: int


class ExceptionUpdate(BaseModel):
    """Schema for updating an exception."""

    resolution_note: str | None = None


class ExceptionNoteCreate(BaseModel):
    """Schema for creating an exception note."""

    content: str = Field(..., min_length=1, max_length=5000)


class ExceptionNoteResponse(BaseModel):
    """Exception note response schema."""

    id: str
    exception_id: str
    user_id: str
    content: str
    created_at: str

    class Config:
        from_attributes = True
