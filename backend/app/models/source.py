"""Source system and schema mapping models."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, utc_now


class SourceType(str, enum.Enum):
    """Type of source system."""

    CSV = "csv"
    XLSX = "xlsx"
    API = "api"
    DATABASE = "database"


class SourceSystem(BaseModel):
    """Source system configuration."""

    __tablename__ = "source_systems"

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    config_json: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Relationships
    created_by_user = relationship("User", back_populates="source_systems")
    schema_mappings = relationship(
        "SourceSchemaMapping",
        back_populates="source_system",
        order_by="desc(SourceSchemaMapping.version)",
    )
    ingestion_jobs = relationship("IngestionJob", back_populates="source_system")
    raw_records = relationship("RawRecord", back_populates="source_system")
    canonical_records = relationship("CanonicalRecord", back_populates="source_system")

    def __repr__(self) -> str:
        return f"<SourceSystem {self.name}>"

    @property
    def active_schema_mapping(self) -> "SourceSchemaMapping | None":
        """Get the currently active schema mapping."""
        for mapping in self.schema_mappings:
            if mapping.is_active:
                return mapping
        return None


class SourceSchemaMapping(BaseModel):
    """Schema mapping configuration for a source system."""

    __tablename__ = "source_schema_mappings"

    source_system_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_systems.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    mapping_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    source_system = relationship("SourceSystem", back_populates="schema_mappings")

    def __repr__(self) -> str:
        return f"<SourceSchemaMapping source={self.source_system_id} v{self.version}>"

    @property
    def field_mappings(self) -> dict[str, str]:
        """Get field mappings from source columns to canonical fields.

        Example mapping_json structure:
        {
            "fields": {
                "Transaction ID": "external_record_id",
                "Date": "record_date",
                "Amount": "amount",
                "Currency": "currency",
                "Description": "description",
                "Reference": "reference_code",
                "Account": "account_id"
            },
            "date_format": "%Y-%m-%d",
            "decimal_separator": ".",
            "skip_rows": 0
        }
        """
        return self.mapping_json.get("fields", {})

    @property
    def date_format(self) -> str:
        """Get expected date format."""
        return self.mapping_json.get("date_format", "%Y-%m-%d")

    @property
    def skip_rows(self) -> int:
        """Get number of header rows to skip."""
        return self.mapping_json.get("skip_rows", 0)
