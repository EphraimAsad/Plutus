"""AI provider factory."""

from typing import Literal

from app.core.config import settings
from app.core.logging import get_logger
from app.core.ai_providers.base import BaseAIProvider
from app.core.ai_providers.ollama import OllamaProvider
from app.core.ai_providers.anthropic import AnthropicProvider
from app.core.ai_providers.openai import OpenAIProvider

logger = get_logger(__name__)

ProviderType = Literal["ollama", "anthropic", "openai"]


def get_ai_provider(
    provider: ProviderType | None = None,
    model: str | None = None,
) -> BaseAIProvider:
    """Get an AI provider instance.

    Args:
        provider: Provider name (defaults to settings.AI_PROVIDER)
        model: Model name override (defaults to provider's default)

    Returns:
        Configured AI provider instance

    Raises:
        ValueError: If provider is unknown or AI is disabled
    """
    if not settings.AI_ENABLED:
        raise ValueError("AI features are disabled. Set AI_ENABLED=true to enable.")

    provider_name = provider or settings.AI_PROVIDER

    providers = {
        "ollama": OllamaProvider,
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
    }

    provider_class = providers.get(provider_name)
    if not provider_class:
        raise ValueError(
            f"Unknown AI provider: {provider_name}. "
            f"Available providers: {list(providers.keys())}"
        )

    logger.debug(f"Creating AI provider: {provider_name} with model: {model or 'default'}")
    return provider_class(model=model)


async def get_available_provider() -> BaseAIProvider | None:
    """Get the first available AI provider.

    Checks providers in order of preference:
    1. Configured provider (settings.AI_PROVIDER)
    2. Ollama (local)
    3. Anthropic (if API key set)
    4. OpenAI (if API key set)

    Returns:
        Available provider or None if none available
    """
    if not settings.AI_ENABLED:
        return None

    # Try configured provider first
    try:
        provider = get_ai_provider()
        if await provider.is_available():
            return provider
    except Exception as e:
        logger.warning(f"Configured provider not available: {e}")

    # Fall back to trying each provider
    for provider_name in ["ollama", "anthropic", "openai"]:
        if provider_name == settings.AI_PROVIDER:
            continue  # Already tried

        try:
            provider = get_ai_provider(provider=provider_name)
            if await provider.is_available():
                logger.info(f"Using fallback AI provider: {provider_name}")
                return provider
        except Exception:
            continue

    logger.warning("No AI providers available")
    return None


async def check_ai_status() -> dict:
    """Check the status of all AI providers.

    Returns:
        Dictionary with status of each provider
    """
    status = {
        "enabled": settings.AI_ENABLED,
        "configured_provider": settings.AI_PROVIDER,
        "providers": {},
    }

    if not settings.AI_ENABLED:
        return status

    for provider_name in ["ollama", "anthropic", "openai"]:
        try:
            provider = get_ai_provider(provider=provider_name)
            is_available = await provider.is_available()
            status["providers"][provider_name] = {
                "available": is_available,
                "model": provider.get_model(),
            }
        except Exception as e:
            status["providers"][provider_name] = {
                "available": False,
                "error": str(e),
            }

    return status
