"""Report generation models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ReportType(str, enum.Enum):
    """Type of report."""

    RECONCILIATION_SUMMARY = "reconciliation_summary"
    UNMATCHED_ITEMS = "unmatched_items"
    EXCEPTION_BACKLOG = "exception_backlog"
    ANOMALY_REPORT = "anomaly_report"
    INGESTION_HEALTH = "ingestion_health"
    OPERATIONAL_SUMMARY = "operational_summary"
    MATCH_ANALYSIS = "match_analysis"
    TREND_ANALYSIS = "trend_analysis"


class ReportStatus(str, enum.Enum):
    """Status of report generation."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportFormat(str, enum.Enum):
    """Output format for report export."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class Report(BaseModel):
    """Generated report."""

    __tablename__ = "reports"

    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    filters_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, values_callable=lambda x: [e.value for e in x]),
        default=ReportStatus.PENDING,
        nullable=False,
        index=True,
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    file_format: Mapped[ReportFormat | None] = mapped_column(
        Enum(ReportFormat, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    generated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
    )

    # Report metadata
    parameters_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    generated_by_user = relationship("User", back_populates="reports")
    snapshots = relationship("ReportSnapshot", back_populates="report")
    ai_explanations = relationship("AIExplanation", back_populates="report")

    __table_args__ = (
        Index("ix_reports_type_generated", "report_type", "generated_at"),
    )

    def __repr__(self) -> str:
        return f"<Report {self.title} type={self.report_type}>"


class ReportSnapshot(BaseModel):
    """Snapshot of data used to generate a report."""

    __tablename__ = "report_snapshots"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id"),
        nullable=False,
        index=True,
    )
    snapshot_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Relationships
    report = relationship("Report", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<ReportSnapshot report={self.report_id}>"
