from __future__ import annotations

import os

from .base import TTSRequest
from .http_provider import JsonHttpTTSProvider


class OpenAITTSProvider(JsonHttpTTSProvider):
    id = "openai"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.endpoint = os.getenv("OPENAI_TTS_ENDPOINT", "https://api.openai.com/v1/audio/speech")
        self.model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def available(self) -> bool:
        return bool(self.api_key and self.endpoint)

    def build_payload(self, request: TTSRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "voice": request.voice or os.getenv("OPENAI_TTS_VOICE", "alloy"),
            "input": request.text,
            "response_format": "mp3",
            "speed": request.speed,
        }
        return payload
