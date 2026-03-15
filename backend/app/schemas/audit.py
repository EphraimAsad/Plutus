"""Audit log schemas."""

from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Audit log response schema."""

    id: str
    actor_user_id: str | None
    action_type: str
    entity_type: str
    entity_id: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    metadata_json: dict[str, Any]
    created_at: str

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
