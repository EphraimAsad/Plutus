"""OpenAI GPT AI provider implementation."""

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ai_providers.base import BaseAIProvider, AIResponse

logger = get_logger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT AI provider.

    Uses the OpenAI Chat Completions API for generating responses.
    Requires a valid API key configured in settings.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """Initialize OpenAI provider.

        Args:
            model: Model name (e.g., "gpt-4-turbo-preview", "gpt-3.5-turbo")
            api_key: OpenAI API key (defaults to settings)
        """
        super().__init__(model)
        self.api_key = api_key or settings.OPENAI_API_KEY

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return settings.OPENAI_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Generate a response using GPT.

        Args:
            prompt: The user prompt
            system_prompt: Optional system context
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum response length

        Returns:
            AIResponse with generated content
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        model = self.get_model()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build the request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    OPENAI_API_URL,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Extract content from response
                choices = data.get("choices", [])
                content = ""
                finish_reason = "stop"

                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    finish_reason = choices[0].get("finish_reason", "stop")

                # Calculate tokens
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                return AIResponse(
                    content=content,
                    model=model,
                    provider=self.provider_name,
                    tokens_used=prompt_tokens + completion_tokens,
                    finish_reason=finish_reason,
                    metadata={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "id": data.get("id"),
                        "created": data.get("created"),
                    },
                )

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"OpenAI API error: {e.response.status_code} - {error_body}")

            if e.response.status_code == 401:
                raise ValueError("Invalid OpenAI API key") from e
            elif e.response.status_code == 429:
                raise RuntimeError("OpenAI rate limit exceeded") from e
            elif e.response.status_code == 400:
                raise ValueError(f"Invalid request: {error_body}") from e
            else:
                raise RuntimeError(f"OpenAI API error: {error_body}") from e

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if OpenAI is configured with a valid API key."""
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return False

        # Basic validation of key format
        if not self.api_key.startswith("sk-"):
            logger.warning("OpenAI API key appears invalid (should start with 'sk-')")
            return False

        return True
