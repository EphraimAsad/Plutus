"""Anomaly management routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from app.models.transaction import CanonicalRecord
from app.api.deps import CurrentUser

router = APIRouter()


@router.get("")
async def list_anomalies(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    anomaly_type: str | None = None,
    severity: str | None = None,
    reconciliation_run_id: uuid.UUID | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> dict:
    """List anomalies with optional filters."""
    query = select(Anomaly).options(
        joinedload(Anomaly.canonical_record)
    ).order_by(Anomaly.created_at.desc())

    if anomaly_type:
        try:
            type_enum = AnomalyType(anomaly_type)
            query = query.where(Anomaly.anomaly_type == type_enum)
        except ValueError:
            pass

    if severity:
        try:
            sev_enum = AnomalySeverity(severity)
            query = query.where(Anomaly.severity == sev_enum)
        except ValueError:
            pass

    if reconciliation_run_id:
        query = query.where(Anomaly.reconciliation_run_id == reconciliation_run_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    anomalies = result.unique().scalars().all()

    return {
        "items": [
            {
                "id": str(a.id),
                "reconciliation_run_id": str(a.reconciliation_run_id) if a.reconciliation_run_id else None,
                "canonical_record_id": str(a.canonical_record_id) if a.canonical_record_id else None,
                "anomaly_type": a.anomaly_type.value,
                "severity": a.severity.value,
                "score": a.score,
                "description": a.description,
                "details": a.details_json,
                "created_at": a.created_at.isoformat(),
                "record": {
                    "id": str(a.canonical_record.id),
                    "external_record_id": a.canonical_record.external_record_id,
                    "amount": float(a.canonical_record.amount) if a.canonical_record.amount else None,
                    "currency": a.canonical_record.currency,
                    "counterparty": a.canonical_record.counterparty,
                    "record_date": a.canonical_record.record_date.isoformat() if a.canonical_record.record_date else None,
                } if a.canonical_record else None,
            }
            for a in anomalies
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/summary")
async def get_anomaly_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    reconciliation_run_id: uuid.UUID | None = None,
) -> dict:
    """Get summary statistics for anomalies."""
    base_query = select(Anomaly)
    if reconciliation_run_id:
        base_query = base_query.where(Anomaly.reconciliation_run_id == reconciliation_run_id)

    # Count by type
    type_counts = {}
    for atype in AnomalyType:
        count_query = select(func.count()).select_from(
            base_query.where(Anomaly.anomaly_type == atype).subquery()
        )
        result = await db.execute(count_query)
        count = result.scalar() or 0
        if count > 0:
            type_counts[atype.value] = count

    # Count by severity
    severity_counts = {}
    for sev in AnomalySeverity:
        count_query = select(func.count()).select_from(
            base_query.where(Anomaly.severity == sev).subquery()
        )
        result = await db.execute(count_query)
        count = result.scalar() or 0
        if count > 0:
            severity_counts[sev.value] = count

    # Total count
    total_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    return {
        "total": total,
        "by_type": type_counts,
        "by_severity": severity_counts,
    }


@router.get("/{anomaly_id}")
async def get_anomaly(
    anomaly_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get anomaly details."""
    result = await db.execute(
        select(Anomaly)
        .options(joinedload(Anomaly.canonical_record))
        .where(Anomaly.id == anomaly_id)
    )
    anomaly = result.unique().scalar_one_or_none()

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly not found",
        )

    return {
        "id": str(anomaly.id),
        "reconciliation_run_id": str(anomaly.reconciliation_run_id) if anomaly.reconciliation_run_id else None,
        "canonical_record_id": str(anomaly.canonical_record_id) if anomaly.canonical_record_id else None,
        "anomaly_type": anomaly.anomaly_type.value,
        "severity": anomaly.severity.value,
        "score": anomaly.score,
        "description": anomaly.description,
        "details": anomaly.details_json,
        "created_at": anomaly.created_at.isoformat(),
        "record": {
            "id": str(anomaly.canonical_record.id),
            "external_record_id": anomaly.canonical_record.external_record_id,
            "amount": float(anomaly.canonical_record.amount) if anomaly.canonical_record.amount else None,
            "currency": anomaly.canonical_record.currency,
            "counterparty": anomaly.canonical_record.counterparty,
            "description": anomaly.canonical_record.description,
            "record_date": anomaly.canonical_record.record_date.isoformat() if anomaly.canonical_record.record_date else None,
            "settlement_date": anomaly.canonical_record.settlement_date.isoformat() if anomaly.canonical_record.settlement_date else None,
        } if anomaly.canonical_record else None,
    }


@router.get("/types")
async def get_anomaly_types(
    current_user: CurrentUser,
) -> dict:
    """Get available anomaly types and severities."""
    return {
        "types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in AnomalyType
        ],
        "severities": [
            {"value": s.value, "label": s.value.title()}
            for s in AnomalySeverity
        ],
    }
