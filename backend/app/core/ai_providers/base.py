"""Base AI provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIResponse:
    """Response from an AI provider."""

    content: str
    model: str
    provider: str
    tokens_used: int = 0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)
    safety_flags: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """Check if the response has no safety flags."""
        return len(self.safety_flags) == 0


class BaseAIProvider(ABC):
    """Abstract base class for AI providers.

    All AI providers must implement this interface to ensure consistent
    behavior across different backends (Ollama, Anthropic, OpenAI).
    """

    def __init__(self, model: str | None = None):
        """Initialize provider with optional model override."""
        self.model = model

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Generate a response from the AI model.

        Args:
            prompt: The user prompt/question
            system_prompt: Optional system prompt for context
            temperature: Creativity setting (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            AIResponse with the generated content
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        pass

    def get_model(self) -> str:
        """Get the model to use (custom or default)."""
        return self.model or self.default_model

    def _build_exception_prompt(
        self,
        exception_type: str,
        exception_title: str,
        left_record: dict[str, Any] | None,
        right_record: dict[str, Any] | None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Build a prompt for explaining an exception.

        This is a read-only analysis task - the AI should never suggest
        modifying data or taking actions that change business state.
        """
        prompt_parts = [
            "You are a financial reconciliation expert. Analyze the following exception and provide a clear, concise explanation.",
            "",
            f"Exception Type: {exception_type}",
            f"Title: {exception_title}",
            "",
        ]

        if left_record:
            prompt_parts.append("Left Record (Source A):")
            for key, value in left_record.items():
                prompt_parts.append(f"  - {key}: {value}")
            prompt_parts.append("")

        if right_record:
            prompt_parts.append("Right Record (Source B):")
            for key, value in right_record.items():
                prompt_parts.append(f"  - {key}: {value}")
            prompt_parts.append("")

        if context:
            prompt_parts.append("Additional Context:")
            for key, value in context.items():
                prompt_parts.append(f"  - {key}: {value}")
            prompt_parts.append("")

        prompt_parts.extend([
            "Please provide:",
            "1. A brief explanation of why this exception was raised",
            "2. The likely root cause of the discrepancy",
            "3. Suggested areas to investigate (do NOT suggest modifying any data)",
            "",
            "Keep your response concise and factual. Focus on analysis only.",
        ])

        return "\n".join(prompt_parts)

    def _build_anomaly_prompt(
        self,
        anomaly_type: str,
        severity: str,
        details: dict[str, Any],
        record: dict[str, Any] | None = None,
    ) -> str:
        """Build a prompt for explaining an anomaly."""
        prompt_parts = [
            "You are a financial operations analyst. Analyze the following detected anomaly and explain its significance.",
            "",
            f"Anomaly Type: {anomaly_type}",
            f"Severity: {severity}",
            "",
            "Detection Details:",
        ]

        for key, value in details.items():
            prompt_parts.append(f"  - {key}: {value}")

        if record:
            prompt_parts.append("")
            prompt_parts.append("Related Record:")
            for key, value in record.items():
                prompt_parts.append(f"  - {key}: {value}")

        prompt_parts.extend([
            "",
            "Please provide:",
            "1. An explanation of what this anomaly indicates",
            "2. Potential business implications",
            "3. Recommended investigation steps (read-only analysis)",
            "",
            "Be concise and focus on actionable insights.",
        ])

        return "\n".join(prompt_parts)

    def _build_report_summary_prompt(
        self,
        report_type: str,
        summary_data: dict[str, Any],
    ) -> str:
        """Build a prompt for generating a report narrative summary."""
        prompt_parts = [
            "You are an operations reporting specialist. Generate a brief executive summary for the following report data.",
            "",
            f"Report Type: {report_type}",
            "",
            "Key Metrics:",
        ]

        for key, value in summary_data.items():
            if isinstance(value, dict):
                prompt_parts.append(f"  {key}:")
                for k, v in value.items():
                    prompt_parts.append(f"    - {k}: {v}")
            else:
                prompt_parts.append(f"  - {key}: {value}")

        prompt_parts.extend([
            "",
            "Generate a 2-3 paragraph executive summary that:",
            "1. Highlights key findings",
            "2. Notes any concerning trends or outliers",
            "3. Provides context for the metrics",
            "",
            "Write in a professional, concise style suitable for management review.",
        ])

        return "\n".join(prompt_parts)
