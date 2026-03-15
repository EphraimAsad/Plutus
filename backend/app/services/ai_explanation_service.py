"""AI Explanation service for generating natural language explanations."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ai_providers import get_ai_provider, AIResponse
from app.core.ai_providers.factory import get_available_provider
from app.models.ai_explanation import AIExplanation, AIExplanationStatus, ParentType
from app.models.exception import Exception as ExceptionModel
from app.models.anomaly import Anomaly
from app.models.report import Report, ReportSnapshot

logger = get_logger(__name__)


class AIExplanationService:
    """Service for generating AI-powered explanations.

    This service is READ-ONLY - it analyzes data and generates explanations
    but never modifies business data or takes any actions.
    """

    SYSTEM_PROMPT = """You are a financial operations analyst assistant. Your role is to analyze reconciliation data and provide clear, actionable explanations.

IMPORTANT GUIDELINES:
- You are in READ-ONLY mode - never suggest modifying data directly
- Focus on analysis, root cause identification, and investigation recommendations
- Be concise and professional
- Use financial/accounting terminology appropriately
- Highlight key discrepancies and patterns
- Suggest areas to investigate, not actions to take"""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db

    async def explain_exception(
        self,
        exception_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AIExplanation:
        """Generate an AI explanation for an exception.

        Args:
            exception_id: ID of the exception to explain
            user_id: ID of the user requesting explanation

        Returns:
            AIExplanation record with generated content
        """
        # Get exception
        result = await self.db.execute(
            select(ExceptionModel).where(ExceptionModel.id == exception_id)
        )
        exception = result.scalar_one_or_none()

        if not exception:
            raise ValueError(f"Exception not found: {exception_id}")

        # Get related records from the related_record_ids JSON array
        from app.models.transaction import CanonicalRecord
        left_record = None
        right_record = None
        records = []

        for record_id_str in exception.related_record_ids[:2]:  # Get first 2 records
            try:
                record_id = uuid.UUID(record_id_str) if isinstance(record_id_str, str) else record_id_str
                record = await self.db.get(CanonicalRecord, record_id)
                if record:
                    records.append(self._record_to_dict(record))
            except (ValueError, TypeError):
                continue

        if len(records) >= 1:
            left_record = records[0]
        if len(records) >= 2:
            right_record = records[1]

        # Create input JSON
        input_json = {
            "exception_type": exception.exception_type.value,
            "title": exception.title,
            "severity": exception.severity.value,
            "description": exception.description,
            "left_record": left_record,
            "right_record": right_record,
            "metadata": exception.metadata_json,
        }

        # Get AI provider
        provider = await get_available_provider()
        if not provider:
            raise RuntimeError("No AI provider available")

        # Build prompt
        prompt = provider._build_exception_prompt(
            exception_type=exception.exception_type.value,
            exception_title=exception.title,
            left_record=left_record,
            right_record=right_record,
            context={
                "severity": exception.severity.value,
                "status": exception.status.value,
                "description": exception.description,
            },
        )

        # Generate explanation
        try:
            response = await provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=800,
            )

            # Create explanation record
            explanation = AIExplanation(
                parent_type=ParentType.EXCEPTION,
                parent_id=exception_id,
                exception_id=exception_id,
                input_json=input_json,
                prompt_version="v1",
                model_name=response.model,
                provider=response.provider,
                status=AIExplanationStatus.COMPLETED,
                output_text=response.content,
                safety_flags={"concerns": response.safety_flags} if response.safety_flags else {},
                metadata_json={
                    "finish_reason": response.finish_reason,
                    "prompt_length": len(prompt),
                },
                requested_by=user_id,
                completed_at=datetime.now(timezone.utc),
                input_tokens=response.metadata.get("prompt_eval_count") or response.metadata.get("input_tokens", 0),
                output_tokens=response.tokens_used,
            )

        except Exception as e:
            logger.error(f"AI generation failed for exception {exception_id}: {e}")
            explanation = AIExplanation(
                parent_type=ParentType.EXCEPTION,
                parent_id=exception_id,
                exception_id=exception_id,
                input_json=input_json,
                prompt_version="v1",
                model_name=provider.get_model(),
                provider=provider.provider_name,
                status=AIExplanationStatus.FAILED,
                error_message=str(e)[:2000],
                requested_by=user_id,
                completed_at=datetime.now(timezone.utc),
            )

        self.db.add(explanation)
        await self.db.flush()

        logger.info(f"Generated AI explanation for exception {exception_id}: {explanation.status.value}")
        return explanation

    async def explain_anomaly(
        self,
        anomaly_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AIExplanation:
        """Generate an AI explanation for an anomaly.

        Args:
            anomaly_id: ID of the anomaly to explain
            user_id: ID of the user requesting explanation

        Returns:
            AIExplanation record with generated content
        """
        # Get anomaly with related record
        result = await self.db.execute(
            select(Anomaly)
            .options(joinedload(Anomaly.canonical_record))
            .where(Anomaly.id == anomaly_id)
        )
        anomaly = result.unique().scalar_one_or_none()

        if not anomaly:
            raise ValueError(f"Anomaly not found: {anomaly_id}")

        # Get related record
        record = None
        if anomaly.canonical_record:
            record = self._record_to_dict(anomaly.canonical_record)

        # Create input JSON
        input_json = {
            "anomaly_type": anomaly.anomaly_type.value,
            "severity": anomaly.severity.value,
            "details": anomaly.details_json,
            "record": record,
        }

        # Get AI provider
        provider = await get_available_provider()
        if not provider:
            raise RuntimeError("No AI provider available")

        # Build prompt
        prompt = provider._build_anomaly_prompt(
            anomaly_type=anomaly.anomaly_type.value,
            severity=anomaly.severity.value,
            details=anomaly.details_json,
            record=record,
        )

        # Generate explanation
        try:
            response = await provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=600,
            )

            explanation = AIExplanation(
                parent_type=ParentType.ANOMALY,
                parent_id=anomaly_id,
                input_json=input_json,
                prompt_version="v1",
                model_name=response.model,
                provider=response.provider,
                status=AIExplanationStatus.COMPLETED,
                output_text=response.content,
                safety_flags={"concerns": response.safety_flags} if response.safety_flags else {},
                metadata_json={
                    "anomaly_type": anomaly.anomaly_type.value,
                    "severity": anomaly.severity.value,
                    "finish_reason": response.finish_reason,
                },
                requested_by=user_id,
                completed_at=datetime.now(timezone.utc),
                output_tokens=response.tokens_used,
            )

        except Exception as e:
            logger.error(f"AI generation failed for anomaly {anomaly_id}: {e}")
            explanation = AIExplanation(
                parent_type=ParentType.ANOMALY,
                parent_id=anomaly_id,
                input_json=input_json,
                prompt_version="v1",
                model_name=provider.get_model(),
                provider=provider.provider_name,
                status=AIExplanationStatus.FAILED,
                error_message=str(e)[:2000],
                requested_by=user_id,
                completed_at=datetime.now(timezone.utc),
            )

        self.db.add(explanation)
        await self.db.flush()

        logger.info(f"Generated AI explanation for anomaly {anomaly_id}: {explanation.status.value}")
        return explanation

    async def explain_report(
        self,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AIExplanation:
        """Generate an AI narrative summary for a report.

        Args:
            report_id: ID of the report to summarize
            user_id: ID of the user requesting explanation

        Returns:
            AIExplanation record with generated summary
        """
        # Get report
        result = await self.db.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise ValueError(f"Report not found: {report_id}")

        # Get latest snapshot
        snapshot_result = await self.db.execute(
            select(ReportSnapshot)
            .where(ReportSnapshot.report_id == report_id)
            .order_by(ReportSnapshot.created_at.desc())
            .limit(1)
        )
        snapshot = snapshot_result.scalar_one_or_none()

        if not snapshot:
            raise ValueError(f"Report has no data snapshot: {report_id}")

        # Extract summary data
        snapshot_data = snapshot.snapshot_json
        summary_data = snapshot_data.get("summary", snapshot_data)

        # Create input JSON
        input_json = {
            "report_type": report.report_type.value,
            "title": report.title,
            "summary": summary_data,
        }

        # Get AI provider
        provider = await get_available_provider()
        if not provider:
            raise RuntimeError("No AI provider available")

        # Build prompt
        prompt = provider._build_report_summary_prompt(
            report_type=report.report_type.value,
            summary_data=summary_data,
        )

        # Generate explanation
        try:
            response = await provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.6,
                max_tokens=1000,
            )

            explanation = AIExplanation(
                parent_type=ParentType.REPORT,
                parent_id=report_id,
                report_id=report_id,
                input_json=input_json,
                prompt_version="v1",
                model_name=response.model,
                provider=response.provider,
                status=AIExplanationStatus.COMPLETED,
                output_text=response.content,
                safety_flags={"concerns": response.safety_flags} if response.safety_flags else {},
                metadata_json={
                    "report_type": report.report_type.value,
                    "finish_reason": response.finish_reason,
                },
                requested_by=user_id,
                completed_at=datetime.now(timezone.utc),
                output_tokens=response.tokens_used,
            )

        except Exception as e:
            logger.error(f"AI generation failed for report {report_id}: {e}")
            explanation = AIExplanation(
                parent_type=ParentType.REPORT,
                parent_id=report_id,
                report_id=report_id,
                input_json=input_json,
                prompt_version="v1",
                model_name=provider.get_model(),
                provider=provider.provider_name,
                status=AIExplanationStatus.FAILED,
                error_message=str(e)[:2000],
                requested_by=user_id,
                completed_at=datetime.now(timezone.utc),
            )

        self.db.add(explanation)
        await self.db.flush()

        logger.info(f"Generated AI summary for report {report_id}: {explanation.status.value}")
        return explanation

    async def get_explanation(
        self,
        explanation_id: uuid.UUID,
    ) -> AIExplanation | None:
        """Get an AI explanation by ID."""
        result = await self.db.execute(
            select(AIExplanation).where(AIExplanation.id == explanation_id)
        )
        return result.scalar_one_or_none()

    async def get_explanations_for_entity(
        self,
        entity_id: uuid.UUID,
        parent_type: ParentType | None = None,
    ) -> list[AIExplanation]:
        """Get all explanations for a source entity.

        Args:
            entity_id: ID of the source entity (exception, anomaly, or report)
            parent_type: Optional filter by type

        Returns:
            List of AIExplanation records
        """
        query = select(AIExplanation).where(
            AIExplanation.parent_id == entity_id
        )

        if parent_type:
            query = query.where(AIExplanation.parent_type == parent_type)

        query = query.order_by(AIExplanation.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _record_to_dict(self, record) -> dict[str, Any]:
        """Convert a canonical record to a dictionary for prompts."""
        return {
            "external_id": record.external_record_id,
            "amount": f"{record.amount} {record.currency}" if record.amount else None,
            "date": record.record_date.isoformat() if record.record_date else None,
            "settlement_date": record.settlement_date.isoformat() if record.settlement_date else None,
            "counterparty": record.counterparty,
            "description": record.description,
            "reference": record.reference_code,
        }


async def get_ai_explanation_service(db: AsyncSession) -> AIExplanationService:
    """Factory function to create AI explanation service."""
    return AIExplanationService(db)
