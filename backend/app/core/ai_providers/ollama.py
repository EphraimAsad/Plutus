"""Ollama AI provider implementation."""

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ai_providers.base import BaseAIProvider, AIResponse

logger = get_logger(__name__)


class OllamaProvider(BaseAIProvider):
    """Ollama local AI provider.

    Uses Ollama's REST API to generate responses from locally-hosted models.
    This is the default provider for privacy-conscious deployments.
    """

    def __init__(self, model: str | None = None, base_url: str | None = None):
        """Initialize Ollama provider.

        Args:
            model: Model name (e.g., "gemma:7b", "llama3", "mistral")
            base_url: Ollama server URL (defaults to settings)
        """
        super().__init__(model)
        self.base_url = base_url or settings.OLLAMA_BASE_URL

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return settings.OLLAMA_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Generate a response using Ollama.

        Args:
            prompt: The user prompt
            system_prompt: Optional system context
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum response length

        Returns:
            AIResponse with generated content
        """
        model = self.get_model()

        # Build the request payload
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=200.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                return AIResponse(
                    content=data.get("response", ""),
                    model=model,
                    provider=self.provider_name,
                    tokens_used=data.get("eval_count", 0),
                    finish_reason="stop" if data.get("done", False) else "length",
                    metadata={
                        "total_duration": data.get("total_duration"),
                        "load_duration": data.get("load_duration"),
                        "prompt_eval_count": data.get("prompt_eval_count"),
                    },
                )

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            raise ConnectionError(
                f"Cannot connect to Ollama server at {self.base_url}. "
                "Ensure Ollama is running and accessible."
            ) from e
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Ollama API error: {e.response.text}") from e
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check if Ollama is running
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False

                # Check if our model is available
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model = self.get_model()

                # Check for exact match or base model match (e.g., "gemma:7b" matches "gemma")
                if model in models:
                    return True

                # Check if base model name exists
                base_model = model.split(":")[0]
                for available in models:
                    if available.startswith(base_model):
                        return True

                logger.warning(
                    f"Model '{model}' not found in Ollama. "
                    f"Available models: {models}. "
                    f"Run 'ollama pull {model}' to download it."
                )
                return False

        except httpx.ConnectError:
            logger.warning(f"Ollama not available at {self.base_url}")
            return False
        except Exception as e:
            logger.error(f"Error checking Ollama availability: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def pull_model(self, model: str | None = None) -> bool:
        """Pull a model from Ollama registry.

        Args:
            model: Model to pull (defaults to configured model)

        Returns:
            True if successful
        """
        model = model or self.get_model()
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model, "stream": False},
                )
                response.raise_for_status()
                logger.info(f"Successfully pulled model: {model}")
                return True
        except Exception as e:
            logger.error(f"Failed to pull model {model}: {e}")
            return False
