from __future__ import annotations

import os

from .base import TTSRequest
from .http_provider import JsonHttpTTSProvider


class VolcengineTTSProvider(JsonHttpTTSProvider):
    id = "volcengine"

    def __init__(self) -> None:
        self.endpoint = os.getenv("VOLCENGINE_TTS_ENDPOINT", "")
        self.token = os.getenv("VOLCENGINE_TTS_TOKEN", "")
        self.app_id = os.getenv("VOLCENGINE_TTS_APP_ID", "")
        self.cluster = os.getenv("VOLCENGINE_TTS_CLUSTER", "volcano_tts")
        self.headers = {"Authorization": f"Bearer;{self.token}", "Content-Type": "application/json"}

    def available(self) -> bool:
        return bool(self.endpoint and self.token and self.app_id)

    def build_payload(self, request: TTSRequest) -> dict[str, object]:
        return {
            "app": {"appid": self.app_id, "token": self.token, "cluster": self.cluster},
            "user": {"uid": os.getenv("VOLCENGINE_TTS_USER_ID", "talking-skills")},
            "audio": {
                "voice_type": request.voice or os.getenv("VOLCENGINE_TTS_VOICE", ""),
                "encoding": "mp3",
                "speed_ratio": request.speed,
                "rate": request.sample_rate,
            },
            "request": {"reqid": os.urandom(16).hex(), "text": request.text, "operation": "query"},
        }
