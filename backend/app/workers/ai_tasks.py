"""Celery tasks for AI explanation generation."""

import uuid
from typing import Literal

from celery import shared_task

from app.core.logging import get_logger

logger = get_logger(__name__)

ExplanationType = Literal["exception", "anomaly", "report"]


@shared_task(bind=True, max_retries=2)
def generate_ai_explanation(
    self,
    explanation_type: ExplanationType,
    entity_id: str,
    user_id: str,
) -> dict:
    """Generate an AI explanation for an entity.

    This task:
    1. Gets the appropriate AI provider
    2. Loads the entity data
    3. Generates a prompt and sends to AI
    4. Saves the explanation result
    """
    logger.info(f"Generating AI explanation for {explanation_type}: {entity_id}")

    try:
        from app.services.ai_explanation_service import AIExplanationService
        from app.core.database import get_worker_session
        import asyncio

        async def run():
            async with get_worker_session() as session:
                service = AIExplanationService(session)

                entity_uuid = uuid.UUID(entity_id)
                user_uuid = uuid.UUID(user_id)

                if explanation_type == "exception":
                    result = await service.explain_exception(entity_uuid, user_uuid)
                elif explanation_type == "anomaly":
                    result = await service.explain_anomaly(entity_uuid, user_uuid)
                elif explanation_type == "report":
                    result = await service.explain_report(entity_uuid, user_uuid)
                else:
                    raise ValueError(f"Unknown explanation type: {explanation_type}")

                await session.commit()
                return {
                    "id": str(result.id),
                    "status": result.status.value,
                    "output_text": result.output_text,
                    "model_name": result.model_name,
                    "provider": result.provider,
                }

        result = asyncio.run(run())
        logger.info(f"AI explanation completed: {result['status']}")
        return {"status": "completed", **result}

    except Exception as exc:
        logger.error(f"AI explanation for {explanation_type}:{entity_id} failed: {exc}")

        # Try to mark as failed in DB
        try:
            from app.core.database import get_worker_session
            from app.models.ai_explanation import AIExplanation, AIExplanationStatus, ParentType
            from sqlalchemy import select, and_
            from datetime import datetime, timezone
            import asyncio

            async def mark_failed():
                async with get_worker_session() as session:
                    # Find the pending explanation for this entity
                    type_map = {
                        "exception": ParentType.EXCEPTION,
                        "anomaly": ParentType.ANOMALY,
                        "report": ParentType.REPORT,
                    }
                    result = await session.execute(
                        select(AIExplanation).where(
                            and_(
                                AIExplanation.parent_type == type_map[explanation_type],
                                AIExplanation.parent_id == uuid.UUID(entity_id),
                                AIExplanation.status == AIExplanationStatus.PENDING,
                            )
                        ).order_by(AIExplanation.created_at.desc()).limit(1)
                    )
                    explanation = result.scalar_one_or_none()
                    if explanation:
                        explanation.status = AIExplanationStatus.FAILED
                        explanation.error_message = str(exc)[:2000]
                        explanation.completed_at = datetime.now(timezone.utc)
                        await session.commit()

            asyncio.run(mark_failed())
        except Exception as inner_exc:
            logger.error(f"Failed to mark explanation as failed: {inner_exc}")

        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@shared_task
def batch_generate_explanations(
    explanation_type: ExplanationType,
    entity_ids: list[str],
    user_id: str,
) -> dict:
    """Generate multiple AI explanations in batch.

    Queues individual tasks for each entity.
    """
    logger.info(f"Batch generating {len(entity_ids)} {explanation_type} explanations")

    results = []
    for entity_id in entity_ids:
        try:
            task = generate_ai_explanation.delay(
                explanation_type=explanation_type,
                entity_id=entity_id,
                user_id=user_id,
            )
            results.append({"entity_id": entity_id, "task_id": task.id})
        except Exception as exc:
            results.append({"entity_id": entity_id, "error": str(exc)})

    return {"status": "submitted", "count": len(entity_ids), "results": results}
