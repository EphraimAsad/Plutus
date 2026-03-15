"""Source system management routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.source import SourceSystem, SourceSchemaMapping, SourceType
from app.schemas.source import (
    SourceSystemCreate,
    SourceSystemUpdate,
    SourceSystemResponse,
    SchemaMappingCreate,
    SchemaMappingResponse,
)
from app.api.deps import CurrentUser, AdminUser

router = APIRouter()


@router.get("", response_model=list[SourceSystemResponse])
async def list_sources(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = True,
) -> list[SourceSystemResponse]:
    """List all source systems."""
    query = select(SourceSystem).options(selectinload(SourceSystem.schema_mappings))
    if active_only:
        query = query.where(SourceSystem.is_active == True)
    query = query.order_by(SourceSystem.name)

    result = await db.execute(query)
    sources = result.scalars().all()

    return [
        SourceSystemResponse(
            id=str(source.id),
            name=source.name,
            source_type=source.source_type.value,
            description=source.description,
            is_active=source.is_active,
            config_json=source.config_json,
            created_at=source.created_at.isoformat(),
            active_mapping_version=source.active_schema_mapping.version if source.active_schema_mapping else None,
        )
        for source in sources
    ]


@router.post("", response_model=SourceSystemResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: SourceSystemCreate,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SourceSystemResponse:
    """Create a new source system (admin only)."""
    # Check if name already exists
    result = await db.execute(select(SourceSystem).where(SourceSystem.name == request.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source system with this name already exists",
        )

    # Validate source type
    try:
        source_type = SourceType(request.source_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source type. Must be one of: {[t.value for t in SourceType]}",
        )

    source = SourceSystem(
        name=request.name,
        source_type=source_type,
        description=request.description,
        is_active=True,
        config_json=request.config_json or {},
        created_by=current_user.id,
    )
    db.add(source)
    await db.flush()

    return SourceSystemResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type.value,
        description=source.description,
        is_active=source.is_active,
        config_json=source.config_json,
        created_at=source.created_at.isoformat(),
        active_mapping_version=None,
    )


@router.get("/{source_id}", response_model=SourceSystemResponse)
async def get_source(
    source_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SourceSystemResponse:
    """Get source system by ID."""
    result = await db.execute(
        select(SourceSystem)
        .where(SourceSystem.id == source_id)
        .options(selectinload(SourceSystem.schema_mappings))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    return SourceSystemResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type.value,
        description=source.description,
        is_active=source.is_active,
        config_json=source.config_json,
        created_at=source.created_at.isoformat(),
        active_mapping_version=source.active_schema_mapping.version if source.active_schema_mapping else None,
    )


@router.put("/{source_id}", response_model=SourceSystemResponse)
async def update_source(
    source_id: uuid.UUID,
    request: SourceSystemUpdate,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SourceSystemResponse:
    """Update source system (admin only)."""
    result = await db.execute(
        select(SourceSystem)
        .where(SourceSystem.id == source_id)
        .options(selectinload(SourceSystem.schema_mappings))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    if request.name is not None:
        # Check for duplicate name
        existing = await db.execute(
            select(SourceSystem).where(
                SourceSystem.name == request.name, SourceSystem.id != source_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source system with this name already exists",
            )
        source.name = request.name

    if request.description is not None:
        source.description = request.description

    if request.is_active is not None:
        source.is_active = request.is_active

    if request.config_json is not None:
        source.config_json = request.config_json

    await db.flush()

    return SourceSystemResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type.value,
        description=source.description,
        is_active=source.is_active,
        config_json=source.config_json,
        created_at=source.created_at.isoformat(),
        active_mapping_version=source.active_schema_mapping.version if source.active_schema_mapping else None,
    )


@router.post("/{source_id}/schema-mapping", response_model=SchemaMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_schema_mapping(
    source_id: uuid.UUID,
    request: SchemaMappingCreate,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SchemaMappingResponse:
    """Create a new schema mapping for a source system (admin only)."""
    result = await db.execute(
        select(SourceSystem)
        .where(SourceSystem.id == source_id)
        .options(selectinload(SourceSystem.schema_mappings))
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source system not found",
        )

    # Get next version number
    max_version = max((m.version for m in source.schema_mappings), default=0)
    new_version = max_version + 1

    # If activating this mapping, deactivate others
    if request.is_active:
        for mapping in source.schema_mappings:
            mapping.is_active = False

    new_mapping = SourceSchemaMapping(
        source_system_id=source_id,
        version=new_version,
        mapping_json=request.mapping_json,
        is_active=request.is_active,
    )
    db.add(new_mapping)
    await db.flush()

    return SchemaMappingResponse(
        id=str(new_mapping.id),
        source_system_id=str(source_id),
        version=new_mapping.version,
        mapping_json=new_mapping.mapping_json,
        is_active=new_mapping.is_active,
        created_at=new_mapping.created_at.isoformat(),
    )


@router.get("/{source_id}/schema-mappings", response_model=list[SchemaMappingResponse])
async def list_schema_mappings(
    source_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SchemaMappingResponse]:
    """List all schema mappings for a source system."""
    result = await db.execute(
        select(SourceSchemaMapping)
        .where(SourceSchemaMapping.source_system_id == source_id)
        .order_by(SourceSchemaMapping.version.desc())
    )
    mappings = result.scalars().all()

    return [
        SchemaMappingResponse(
            id=str(mapping.id),
            source_system_id=str(source_id),
            version=mapping.version,
            mapping_json=mapping.mapping_json,
            is_active=mapping.is_active,
            created_at=mapping.created_at.isoformat(),
        )
        for mapping in mappings
    ]


@router.post("/{source_id}/schema-mapping/{mapping_id}/activate")
async def activate_schema_mapping(
    source_id: uuid.UUID,
    mapping_id: uuid.UUID,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Activate a specific schema mapping version (admin only)."""
    # Get all mappings for this source
    result = await db.execute(
        select(SourceSchemaMapping).where(SourceSchemaMapping.source_system_id == source_id)
    )
    mappings = result.scalars().all()

    target_mapping = None
    for mapping in mappings:
        if mapping.id == mapping_id:
            target_mapping = mapping
            mapping.is_active = True
        else:
            mapping.is_active = False

    if not target_mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema mapping not found",
        )

    await db.flush()

    return {"message": f"Schema mapping v{target_mapping.version} activated"}
