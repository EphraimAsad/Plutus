"""Celery tasks for reconciliation processing."""

from celery import shared_task

from app.core.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3)
def run_reconciliation(self, run_id: str, left_source_id: str, right_source_id: str) -> dict:
    """Run a reconciliation job.

    This task:
    1. Loads canonical records for matching
    2. Runs exact matching
    3. Runs tolerance matching
    4. Runs fuzzy matching
    5. Generates match candidates
    6. Creates exceptions for review items
    7. Updates run statistics

    Args:
        run_id: UUID of the reconciliation run
        left_source_id: UUID of the left source system
        right_source_id: UUID of the right source system
    """
    import uuid

    logger.info(f"Running reconciliation: {run_id}")

    try:
        from app.services.reconciliation_service import ReconciliationService
        from app.core.database import get_worker_session
        import asyncio

        async def do_reconciliation():
            async with get_worker_session() as session:
                service = ReconciliationService(session)
                result = await service.run_reconciliation(
                    run_id=uuid.UUID(run_id),
                    left_source_id=uuid.UUID(left_source_id),
                    right_source_id=uuid.UUID(right_source_id),
                )
                await session.commit()
                return result

        result = asyncio.run(do_reconciliation())
        return {"status": "completed", "run_id": run_id, "result": result}

    except Exception as exc:
        logger.error(f"Reconciliation {run_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def run_duplicate_detection(self, run_id: str, source_id: str) -> dict:
    """Run duplicate detection within a single source.

    Args:
        run_id: UUID of the reconciliation run
        source_id: UUID of the source system to check
    """
    import uuid

    logger.info(f"Running duplicate detection: {run_id} for source {source_id}")

    try:
        from app.services.reconciliation_service import ReconciliationService
        from app.core.database import get_worker_session
        import asyncio

        async def do_detection():
            async with get_worker_session() as session:
                service = ReconciliationService(session)
                result = await service.run_reconciliation_single_source(
                    run_id=uuid.UUID(run_id),
                    source_id=uuid.UUID(source_id),
                )
                await session.commit()
                return result

        result = asyncio.run(do_detection())
        return {"status": "completed", "run_id": run_id, "result": result}

    except Exception as exc:
        logger.error(f"Duplicate detection {run_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))


@shared_task
def run_anomaly_detection(run_id: str | None = None) -> dict:
    """Run anomaly detection on canonical records.

    Can be run as part of reconciliation or standalone.
    """
    logger.info(f"Running anomaly detection for run: {run_id or 'all'}")

    try:
        from app.services.anomaly_service import AnomalyService
        from app.core.database import get_worker_session
        import asyncio

        async def run():
            async with get_worker_session() as session:
                service = AnomalyService(session)
                result = await service.detect_anomalies(run_id)
                await session.commit()
                return result

        result = asyncio.run(run())
        return {"status": "completed", "anomalies_found": result}

    except Exception as exc:
        logger.error(f"Anomaly detection failed: {exc}")
        return {"status": "failed", "error": str(exc)}


@shared_task
def generate_match_candidates(run_id: str, batch_size: int = 1000) -> dict:
    """Generate match candidates for a reconciliation run in batches."""
    logger.info(f"Generating match candidates for run {run_id}")

    try:
        from app.services.matching_service import MatchingService
        from app.core.database import get_worker_session
        import asyncio

        async def run():
            async with get_worker_session() as session:
                service = MatchingService(session)
                result = await service.generate_candidates(run_id, batch_size)
                await session.commit()
                return result

        result = asyncio.run(run())
        return {"status": "completed", "candidates_generated": result}

    except Exception as exc:
        logger.error(f"Match candidate generation failed: {exc}")
        return {"status": "failed", "error": str(exc)}
