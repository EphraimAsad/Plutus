"""Anthropic Claude AI provider implementation."""

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ai_providers.base import BaseAIProvider, AIResponse

logger = get_logger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude AI provider.

    Uses the Anthropic Messages API for generating responses.
    Requires a valid API key configured in settings.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """Initialize Anthropic provider.

        Args:
            model: Model name (e.g., "claude-3-sonnet-20240229")
            api_key: Anthropic API key (defaults to settings)
        """
        super().__init__(model)
        self.api_key = api_key or settings.ANTHROPIC_API_KEY

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return settings.ANTHROPIC_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Generate a response using Claude.

        Args:
            prompt: The user prompt
            system_prompt: Optional system context
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum response length

        Returns:
            AIResponse with generated content
        """
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")

        model = self.get_model()

        # Build the request payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        if system_prompt:
            payload["system"] = system_prompt

        if temperature != 0.7:  # Only include if non-default
            payload["temperature"] = temperature

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Extract content from response
                content = ""
                if "content" in data and data["content"]:
                    content = data["content"][0].get("text", "")

                # Calculate tokens
                input_tokens = data.get("usage", {}).get("input_tokens", 0)
                output_tokens = data.get("usage", {}).get("output_tokens", 0)

                return AIResponse(
                    content=content,
                    model=model,
                    provider=self.provider_name,
                    tokens_used=input_tokens + output_tokens,
                    finish_reason=data.get("stop_reason", "end_turn"),
                    metadata={
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "id": data.get("id"),
                    },
                )

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"Anthropic API error: {e.response.status_code} - {error_body}")

            if e.response.status_code == 401:
                raise ValueError("Invalid Anthropic API key") from e
            elif e.response.status_code == 429:
                raise RuntimeError("Anthropic rate limit exceeded") from e
            else:
                raise RuntimeError(f"Anthropic API error: {error_body}") from e

        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Anthropic is configured with a valid API key."""
        if not self.api_key:
            logger.warning("Anthropic API key not configured")
            return False

        # We don't make an API call to validate - just check the key format
        if not self.api_key.startswith("sk-ant-"):
            logger.warning("Anthropic API key appears invalid (should start with 'sk-ant-')")
            return False

        return True
