"""AI explanation models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AIExplanationStatus(str, enum.Enum):
    """Status of AI explanation generation."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"  # Rejected by safety filters


class ParentType(str, enum.Enum):
    """Type of parent entity for explanation."""

    EXCEPTION = "exception"
    ANOMALY = "anomaly"
    REPORT = "report"
    MATCH_CANDIDATE = "match_candidate"
    RECONCILIATION_RUN = "reconciliation_run"


class AIExplanation(BaseModel):
    """AI-generated explanation for an entity."""

    __tablename__ = "ai_explanations"

    parent_type: Mapped[ParentType] = mapped_column(
        Enum(ParentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Foreign keys for direct relationships (optional, for easier querying)
    exception_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exceptions.id"),
        nullable=True,
        index=True,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id"),
        nullable=True,
        index=True,
    )

    # Input data (structured only)
    input_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Generation metadata
    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1",
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ollama",
    )

    # Status and output
    status: Mapped[AIExplanationStatus] = mapped_column(
        Enum(AIExplanationStatus, values_callable=lambda x: [e.value for e in x]),
        default=AIExplanationStatus.PENDING,
        nullable=False,
        index=True,
    )
    output_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Safety and metadata
    safety_flags: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Request tracking
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Token usage tracking
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    output_tokens: Mapped[int | None] = mapped_column(default=None)

    # Relationships
    requested_by_user = relationship("User", back_populates="ai_explanations")
    exception = relationship("Exception", back_populates="ai_explanations")
    report = relationship("Report", back_populates="ai_explanations")

    __table_args__ = (
        Index("ix_ai_explanations_parent", "parent_type", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<AIExplanation {self.parent_type}:{self.parent_id} status={self.status}>"

    @property
    def is_complete(self) -> bool:
        """Check if explanation generation is complete."""
        return self.status in (
            AIExplanationStatus.COMPLETED,
            AIExplanationStatus.FAILED,
            AIExplanationStatus.REJECTED,
        )

    @property
    def has_safety_concerns(self) -> bool:
        """Check if there are any safety flags."""
        return bool(self.safety_flags.get("concerns"))
