from typing import Literal

import structlog

from src.core.config import settings
from src.core.exceptions import LLMProviderUnavailableError
from src.services.llm.anthropic import AnthropicProvider
from src.services.llm.base import LLMProvider, ReviewRequest, ReviewResponse
from src.services.llm.ollama import OllamaProvider

logger = structlog.get_logger()

ProviderName = Literal["anthropic", "openai", "ollama"]


class LLMRouter:
    """Routes review requests to appropriate LLM provider."""

    def __init__(
        self,
        default_provider: ProviderName | None = None,
        fallback_enabled: bool = True,
    ) -> None:
        self.default_provider = default_provider or settings.default_llm_provider
        self.fallback_enabled = fallback_enabled
        self._providers: dict[str, LLMProvider] = {}

    def _get_provider(self, name: ProviderName) -> LLMProvider:
        """Get or create a provider instance."""
        if name not in self._providers:
            if name == "anthropic":
                self._providers[name] = AnthropicProvider()
            elif name == "ollama":
                self._providers[name] = OllamaProvider()
            elif name == "openai":
                # TODO: Implement OpenAI provider
                raise LLMProviderUnavailableError("OpenAI provider not implemented yet")
            else:
                raise LLMProviderUnavailableError(f"Unknown provider: {name}")
        return self._providers[name]

    def get_available_providers(self) -> list[str]:
        """Get list of available (configured) providers."""
        available = []
        for name in ("anthropic", "ollama"):
            try:
                provider = self._get_provider(name)  # type: ignore[arg-type]
                if provider.is_available():
                    available.append(name)
            except LLMProviderUnavailableError:
                continue
        return available

    async def review_code(
        self,
        request: ReviewRequest,
        provider: ProviderName | None = None,
    ) -> ReviewResponse:
        """
        Review code using the specified or default provider.

        Args:
            request: The review request.
            provider: Optional specific provider to use.

        Returns:
            ReviewResponse from the LLM.

        Raises:
            LLMProviderUnavailableError: If no providers are available.
        """
        provider_name = provider or self.default_provider

        # Try primary provider
        try:
            llm = self._get_provider(provider_name)  # type: ignore[arg-type]
            if llm.is_available():
                logger.info(
                    "Using LLM provider",
                    provider=provider_name,
                    model=llm.model,
                )
                return await llm.review_code(request)
        except Exception as e:
            logger.warning(
                "Primary provider failed",
                provider=provider_name,
                error=str(e),
            )
            if not self.fallback_enabled:
                raise

        # Try fallback providers
        if self.fallback_enabled:
            fallback_order = ["anthropic", "ollama"]
            for fallback_name in fallback_order:
                if fallback_name == provider_name:
                    continue

                try:
                    llm = self._get_provider(fallback_name)  # type: ignore[arg-type]
                    if llm.is_available():
                        logger.info(
                            "Using fallback provider",
                            provider=fallback_name,
                            model=llm.model,
                        )
                        return await llm.review_code(request)
                except Exception as e:
                    logger.warning(
                        "Fallback provider failed",
                        provider=fallback_name,
                        error=str(e),
                    )
                    continue

        raise LLMProviderUnavailableError("No LLM providers available")
