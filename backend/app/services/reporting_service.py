"""Reporting service for generating operational reports."""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.report import Report, ReportStatus, ReportType, ReportFormat, ReportSnapshot
from app.models.reconciliation import ReconciliationRun, ReconciliationStatus, MatchCandidate, UnmatchedRecord
from app.models.exception import Exception as ExceptionModel, ExceptionStatus, ExceptionSeverity
from app.models.anomaly import Anomaly, AnomalySeverity
from app.models.ingestion import IngestionJob, IngestionJobStatus
from app.models.transaction import CanonicalRecord

logger = get_logger(__name__)


class ReportingService:
    """Service for generating various operational reports."""

    def __init__(self, db: AsyncSession):
        """Initialize reporting service."""
        self.db = db

    async def generate_report(
        self,
        report_id: uuid.UUID,
        file_format: ReportFormat = ReportFormat.CSV,
    ) -> dict[str, Any]:
        """Generate a report based on its type.

        Args:
            report_id: ID of the report to generate
            file_format: Output format

        Returns:
            Report data dictionary
        """
        # Get report record
        result = await self.db.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise ValueError(f"Report not found: {report_id}")

        # Update status to generating
        report.status = ReportStatus.GENERATING
        await self.db.flush()

        try:
            # Generate based on type
            generators = {
                ReportType.RECONCILIATION_SUMMARY: self._generate_reconciliation_summary,
                ReportType.UNMATCHED_ITEMS: self._generate_unmatched_items,
                ReportType.EXCEPTION_BACKLOG: self._generate_exception_backlog,
                ReportType.ANOMALY_REPORT: self._generate_anomaly_report,
                ReportType.INGESTION_HEALTH: self._generate_ingestion_health,
                ReportType.OPERATIONAL_SUMMARY: self._generate_operational_summary,
                ReportType.MATCH_ANALYSIS: self._generate_match_analysis,
            }

            generator = generators.get(report.report_type)
            if not generator:
                raise ValueError(f"Unknown report type: {report.report_type}")

            data = await generator(report.filters_json, report.parameters_json)

            # Save snapshot
            snapshot = ReportSnapshot(
                report_id=report_id,
                snapshot_json=data,
            )
            self.db.add(snapshot)

            # Export to file
            from app.services.export_service import ExportService
            export_service = ExportService()
            file_path = export_service.export(
                report_id=report_id,
                data=data,
                format=file_format,
                title=report.title,
            )

            # Update report status
            report.status = ReportStatus.COMPLETED
            report.generated_at = datetime.now(timezone.utc)
            report.file_format = file_format
            report.file_path = file_path

            await self.db.flush()

            return {
                **data,
                "file_path": file_path,
                "record_count": data.get("total_runs", 0) or len(data.get("runs", [])) or len(data.get("items", [])),
            }

        except Exception as e:
            report.status = ReportStatus.FAILED
            report.error_message = str(e)[:2000]
            await self.db.flush()
            raise

    async def _generate_reconciliation_summary(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate reconciliation summary report."""
        # Get date range
        days = parameters.get("days", 30)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get reconciliation runs
        query = select(ReconciliationRun).where(
            ReconciliationRun.created_at >= start_date
        ).order_by(ReconciliationRun.created_at.desc())

        result = await self.db.execute(query)
        runs = result.scalars().all()

        # Aggregate statistics
        total_runs = len(runs)
        completed_runs = len([r for r in runs if r.status == ReconciliationStatus.COMPLETED])
        total_records = sum((r.total_left_records or 0) + (r.total_right_records or 0) for r in runs)
        total_matched = sum(r.total_matched or 0 for r in runs)
        total_unmatched = sum(r.total_unmatched or 0 for r in runs)
        total_exceptions = sum(r.total_exceptions or 0 for r in runs)

        avg_match_rate = 0
        if runs:
            rates = [r.match_rate for r in runs if r.match_rate is not None]
            avg_match_rate = sum(rates) / len(rates) if rates else 0

        return {
            "report_type": "reconciliation_summary",
            "period_days": days,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_runs": total_runs,
                "completed_runs": completed_runs,
                "total_records_processed": total_records,
                "total_matched": total_matched,
                "total_unmatched": total_unmatched,
                "total_exceptions": total_exceptions,
                "average_match_rate": round(avg_match_rate, 4),
            },
            "runs": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "status": r.status.value,
                    "created_at": r.created_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "left_records": r.total_left_records,
                    "right_records": r.total_right_records,
                    "matched": r.total_matched,
                    "unmatched": r.total_unmatched,
                    "exceptions": r.total_exceptions,
                    "match_rate": r.match_rate,
                }
                for r in runs
            ],
        }

    async def _generate_unmatched_items(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate unmatched items report."""
        run_id = filters.get("reconciliation_run_id")

        query = select(UnmatchedRecord, CanonicalRecord).join(
            CanonicalRecord,
            UnmatchedRecord.canonical_record_id == CanonicalRecord.id
        )

        if run_id:
            query = query.where(UnmatchedRecord.reconciliation_run_id == uuid.UUID(run_id))

        query = query.limit(parameters.get("limit", 1000))

        result = await self.db.execute(query)
        rows = result.all()

        items = []
        for unmatched, record in rows:
            items.append({
                "unmatched_id": str(unmatched.id),
                "record_id": str(record.id),
                "external_record_id": record.external_record_id,
                "source_system_id": str(record.source_system_id),
                "record_date": record.record_date.isoformat() if record.record_date else None,
                "amount": str(record.amount) if record.amount else None,
                "currency": record.currency,
                "reference_code": record.reference_code,
                "description": record.description,
                "counterparty": record.counterparty,
                "reason_code": unmatched.reason_code,
            })

        return {
            "report_type": "unmatched_items",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": filters,
            "total_items": len(items),
            "items": items,
        }

    async def _generate_exception_backlog(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate exception backlog report."""
        # Get open exceptions
        query = select(ExceptionModel).where(
            ExceptionModel.status.in_([ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW])
        ).order_by(ExceptionModel.severity.desc(), ExceptionModel.created_at)

        if filters.get("severity"):
            query = query.where(ExceptionModel.severity == filters["severity"])

        result = await self.db.execute(query)
        exceptions = result.scalars().all()

        # Group by severity
        by_severity = {}
        for e in exceptions:
            sev = e.severity.value
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append({
                "id": str(e.id),
                "title": e.title,
                "exception_type": e.exception_type.value,
                "status": e.status.value,
                "created_at": e.created_at.isoformat(),
                "age_hours": (datetime.now(timezone.utc) - e.created_at).total_seconds() / 3600,
                "assigned_to": str(e.assigned_to) if e.assigned_to else None,
            })

        # Calculate aging statistics
        ages = [(datetime.now(timezone.utc) - e.created_at).total_seconds() / 3600 for e in exceptions]
        avg_age = sum(ages) / len(ages) if ages else 0
        max_age = max(ages) if ages else 0

        return {
            "report_type": "exception_backlog",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_open": len(exceptions),
                "by_severity": {k: len(v) for k, v in by_severity.items()},
                "average_age_hours": round(avg_age, 2),
                "max_age_hours": round(max_age, 2),
            },
            "exceptions_by_severity": by_severity,
        }

    async def _generate_anomaly_report(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate anomaly detection report."""
        days = parameters.get("days", 30)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = select(Anomaly).where(
            Anomaly.created_at >= start_date
        ).order_by(Anomaly.severity.desc(), Anomaly.created_at.desc())

        result = await self.db.execute(query)
        anomalies = result.scalars().all()

        # Group by type
        by_type = {}
        for a in anomalies:
            atype = a.anomaly_type.value
            if atype not in by_type:
                by_type[atype] = []
            by_type[atype].append({
                "id": str(a.id),
                "severity": a.severity.value,
                "score": a.score,
                "details": a.details_json,
                "created_at": a.created_at.isoformat(),
            })

        # Group by severity
        by_severity = {}
        for a in anomalies:
            sev = a.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "report_type": "anomaly_report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "summary": {
                "total_anomalies": len(anomalies),
                "by_type": {k: len(v) for k, v in by_type.items()},
                "by_severity": by_severity,
            },
            "anomalies_by_type": by_type,
        }

    async def _generate_ingestion_health(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate ingestion health report."""
        days = parameters.get("days", 7)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = select(IngestionJob).where(
            IngestionJob.created_at >= start_date
        ).order_by(IngestionJob.created_at.desc())

        result = await self.db.execute(query)
        jobs = result.scalars().all()

        # Aggregate by status
        by_status = {}
        for j in jobs:
            status = j.status.value
            by_status[status] = by_status.get(status, 0) + 1

        # Calculate totals
        total_rows = sum(j.rows_received or 0 for j in jobs)
        valid_rows = sum(j.rows_valid or 0 for j in jobs)
        invalid_rows = sum(j.rows_invalid or 0 for j in jobs)

        validation_rate = valid_rows / total_rows if total_rows > 0 else 0

        # Processing times
        completed_jobs = [j for j in jobs if j.started_at and j.completed_at]
        processing_times = [
            (j.completed_at - j.started_at).total_seconds()
            for j in completed_jobs
        ]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

        return {
            "report_type": "ingestion_health",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "summary": {
                "total_jobs": len(jobs),
                "by_status": by_status,
                "total_rows_processed": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "validation_rate": round(validation_rate, 4),
                "avg_processing_seconds": round(avg_processing_time, 2),
            },
            "jobs": [
                {
                    "id": str(j.id),
                    "source_system_id": str(j.source_system_id),
                    "file_name": j.file_name,
                    "status": j.status.value,
                    "rows_received": j.rows_received,
                    "rows_valid": j.rows_valid,
                    "rows_invalid": j.rows_invalid,
                    "created_at": j.created_at.isoformat(),
                }
                for j in jobs[:100]  # Limit to 100 jobs
            ],
        }

    async def _generate_operational_summary(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate overall operational summary report."""
        days = parameters.get("days", 30)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get ingestion stats
        ingestion_result = await self.db.execute(
            select(
                func.count(IngestionJob.id),
                func.sum(IngestionJob.rows_received),
                func.sum(IngestionJob.rows_valid),
            ).where(IngestionJob.created_at >= start_date)
        )
        ingestion_stats = ingestion_result.one()

        # Get reconciliation stats
        recon_result = await self.db.execute(
            select(
                func.count(ReconciliationRun.id),
                func.sum(ReconciliationRun.total_matched),
                func.sum(ReconciliationRun.total_unmatched),
            ).where(ReconciliationRun.created_at >= start_date)
        )
        recon_stats = recon_result.one()

        # Get exception stats
        exception_result = await self.db.execute(
            select(func.count(ExceptionModel.id)).where(
                ExceptionModel.created_at >= start_date
            )
        )
        total_exceptions = exception_result.scalar() or 0

        resolved_result = await self.db.execute(
            select(func.count(ExceptionModel.id)).where(
                and_(
                    ExceptionModel.created_at >= start_date,
                    ExceptionModel.status == ExceptionStatus.RESOLVED,
                )
            )
        )
        resolved_exceptions = resolved_result.scalar() or 0

        # Get anomaly stats
        anomaly_result = await self.db.execute(
            select(func.count(Anomaly.id)).where(
                Anomaly.created_at >= start_date
            )
        )
        total_anomalies = anomaly_result.scalar() or 0

        return {
            "report_type": "operational_summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "ingestion": {
                "total_jobs": ingestion_stats[0] or 0,
                "total_rows": ingestion_stats[1] or 0,
                "valid_rows": ingestion_stats[2] or 0,
            },
            "reconciliation": {
                "total_runs": recon_stats[0] or 0,
                "total_matched": recon_stats[1] or 0,
                "total_unmatched": recon_stats[2] or 0,
            },
            "exceptions": {
                "total_created": total_exceptions,
                "total_resolved": resolved_exceptions,
                "resolution_rate": resolved_exceptions / total_exceptions if total_exceptions > 0 else 0,
            },
            "anomalies": {
                "total_detected": total_anomalies,
            },
        }

    async def _generate_match_analysis(
        self,
        filters: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate match analysis report."""
        run_id = filters.get("reconciliation_run_id")

        if not run_id:
            raise ValueError("reconciliation_run_id filter is required")

        # Get match candidates
        query = select(MatchCandidate).where(
            MatchCandidate.reconciliation_run_id == uuid.UUID(run_id)
        )

        result = await self.db.execute(query)
        candidates = result.scalars().all()

        # Analyze by match type
        by_type = {}
        by_status = {}
        score_distribution = {"0.9-1.0": 0, "0.8-0.9": 0, "0.7-0.8": 0, "<0.7": 0}

        for c in candidates:
            # By type
            mtype = c.match_type.value
            by_type[mtype] = by_type.get(mtype, 0) + 1

            # By status
            status = c.decision_status.value
            by_status[status] = by_status.get(status, 0) + 1

            # Score distribution
            if c.score >= 0.9:
                score_distribution["0.9-1.0"] += 1
            elif c.score >= 0.8:
                score_distribution["0.8-0.9"] += 1
            elif c.score >= 0.7:
                score_distribution["0.7-0.8"] += 1
            else:
                score_distribution["<0.7"] += 1

        return {
            "report_type": "match_analysis",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reconciliation_run_id": run_id,
            "summary": {
                "total_candidates": len(candidates),
                "by_match_type": by_type,
                "by_decision_status": by_status,
                "score_distribution": score_distribution,
            },
        }


async def get_reporting_service(db: AsyncSession) -> ReportingService:
    """Factory function to create reporting service."""
    return ReportingService(db)
