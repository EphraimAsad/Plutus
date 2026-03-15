"""Reconciliation run and match models."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ReconciliationStatus(str, enum.Enum):
    """Status of a reconciliation run."""

    PENDING = "pending"
    RUNNING = "running"
    MATCHING = "matching"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatchType(str, enum.Enum):
    """Type of match that was found."""

    EXACT = "exact"
    TOLERANCE = "tolerance"
    FUZZY = "fuzzy"
    SCORED = "scored"
    MANUAL = "manual"


class MatchDecisionStatus(str, enum.Enum):
    """Decision status for a match candidate."""

    PENDING = "pending"
    AUTO_MATCHED = "auto_matched"
    AUTO_REJECTED = "auto_rejected"
    REQUIRES_REVIEW = "requires_review"
    MANUALLY_MATCHED = "manually_matched"
    MANUALLY_REJECTED = "manually_rejected"


class ResolutionType(str, enum.Enum):
    """Type of match resolution."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class MatchStatus(str, enum.Enum):
    """Status of a reconciled match."""

    MATCHED = "matched"
    PARTIAL = "partial"
    UNMATCHED = "unmatched"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    ANOMALY_FLAGGED = "anomaly_flagged"
    REQUIRES_REVIEW = "requires_review"
    RESOLVED_MANUALLY = "resolved_manually"


class ReconciliationRun(BaseModel):
    """A single reconciliation run."""

    __tablename__ = "reconciliation_runs"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, values_callable=lambda x: [e.value for e in x]),
        default=ReconciliationStatus.PENDING,
        nullable=False,
        index=True,
    )
    parameters_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Statistics (populated after completion)
    total_left_records: Mapped[int | None] = mapped_column(default=0)
    total_right_records: Mapped[int | None] = mapped_column(default=0)
    total_matched: Mapped[int | None] = mapped_column(default=0)
    total_unmatched: Mapped[int | None] = mapped_column(default=0)
    total_exceptions: Mapped[int | None] = mapped_column(default=0)

    # Relationships
    triggered_by_user = relationship("User", back_populates="reconciliation_runs")
    match_candidates = relationship("MatchCandidate", back_populates="reconciliation_run")
    reconciled_matches = relationship("ReconciledMatch", back_populates="reconciliation_run")
    unmatched_records = relationship("UnmatchedRecord", back_populates="reconciliation_run")
    anomalies = relationship("Anomaly", back_populates="reconciliation_run")
    exceptions = relationship("Exception", back_populates="reconciliation_run")

    def __repr__(self) -> str:
        return f"<ReconciliationRun {self.name} status={self.status}>"

    @property
    def match_rate(self) -> float:
        """Calculate the match rate."""
        total = (self.total_left_records or 0) + (self.total_right_records or 0)
        if total == 0:
            return 0.0
        matched = self.total_matched or 0
        return (matched * 2) / total  # Each match covers 2 records


class MatchCandidate(BaseModel):
    """A potential match between two records."""

    __tablename__ = "match_candidates"

    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=False,
        index=True,
    )
    left_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_records.id"),
        nullable=False,
        index=True,
    )
    right_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_records.id"),
        nullable=False,
        index=True,
    )
    match_type: Mapped[MatchType] = mapped_column(
        Enum(MatchType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
    )
    feature_payload: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    decision_status: Mapped[MatchDecisionStatus] = mapped_column(
        Enum(MatchDecisionStatus, values_callable=lambda x: [e.value for e in x]),
        default=MatchDecisionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="match_candidates")
    left_record = relationship(
        "CanonicalRecord",
        foreign_keys=[left_record_id],
        back_populates="left_match_candidates",
    )
    right_record = relationship(
        "CanonicalRecord",
        foreign_keys=[right_record_id],
        back_populates="right_match_candidates",
    )

    __table_args__ = (
        Index("ix_match_candidates_records", "left_record_id", "right_record_id"),
        Index("ix_match_candidates_run_status", "reconciliation_run_id", "decision_status"),
    )

    def __repr__(self) -> str:
        return f"<MatchCandidate {self.left_record_id} <-> {self.right_record_id} score={self.score}>"


class ReconciledMatch(BaseModel):
    """A confirmed reconciled match (may contain multiple records)."""

    __tablename__ = "reconciled_matches"

    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=False,
        index=True,
    )
    match_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    resolution_type: Mapped[ResolutionType] = mapped_column(
        Enum(ResolutionType, values_callable=lambda x: [e.value for e in x]),
        default=ResolutionType.ONE_TO_ONE,
        nullable=False,
    )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, values_callable=lambda x: [e.value for e in x]),
        default=MatchStatus.MATCHED,
        nullable=False,
        index=True,
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
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

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="reconciled_matches")
    items = relationship("ReconciledMatchItem", back_populates="reconciled_match")

    def __repr__(self) -> str:
        return f"<ReconciledMatch group={self.match_group_id} status={self.status}>"


class ReconciledMatchItem(BaseModel):
    """Individual record within a reconciled match."""

    __tablename__ = "reconciled_match_items"

    reconciled_match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciled_matches.id"),
        nullable=False,
        index=True,
    )
    canonical_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_records.id"),
        nullable=False,
        index=True,
    )
    side: Mapped[str] = mapped_column(
        String(10),  # 'left' or 'right'
        nullable=False,
    )
    amount_contribution: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=20, scale=4),
        nullable=True,
    )

    # Relationships
    reconciled_match = relationship("ReconciledMatch", back_populates="items")
    canonical_record = relationship("CanonicalRecord", back_populates="reconciled_match_items")

    def __repr__(self) -> str:
        return f"<ReconciledMatchItem match={self.reconciled_match_id} side={self.side}>"


class UnmatchedRecord(BaseModel):
    """Record that could not be matched in a reconciliation run."""

    __tablename__ = "unmatched_records"

    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=False,
        index=True,
    )
    canonical_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_records.id"),
        nullable=False,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="unmatched_records")
    canonical_record = relationship("CanonicalRecord", back_populates="unmatched_records")

    def __repr__(self) -> str:
        return f"<UnmatchedRecord run={self.reconciliation_run_id} reason={self.reason_code}>"
