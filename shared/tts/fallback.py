from __future__ import annotations

from .base import TTSProvider, TTSRequest, TTSResult, TTSUnavailable


class FallbackTTSProvider(TTSProvider):
    """Try providers in order and keep the first successful audio result."""

    id = "auto"

    def __init__(self, providers: list[TTSProvider]) -> None:
        self.providers = providers

    def available(self) -> bool:
        return any(provider.available() for provider in self.providers)

    def synthesize(self, request: TTSRequest) -> TTSResult:
        errors: list[str] = []
        for provider in self.providers:
            try:
                if not provider.available():
                    errors.append(f"{provider.id}: not configured")
                    continue
                return provider.synthesize(request)
            except (TTSUnavailable, OSError, ValueError) as exc:
                errors.append(f"{provider.id}: {exc}")
        detail = "; ".join(errors) or "no providers configured"
        raise TTSUnavailable(f"No TTS provider succeeded: {detail}")
