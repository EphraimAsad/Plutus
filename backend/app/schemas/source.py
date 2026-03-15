"""Source system schemas."""

from typing import Any

from pydantic import BaseModel, Field


class SourceSystemCreate(BaseModel):
    """Schema for creating a source system."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field(..., description="csv, xlsx, api, or database")
    description: str | None = None
    config_json: dict[str, Any] | None = None


class SourceSystemUpdate(BaseModel):
    """Schema for updating a source system."""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    config_json: dict[str, Any] | None = None


class SourceSystemResponse(BaseModel):
    """Source system response schema."""

    id: str
    name: str
    source_type: str
    description: str | None
    is_active: bool
    config_json: dict[str, Any]
    created_at: str
    active_mapping_version: int | None

    class Config:
        from_attributes = True


class SchemaMappingCreate(BaseModel):
    """Schema for creating a schema mapping."""

    mapping_json: dict[str, Any] = Field(
        ...,
        description="Field mapping configuration",
        examples=[{
            "fields": {
                "Transaction ID": "external_record_id",
                "Date": "record_date",
                "Amount": "amount",
                "Currency": "currency",
                "Description": "description",
                "Reference": "reference_code",
            },
            "date_format": "%Y-%m-%d",
            "decimal_separator": ".",
            "skip_rows": 0,
        }],
    )
    is_active: bool = False


class SchemaMappingResponse(BaseModel):
    """Schema mapping response schema."""

    id: str
    source_system_id: str
    version: int
    mapping_json: dict[str, Any]
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True
