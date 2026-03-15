"""AI explanation routes."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.ai_providers.factory import check_ai_status
from app.models.ai_explanation import AIExplanation, AIExplanationStatus, ParentType
from app.models.exception import Exception as ExceptionModel
from app.models.report import Report
from app.models.anomaly import Anomaly
from app.schemas.ai_explanation import AIExplanationResponse, AIExplanationListResponse
from app.api.deps import CurrentUser, AnalystUser

router = APIRouter()


def check_ai_enabled() -> None:
    """Check if AI explanations are enabled."""
    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI explanations are disabled. Set AI_ENABLED=true to enable.",
        )


def _to_response(explanation: AIExplanation) -> AIExplanationResponse:
    """Convert AIExplanation model to response."""
    return AIExplanationResponse(
        id=str(explanation.id),
        parent_type=explanation.parent_type.value,
        parent_id=str(explanation.parent_id),
        status=explanation.status.value,
        output_text=explanation.output_text,
        model_name=explanation.model_name,
        provider=explanation.provider,
        safety_flags=explanation.safety_flags,
        error_message=explanation.error_message,
        input_tokens=explanation.input_tokens,
        output_tokens=explanation.output_tokens,
        created_at=explanation.created_at.isoformat(),
        completed_at=explanation.completed_at.isoformat() if explanation.completed_at else None,
    )


@router.get("/status")
async def get_ai_status(
    current_user: CurrentUser,
) -> dict:
    """Get the current AI system status."""
    return await check_ai_status()


@router.post("/exception/{exception_id}", response_model=AIExplanationResponse, status_code=status.HTTP_201_CREATED)
async def request_exception_explanation(
    exception_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIExplanationResponse:
    """Request an AI explanation for an exception.

    Queues a background task to generate the explanation using the configured AI provider.
    Poll the returned explanation ID to check for completion.
    """
    check_ai_enabled()

    # Check exception exists
    result = await db.execute(select(ExceptionModel).where(ExceptionModel.id == exception_id))
    exception = result.scalar_one_or_none()

    if not exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exception not found",
        )

    # Queue the AI task
    from app.workers.ai_tasks import generate_ai_explanation
    task = generate_ai_explanation.delay(
        explanation_type="exception",
        entity_id=str(exception_id),
        user_id=str(current_user.id),
    )

    # Create pending record
    explanation = AIExplanation(
        parent_type=ParentType.EXCEPTION,
        parent_id=exception_id,
        exception_id=exception_id,
        input_json={"task_id": task.id},
        model_name=_get_model_name(),
        provider=settings.AI_PROVIDER,
        status=AIExplanationStatus.PENDING,
        requested_by=current_user.id,
    )
    db.add(explanation)
    await db.flush()

    return _to_response(explanation)


@router.post("/report/{report_id}", response_model=AIExplanationResponse, status_code=status.HTTP_201_CREATED)
async def request_report_explanation(
    report_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIExplanationResponse:
    """Request an AI explanation/summary for a report.

    Generates a natural language narrative summary of the report data.
    """
    check_ai_enabled()

    # Check report exists and is completed
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.status.value != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report must be completed before requesting AI summary",
        )

    # Queue the AI task
    from app.workers.ai_tasks import generate_ai_explanation
    task = generate_ai_explanation.delay(
        explanation_type="report",
        entity_id=str(report_id),
        user_id=str(current_user.id),
    )

    # Create pending record
    explanation = AIExplanation(
        parent_type=ParentType.REPORT,
        parent_id=report_id,
        report_id=report_id,
        input_json={"task_id": task.id},
        model_name=_get_model_name(),
        provider=settings.AI_PROVIDER,
        status=AIExplanationStatus.PENDING,
        requested_by=current_user.id,
    )
    db.add(explanation)
    await db.flush()

    return _to_response(explanation)


@router.post("/anomaly/{anomaly_id}", response_model=AIExplanationResponse, status_code=status.HTTP_201_CREATED)
async def request_anomaly_explanation(
    anomaly_id: uuid.UUID,
    current_user: AnalystUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIExplanationResponse:
    """Request an AI explanation for an anomaly."""
    check_ai_enabled()

    # Check anomaly exists
    result = await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anomaly not found",
        )

    # Queue the AI task
    from app.workers.ai_tasks import generate_ai_explanation
    task = generate_ai_explanation.delay(
        explanation_type="anomaly",
        entity_id=str(anomaly_id),
        user_id=str(current_user.id),
    )

    # Create pending record
    explanation = AIExplanation(
        parent_type=ParentType.ANOMALY,
        parent_id=anomaly_id,
        input_json={"task_id": task.id},
        model_name=_get_model_name(),
        provider=settings.AI_PROVIDER,
        status=AIExplanationStatus.PENDING,
        requested_by=current_user.id,
    )
    db.add(explanation)
    await db.flush()

    return _to_response(explanation)


@router.get("/{explanation_id}", response_model=AIExplanationResponse)
async def get_explanation(
    explanation_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIExplanationResponse:
    """Get AI explanation by ID."""
    result = await db.execute(select(AIExplanation).where(AIExplanation.id == explanation_id))
    explanation = result.scalar_one_or_none()

    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explanation not found",
        )

    return _to_response(explanation)


@router.get("")
async def list_explanations(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    parent_type: str | None = None,
    parent_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> AIExplanationListResponse:
    """List AI explanations with filters."""
    query = select(AIExplanation).order_by(AIExplanation.created_at.desc())

    if parent_type:
        try:
            type_enum = ParentType(parent_type)
            query = query.where(AIExplanation.parent_type == type_enum)
        except ValueError:
            pass

    if parent_id:
        query = query.where(AIExplanation.parent_id == parent_id)

    if status_filter:
        try:
            status_enum = AIExplanationStatus(status_filter)
            query = query.where(AIExplanation.status == status_enum)
        except ValueError:
            pass

    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    explanations = result.scalars().all()

    return AIExplanationListResponse(
        items=[_to_response(e) for e in explanations],
        total=total,
        limit=limit,
        offset=offset,
    )


def _get_model_name() -> str:
    """Get the configured model name based on provider."""
    if settings.AI_PROVIDER == "ollama":
        return settings.OLLAMA_MODEL
    elif settings.AI_PROVIDER == "anthropic":
        return settings.ANTHROPIC_MODEL
    elif settings.AI_PROVIDER == "openai":
        return settings.OPENAI_MODEL
    return "unknown"
