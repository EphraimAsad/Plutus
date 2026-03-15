"""SQLAlchemy models for Plutus."""

from app.models.user import User, UserRole
from app.models.source import SourceSystem, SourceSchemaMapping
from app.models.ingestion import IngestionJob, RawRecord, IngestionJobStatus
from app.models.transaction import ValidationResult, CanonicalRecord
from app.models.reconciliation import (
    ReconciliationRun,
    MatchCandidate,
    ReconciledMatch,
    ReconciledMatchItem,
    UnmatchedRecord,
    ReconciliationStatus,
    MatchDecisionStatus,
    ResolutionType,
)
from app.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from app.models.exception import Exception as ExceptionModel, ExceptionType, ExceptionStatus, ExceptionSeverity
from app.models.report import Report, ReportSnapshot, ReportType, ReportStatus
from app.models.ai_explanation import AIExplanation, AIExplanationStatus
from app.models.audit import AuditLog

__all__ = [
    # User
    "User",
    "UserRole",
    # Source
    "SourceSystem",
    "SourceSchemaMapping",
    # Ingestion
    "IngestionJob",
    "IngestionJobStatus",
    "RawRecord",
    # Transaction
    "ValidationResult",
    "CanonicalRecord",
    # Reconciliation
    "ReconciliationRun",
    "ReconciliationStatus",
    "MatchCandidate",
    "MatchDecisionStatus",
    "ReconciledMatch",
    "ReconciledMatchItem",
    "ResolutionType",
    "UnmatchedRecord",
    # Anomaly
    "Anomaly",
    "AnomalyType",
    "AnomalySeverity",
    # Exception
    "ExceptionModel",
    "ExceptionType",
    "ExceptionStatus",
    "ExceptionSeverity",
    # Report
    "Report",
    "ReportSnapshot",
    "ReportType",
    "ReportStatus",
    # AI
    "AIExplanation",
    "AIExplanationStatus",
    # Audit
    "AuditLog",
]
