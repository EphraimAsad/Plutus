"""User model and role definitions."""

import enum
import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """User role enumeration."""

    ADMIN = "admin"
    OPERATIONS_ANALYST = "operations_analyst"
    OPERATIONS_MANAGER = "operations_manager"
    READ_ONLY = "read_only"


class User(BaseModel):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.READ_ONLY,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    source_systems = relationship("SourceSystem", back_populates="created_by_user")
    ingestion_jobs = relationship("IngestionJob", back_populates="triggered_by_user")
    reconciliation_runs = relationship("ReconciliationRun", back_populates="triggered_by_user")
    assigned_exceptions = relationship(
        "Exception",
        foreign_keys="Exception.assigned_to",
        back_populates="assigned_to_user",
    )
    resolved_exceptions = relationship(
        "Exception",
        foreign_keys="Exception.resolved_by",
        back_populates="resolved_by_user",
    )
    reports = relationship("Report", back_populates="generated_by_user")
    ai_explanations = relationship("AIExplanation", back_populates="requested_by_user")
    audit_logs = relationship("AuditLog", back_populates="actor_user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN

    @property
    def can_manage_sources(self) -> bool:
        """Check if user can manage source systems."""
        return self.role == UserRole.ADMIN

    @property
    def can_run_reconciliation(self) -> bool:
        """Check if user can run reconciliation."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATIONS_ANALYST)

    @property
    def can_resolve_exceptions(self) -> bool:
        """Check if user can resolve exceptions."""
        return self.role in (UserRole.ADMIN, UserRole.OPERATIONS_ANALYST)

    @property
    def can_generate_reports(self) -> bool:
        """Check if user can generate reports."""
        return self.role in (
            UserRole.ADMIN,
            UserRole.OPERATIONS_ANALYST,
            UserRole.OPERATIONS_MANAGER,
        )
