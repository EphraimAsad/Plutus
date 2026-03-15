"""Audit log model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import generate_uuid


class AuditLog(Base):
    """Audit log for tracking all significant actions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,  # System actions may not have a user
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    before_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    after_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    actor_user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_action_time", "action_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action_type} on {self.entity_type}:{self.entity_id}>"


# Common action types for reference
class AuditAction:
    """Standard audit action type constants."""

    # Source management
    SOURCE_CREATED = "source_created"
    SOURCE_UPDATED = "source_updated"
    SOURCE_DEACTIVATED = "source_deactivated"
    SCHEMA_MAPPING_CREATED = "schema_mapping_created"
    SCHEMA_MAPPING_ACTIVATED = "schema_mapping_activated"

    # Ingestion
    INGESTION_STARTED = "ingestion_started"
    INGESTION_COMPLETED = "ingestion_completed"
    INGESTION_FAILED = "ingestion_failed"
    VALIDATION_COMPLETED = "validation_completed"

    # Reconciliation
    RECONCILIATION_STARTED = "reconciliation_started"
    RECONCILIATION_COMPLETED = "reconciliation_completed"
    RECONCILIATION_FAILED = "reconciliation_failed"
    MATCH_APPROVED = "match_approved"
    MATCH_REJECTED = "match_rejected"

    # Exceptions
    EXCEPTION_CREATED = "exception_created"
    EXCEPTION_ASSIGNED = "exception_assigned"
    EXCEPTION_RESOLVED = "exception_resolved"
    EXCEPTION_DISMISSED = "exception_dismissed"
    EXCEPTION_ESCALATED = "exception_escalated"
    EXCEPTION_NOTE_ADDED = "exception_note_added"

    # Reports
    REPORT_GENERATED = "report_generated"
    REPORT_DOWNLOADED = "report_downloaded"

    # AI
    AI_EXPLANATION_REQUESTED = "ai_explanation_requested"
    AI_EXPLANATION_COMPLETED = "ai_explanation_completed"

    # Admin
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    THRESHOLD_UPDATED = "threshold_updated"
    SETTING_UPDATED = "setting_updated"

    # Auth
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    LOGIN_FAILED = "login_failed"
