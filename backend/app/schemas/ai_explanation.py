"""AI explanation schemas."""

from typing import Any

from pydantic import BaseModel


class AIExplanationCreate(BaseModel):
    """Schema for requesting an AI explanation."""

    additional_context: str | None = None


class AIExplanationResponse(BaseModel):
    """AI explanation response schema."""

    id: str
    parent_type: str
    parent_id: str
    status: str
    output_text: str | None
    model_name: str
    provider: str
    safety_flags: dict[str, Any]
    error_message: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: str
    completed_at: str | None

    class Config:
        from_attributes = True


class AIExplanationListResponse(BaseModel):
    """Paginated AI explanation list response."""

    items: list[AIExplanationResponse]
    total: int
    limit: int
    offset: int
