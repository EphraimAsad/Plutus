"""Anomaly detection service."""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, stdev
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from app.models.transaction import CanonicalRecord
from app.models.reconciliation import UnmatchedRecord

logger = get_logger(__name__)


class AnomalyConfig:
    """Configuration for anomaly detection rules."""

    def __init__(
        self,
        large_amount_threshold: Decimal = Decimal("100000"),
        large_amount_multiplier: float = 3.0,
        date_lag_threshold_days: int = 30,
        duplicate_similarity_threshold: float = 0.95,
        counterparty_repeat_threshold: int = 5,
        statistical_outlier_std: float = 3.0,
    ):
        self.large_amount_threshold = large_amount_threshold
        self.large_amount_multiplier = large_amount_multiplier
        self.date_lag_threshold_days = date_lag_threshold_days
        self.duplicate_similarity_threshold = duplicate_similarity_threshold
        self.counterparty_repeat_threshold = counterparty_repeat_threshold
        self.statistical_outlier_std = statistical_outlier_std


class AnomalyService:
    """Service for detecting anomalies in reconciliation data."""

    def __init__(self, db: AsyncSession, config: AnomalyConfig | None = None):
        """Initialize anomaly service."""
        self.db = db
        self.config = config or AnomalyConfig()

    async def detect_anomalies(
        self,
        reconciliation_run_id: uuid.UUID | None = None,
        source_system_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Run all anomaly detection rules.

        Args:
            reconciliation_run_id: Optional reconciliation run to analyze
            source_system_id: Optional source system to analyze

        Returns:
            Dictionary with detection results
        """
        logger.info(f"Running anomaly detection for run={reconciliation_run_id}, source={source_system_id}")

        results = {
            "large_amounts": await self._detect_large_amounts(source_system_id),
            "date_lags": await self._detect_date_lags(source_system_id),
            "duplicate_patterns": await self._detect_duplicate_patterns(source_system_id),
            "repeated_unmatched": await self._detect_repeated_unmatched_counterparties(reconciliation_run_id),
            "statistical_outliers": await self._detect_statistical_outliers(source_system_id),
        }

        total = sum(len(v) for v in results.values())
        logger.info(f"Anomaly detection complete: {total} anomalies found")

        return {
            "total_anomalies": total,
            "by_type": {k: len(v) for k, v in results.items()},
            "anomaly_ids": {k: [str(a.id) for a in v] for k, v in results.items()},
        }

    async def _detect_large_amounts(
        self,
        source_system_id: uuid.UUID | None = None,
    ) -> list[Anomaly]:
        """Detect unusually large transaction amounts."""
        anomalies = []

        # Get all amounts for baseline
        query = select(CanonicalRecord.amount).where(CanonicalRecord.amount.isnot(None))
        if source_system_id:
            query = query.where(CanonicalRecord.source_system_id == source_system_id)

        result = await self.db.execute(query)
        amounts = [row[0] for row in result.all() if row[0] is not None]

        if len(amounts) < 10:
            return anomalies

        # Calculate baseline statistics
        amounts_float = [float(a) for a in amounts]
        avg_amount = mean(amounts_float)
        threshold = max(
            float(self.config.large_amount_threshold),
            avg_amount * self.config.large_amount_multiplier,
        )

        # Find records exceeding threshold
        query = select(CanonicalRecord).where(
            CanonicalRecord.amount > Decimal(str(threshold))
        )
        if source_system_id:
            query = query.where(CanonicalRecord.source_system_id == source_system_id)

        result = await self.db.execute(query)
        large_records = result.scalars().all()

        for record in large_records:
            severity = self._calculate_amount_severity(record.amount, Decimal(str(avg_amount)))

            anomaly = Anomaly(
                canonical_record_id=record.id,
                anomaly_type=AnomalyType.UNUSUALLY_LARGE_AMOUNT,
                severity=severity,
                score=float(record.amount) / avg_amount if avg_amount > 0 else 0,
                details_json={
                    "amount": str(record.amount),
                    "average_amount": str(avg_amount),
                    "threshold": str(threshold),
                    "external_record_id": record.external_record_id,
                    "record_date": record.record_date.isoformat() if record.record_date else None,
                },
            )
            self.db.add(anomaly)
            anomalies.append(anomaly)

        await self.db.flush()
        return anomalies

    async def _detect_date_lags(
        self,
        source_system_id: uuid.UUID | None = None,
    ) -> list[Anomaly]:
        """Detect abnormal date lags between record date and settlement date."""
        anomalies = []

        query = select(CanonicalRecord).where(
            CanonicalRecord.record_date.isnot(None),
            CanonicalRecord.settlement_date.isnot(None),
        )
        if source_system_id:
            query = query.where(CanonicalRecord.source_system_id == source_system_id)

        result = await self.db.execute(query)
        records = result.scalars().all()

        for record in records:
            if record.record_date and record.settlement_date:
                lag_days = abs((record.settlement_date - record.record_date).days)

                if lag_days > self.config.date_lag_threshold_days:
                    severity = self._calculate_lag_severity(lag_days)

                    anomaly = Anomaly(
                        canonical_record_id=record.id,
                        anomaly_type=AnomalyType.ABNORMAL_DATE_LAG,
                        severity=severity,
                        score=lag_days / self.config.date_lag_threshold_days,
                        details_json={
                            "record_date": record.record_date.isoformat(),
                            "settlement_date": record.settlement_date.isoformat(),
                            "lag_days": lag_days,
                            "threshold_days": self.config.date_lag_threshold_days,
                            "external_record_id": record.external_record_id,
                        },
                    )
                    self.db.add(anomaly)
                    anomalies.append(anomaly)

        await self.db.flush()
        return anomalies

    async def _detect_duplicate_patterns(
        self,
        source_system_id: uuid.UUID | None = None,
    ) -> list[Anomaly]:
        """Detect potential duplicate transaction patterns."""
        anomalies = []

        # Find records with same amount, date, and similar reference
        query = select(
            CanonicalRecord.amount,
            CanonicalRecord.record_date,
            CanonicalRecord.currency,
            func.count(CanonicalRecord.id).label("count"),
            func.array_agg(CanonicalRecord.id).label("record_ids"),
        ).where(
            CanonicalRecord.amount.isnot(None),
            CanonicalRecord.record_date.isnot(None),
        ).group_by(
            CanonicalRecord.amount,
            CanonicalRecord.record_date,
            CanonicalRecord.currency,
        ).having(func.count(CanonicalRecord.id) > 1)

        if source_system_id:
            query = query.where(CanonicalRecord.source_system_id == source_system_id)

        result = await self.db.execute(query)
        groups = result.all()

        for amount, record_date, currency, count, record_ids in groups:
            if count >= 2:
                severity = AnomalySeverity.MEDIUM if count == 2 else AnomalySeverity.HIGH

                anomaly = Anomaly(
                    anomaly_type=AnomalyType.DUPLICATE_PATTERN,
                    severity=severity,
                    score=float(count),
                    details_json={
                        "amount": str(amount),
                        "record_date": record_date.isoformat() if record_date else None,
                        "currency": currency,
                        "duplicate_count": count,
                        "record_ids": [str(rid) for rid in record_ids] if record_ids else [],
                    },
                )
                self.db.add(anomaly)
                anomalies.append(anomaly)

        await self.db.flush()
        return anomalies

    async def _detect_repeated_unmatched_counterparties(
        self,
        reconciliation_run_id: uuid.UUID | None = None,
    ) -> list[Anomaly]:
        """Detect counterparties that frequently appear in unmatched records."""
        anomalies = []

        if not reconciliation_run_id:
            return anomalies

        # Get unmatched records for this run
        query = select(UnmatchedRecord.canonical_record_id).where(
            UnmatchedRecord.reconciliation_run_id == reconciliation_run_id
        )
        result = await self.db.execute(query)
        unmatched_ids = [row[0] for row in result.all()]

        if not unmatched_ids:
            return anomalies

        # Get counterparty frequency
        query = select(
            CanonicalRecord.counterparty,
            func.count(CanonicalRecord.id).label("count"),
        ).where(
            CanonicalRecord.id.in_(unmatched_ids),
            CanonicalRecord.counterparty.isnot(None),
        ).group_by(CanonicalRecord.counterparty).having(
            func.count(CanonicalRecord.id) >= self.config.counterparty_repeat_threshold
        )

        result = await self.db.execute(query)
        frequent_counterparties = result.all()

        for counterparty, count in frequent_counterparties:
            severity = AnomalySeverity.MEDIUM
            if count >= self.config.counterparty_repeat_threshold * 2:
                severity = AnomalySeverity.HIGH

            anomaly = Anomaly(
                reconciliation_run_id=reconciliation_run_id,
                anomaly_type=AnomalyType.REPEATED_UNMATCHED_COUNTERPARTY,
                severity=severity,
                score=float(count) / self.config.counterparty_repeat_threshold,
                details_json={
                    "counterparty": counterparty,
                    "unmatched_count": count,
                    "threshold": self.config.counterparty_repeat_threshold,
                },
            )
            self.db.add(anomaly)
            anomalies.append(anomaly)

        await self.db.flush()
        return anomalies

    async def _detect_statistical_outliers(
        self,
        source_system_id: uuid.UUID | None = None,
    ) -> list[Anomaly]:
        """Detect statistical outliers in transaction amounts."""
        anomalies = []

        # Get all amounts
        query = select(CanonicalRecord).where(CanonicalRecord.amount.isnot(None))
        if source_system_id:
            query = query.where(CanonicalRecord.source_system_id == source_system_id)

        result = await self.db.execute(query)
        records = result.scalars().all()

        if len(records) < 30:  # Need sufficient data for statistical analysis
            return anomalies

        amounts = [float(r.amount) for r in records if r.amount is not None]
        avg = mean(amounts)
        std = stdev(amounts) if len(amounts) > 1 else 0

        if std == 0:
            return anomalies

        threshold = self.config.statistical_outlier_std * std

        for record in records:
            if record.amount is not None:
                deviation = abs(float(record.amount) - avg)
                if deviation > threshold:
                    z_score = deviation / std

                    severity = AnomalySeverity.LOW
                    if z_score > 4:
                        severity = AnomalySeverity.HIGH
                    elif z_score > 3.5:
                        severity = AnomalySeverity.MEDIUM

                    anomaly = Anomaly(
                        canonical_record_id=record.id,
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        severity=severity,
                        score=z_score,
                        details_json={
                            "amount": str(record.amount),
                            "mean": str(avg),
                            "std_dev": str(std),
                            "z_score": z_score,
                            "threshold_std": self.config.statistical_outlier_std,
                            "external_record_id": record.external_record_id,
                        },
                    )
                    self.db.add(anomaly)
                    anomalies.append(anomaly)

        await self.db.flush()
        return anomalies

    def _calculate_amount_severity(
        self,
        amount: Decimal,
        average: Decimal,
    ) -> AnomalySeverity:
        """Calculate severity for large amount anomaly."""
        if average == 0:
            return AnomalySeverity.HIGH

        ratio = float(amount / average)

        if ratio > 10:
            return AnomalySeverity.CRITICAL
        elif ratio > 5:
            return AnomalySeverity.HIGH
        elif ratio > 3:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def _calculate_lag_severity(self, lag_days: int) -> AnomalySeverity:
        """Calculate severity for date lag anomaly."""
        if lag_days > 90:
            return AnomalySeverity.CRITICAL
        elif lag_days > 60:
            return AnomalySeverity.HIGH
        elif lag_days > 45:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    async def get_anomaly_summary(
        self,
        reconciliation_run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Get summary statistics for anomalies."""
        query = select(
            Anomaly.anomaly_type,
            Anomaly.severity,
            func.count(Anomaly.id),
        ).group_by(Anomaly.anomaly_type, Anomaly.severity)

        if reconciliation_run_id:
            query = query.where(Anomaly.reconciliation_run_id == reconciliation_run_id)

        result = await self.db.execute(query)
        rows = result.all()

        summary = {
            "by_type": defaultdict(int),
            "by_severity": defaultdict(int),
            "total": 0,
        }

        for anomaly_type, severity, count in rows:
            summary["by_type"][anomaly_type.value] += count
            summary["by_severity"][severity.value] += count
            summary["total"] += count

        return dict(summary)


async def get_anomaly_service(db: AsyncSession) -> AnomalyService:
    """Factory function to create anomaly service."""
    return AnomalyService(db)
