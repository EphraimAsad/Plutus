"""Anomaly detection models."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AnomalyType(str, enum.Enum):
    """Type of anomaly detected."""

    DUPLICATE_PATTERN = "duplicate_pattern"
    UNUSUALLY_LARGE_AMOUNT = "unusually_large_amount"
    ABNORMAL_DATE_LAG = "abnormal_date_lag"
    REPEATED_UNMATCHED_COUNTERPARTY = "repeated_unmatched_counterparty"
    SUSPICIOUS_CLUSTERING = "suspicious_clustering"
    VOLUME_SPIKE = "volume_spike"
    AMOUNT_PATTERN = "amount_pattern"
    REFERENCE_ANOMALY = "reference_anomaly"
    STATISTICAL_OUTLIER = "statistical_outlier"


class AnomalySeverity(str, enum.Enum):
    """Severity level of an anomaly."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Anomaly(BaseModel):
    """Detected anomaly in reconciliation data."""

    __tablename__ = "anomalies"

    reconciliation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id"),
        nullable=True,
        index=True,
    )
    canonical_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_records.id"),
        nullable=True,
        index=True,
    )
    anomaly_type: Mapped[AnomalyType] = mapped_column(
        Enum(AnomalyType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    severity: Mapped[AnomalySeverity] = mapped_column(
        Enum(AnomalySeverity, values_callable=lambda x: [e.value for e in x]),
        default=AnomalySeverity.MEDIUM,
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    details_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    reconciliation_run = relationship("ReconciliationRun", back_populates="anomalies")
    canonical_record = relationship("CanonicalRecord", back_populates="anomalies")

    __table_args__ = (
        Index("ix_anomalies_run_severity", "reconciliation_run_id", "severity"),
    )

    def __repr__(self) -> str:
        return f"<Anomaly type={self.anomaly_type} severity={self.severity}>"

    @property
    def description(self) -> str:
        """Get human-readable description of the anomaly."""
        descriptions = {
            AnomalyType.DUPLICATE_PATTERN: "Potential duplicate transaction pattern detected",
            AnomalyType.UNUSUALLY_LARGE_AMOUNT: "Transaction amount is unusually large",
            AnomalyType.ABNORMAL_DATE_LAG: "Abnormal time gap between related transactions",
            AnomalyType.REPEATED_UNMATCHED_COUNTERPARTY: "Counterparty appears frequently in unmatched records",
            AnomalyType.SUSPICIOUS_CLUSTERING: "Suspicious clustering of transactions detected",
            AnomalyType.VOLUME_SPIKE: "Unusual spike in transaction volume",
            AnomalyType.AMOUNT_PATTERN: "Suspicious pattern in transaction amounts",
            AnomalyType.REFERENCE_ANOMALY: "Anomaly detected in reference codes",
            AnomalyType.STATISTICAL_OUTLIER: "Statistical outlier detected",
        }
        return descriptions.get(self.anomaly_type, "Unknown anomaly type")
