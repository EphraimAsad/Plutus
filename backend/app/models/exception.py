"""Exception management models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ExceptionType(str, enum.Enum):
    """Type of exception."""

    AMOUNT_MISMATCH = "amount_mismatch"
    DATE_MISMATCH = "date_mismatch"
    DESCRIPTION_MISMATCH = "description_mismatch"
    LOW_CONFIDENCE_CANDIDATE = "low_confidence_candidate"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    MISSING_COUNTER_ENTRY = "missing_counter_entry"
    INVALID_ROW = "invalid_row"
    AMBIGUOUS_MULTI_MATCH = "ambiguous_multi_match"
    ANOMALY_DETECTED = "anomaly_detected"
    VALIDATION_ERROR = "validation_error"
    REFERENCE_MISMATCH = "reference_mismatch"


class ExceptionStatus(str, enum.Enum):
    """Status of an exception."""

    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"


class ExceptionSeverity(str, enum.Enum):
    """Severity level of an exception."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Exception(BaseModel):
    """Exception requiring human review."""

    __tablename__ = "exceptions"

    reconciliation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=True,
        index=True,
    )
    exception_type: Mapped[ExceptionType] = mapped_column(
        Enum(ExceptionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    severity: Mapped[ExceptionSeverity] = mapped_column(
        Enum(ExceptionSeverity, values_callable=lambda x: [e.value for e in x]),
        default=ExceptionSeverity.MEDIUM,
        nullable=False,
        index=True,
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        Enum(ExceptionStatus, values_callable=lambda x: [e.value for e in x]),
        default=ExceptionStatus.OPEN,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    related_record_ids: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    related_match_candidate_ids: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Additional metadata
    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="exceptions")
    assigned_to_user = relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="assigned_exceptions",
    )
    resolved_by_user = relationship(
        "User",
        foreign_keys=[resolved_by],
        back_populates="resolved_exceptions",
    )
    ai_explanations = relationship("AIExplanation", back_populates="exception")
    notes = relationship("ExceptionNote", back_populates="exception", order_by="ExceptionNote.created_at")

    __table_args__ = (
        Index("ix_exceptions_status_severity", "status", "severity"),
        Index("ix_exceptions_status_assigned", "status", "assigned_to"),
    )

    def __repr__(self) -> str:
        return f"<Exception {self.id} type={self.exception_type} status={self.status}>"

    @property
    def is_open(self) -> bool:
        """Check if exception is still open."""
        return self.status in (ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW)

    @property
    def is_resolved(self) -> bool:
        """Check if exception has been resolved."""
        return self.status in (ExceptionStatus.RESOLVED, ExceptionStatus.DISMISSED)


class ExceptionNote(BaseModel):
    """Notes/comments on an exception."""

    __tablename__ = "exception_notes"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exceptions.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    exception = relationship("Exception", back_populates="notes")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ExceptionNote exception={self.exception_id}>"
