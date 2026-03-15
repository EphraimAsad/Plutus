"""Audit log routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse, AuditLogListResponse
from app.api.deps import CurrentUser, AdminUser

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    current_user: AdminUser,  # Only admins can view audit logs
    db: Annotated[AsyncSession, Depends(get_db)],
    action_type: str | None = None,
    entity_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AuditLogListResponse:
    """List audit logs with filtering (admin only)."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if action_type:
        query = query.where(AuditLog.action_type == action_type)

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)

    if actor_user_id:
        query = query.where(AuditLog.actor_user_id == actor_user_id)

    # Get total count
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    logs = result.scalars().all()

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=str(log.id),
                actor_user_id=str(log.actor_user_id) if log.actor_user_id else None,
                action_type=log.action_type,
                entity_type=log.entity_type,
                entity_id=str(log.entity_id) if log.entity_id else None,
                before_json=log.before_json,
                after_json=log.after_json,
                metadata_json=log.metadata_json,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{entity_type}/{entity_id}", response_model=list[AuditLogResponse])
async def get_entity_audit_history(
    entity_type: str,
    entity_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[AuditLogResponse]:
    """Get audit history for a specific entity."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        AuditLogResponse(
            id=str(log.id),
            actor_user_id=str(log.actor_user_id) if log.actor_user_id else None,
            action_type=log.action_type,
            entity_type=log.entity_type,
            entity_id=str(log.entity_id) if log.entity_id else None,
            before_json=log.before_json,
            after_json=log.after_json,
            metadata_json=log.metadata_json,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
