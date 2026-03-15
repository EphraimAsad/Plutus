"""Validation result and canonical record models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ValidationResult(BaseModel):
    """Validation result for a raw record."""

    __tablename__ = "validation_results"

    raw_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_records.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
    )
    error_codes: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    warning_codes: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    raw_record = relationship("RawRecord", back_populates="validation_result")

    def __repr__(self) -> str:
        return f"<ValidationResult record={self.raw_record_id} valid={self.is_valid}>"

    @property
    def error_messages(self) -> list[str]:
        """Get human-readable error messages."""
        messages = []
        for code in self.error_codes:
            if isinstance(code, dict):
                messages.append(f"{code.get('field', 'Unknown')}: {code.get('message', code.get('code', 'Error'))}")
            else:
                messages.append(str(code))
        return messages


class CanonicalRecord(BaseModel):
    """Normalized canonical record for reconciliation."""

    __tablename__ = "canonical_records"

    raw_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_records.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_systems.id"),
        nullable=False,
        index=True,
    )

    # Record identification
    record_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    external_record_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Entity references
    account_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    entity_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Dates
    record_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    settlement_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Financial data
    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4),
        nullable=True,
        index=True,
    )

    # References and descriptions
    reference_code: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    counterparty: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Computed hash for deduplication
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Full normalized payload
    normalized_payload: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    raw_record = relationship("RawRecord", back_populates="canonical_record")
    source_system = relationship("SourceSystem", back_populates="canonical_records")

    # Match relationships
    left_match_candidates = relationship(
        "MatchCandidate",
        foreign_keys="MatchCandidate.left_record_id",
        back_populates="left_record",
    )
    right_match_candidates = relationship(
        "MatchCandidate",
        foreign_keys="MatchCandidate.right_record_id",
        back_populates="right_record",
    )
    reconciled_match_items = relationship(
        "ReconciledMatchItem",
        back_populates="canonical_record",
    )
    unmatched_records = relationship(
        "UnmatchedRecord",
        back_populates="canonical_record",
    )
    anomalies = relationship(
        "Anomaly",
        back_populates="canonical_record",
    )

    # Indexes
    __table_args__ = (
        Index("ix_canonical_records_date_amount", "record_date", "amount"),
        Index("ix_canonical_records_source_date", "source_system_id", "record_date"),
    )

    def __repr__(self) -> str:
        return f"<CanonicalRecord {self.id} ref={self.reference_code}>"
