"""Audit logging service for tracking user actions."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditLog, AuditAction

logger = get_logger(__name__)


class AuditService:
    """Service for creating and managing audit logs."""

    def __init__(self, db: AsyncSession):
        """Initialize audit service."""
        self.db = db

    async def log(
        self,
        action_type: str,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        metadata: dict[str, Any] | None = None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Create an audit log entry.

        Args:
            action_type: The action performed (use AuditAction constants)
            entity_type: Type of entity affected (e.g., 'source', 'user', 'reconciliation_run')
            entity_id: ID of the affected entity
            actor_user_id: ID of the user who performed the action
            metadata: Additional metadata about the action
            before_json: Previous values (for updates)
            after_json: New values (for updates)

        Returns:
            Created AuditLog entry
        """
        audit_log = AuditLog(
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata or {},
            before_json=before_json,
            after_json=after_json,
        )
        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            f"Audit: {action_type} on {entity_type}:{entity_id} by user {actor_user_id}"
        )
        return audit_log

    async def log_create(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        entity_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a create action."""
        log_metadata = metadata or {}
        if entity_name:
            log_metadata["name"] = entity_name

        action_map = {
            "source": AuditAction.SOURCE_CREATED,
            "user": AuditAction.USER_CREATED,
            "reconciliation_run": AuditAction.RECONCILIATION_STARTED,
            "ingestion_job": AuditAction.INGESTION_STARTED,
            "report": AuditAction.REPORT_GENERATED,
            "exception": AuditAction.EXCEPTION_CREATED,
        }
        action_type = action_map.get(entity_type, f"{entity_type}_created")

        return await self.log(
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            metadata=log_metadata,
        )

    async def log_update(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log an update action."""
        action_map = {
            "source": AuditAction.SOURCE_UPDATED,
            "user": AuditAction.USER_UPDATED,
        }
        action_type = action_map.get(entity_type, f"{entity_type}_updated")

        return await self.log(
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            before_json=before_json,
            after_json=after_json,
            metadata=metadata,
        )

    async def log_delete(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        entity_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a delete action."""
        log_metadata = metadata or {}
        if entity_name:
            log_metadata["name"] = entity_name

        return await self.log(
            action_type=f"{entity_type}_deleted",
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            metadata=log_metadata,
        )

    async def log_exception_action(
        self,
        exception_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log an exception-related action."""
        action_map = {
            "assign": AuditAction.EXCEPTION_ASSIGNED,
            "resolve": AuditAction.EXCEPTION_RESOLVED,
            "dismiss": AuditAction.EXCEPTION_DISMISSED,
            "escalate": AuditAction.EXCEPTION_ESCALATED,
            "note": AuditAction.EXCEPTION_NOTE_ADDED,
        }
        action_type = action_map.get(action, f"exception_{action}")

        return await self.log(
            action_type=action_type,
            entity_type="exception",
            entity_id=exception_id,
            actor_user_id=actor_user_id,
            metadata=metadata,
        )


async def get_audit_service(db: AsyncSession) -> AuditService:
    """Factory function to create audit service."""
    return AuditService(db)
