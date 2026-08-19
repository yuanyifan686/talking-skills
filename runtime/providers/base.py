from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Return plain model text for a provider-neutral prompt."""
