from __future__ import annotations

import base64
import binascii
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import TTSRequest, TTSUnavailable
from .http_provider import JsonHttpTTSProvider


class ByteDanceSeedAudioTTSProvider(JsonHttpTTSProvider):
    """Adapter for the ByteDance Seed Audio 1.0 HTTP API.

    The API accepts a single ``text_prompt``. That prompt may be plain
    narration or a richer instruction containing speaker, music, and sound
    effect directions. The provider deliberately passes the request text
    through unchanged so callers can use either form.
    """

    id = "seed-audio"

    def __init__(self) -> None:
        self.endpoint = os.getenv(
            "BYTEDANCE_SEED_AUDIO_ENDPOINT",
            "https://openspeech.bytedance.com/api/v3/tts/create",
        ).strip()
        self.api_key = os.getenv("BYTEDANCE_SEED_AUDIO_API_KEY", "").strip()
        self.model = os.getenv("BYTEDANCE_SEED_AUDIO_MODEL", "seed-audio-1.0").strip()
        self.watermark = self._load_watermark()
        self.headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
        }

    @staticmethod
    def _load_watermark() -> dict[str, Any]:
        raw = os.getenv("BYTEDANCE_SEED_AUDIO_WATERMARK_JSON", "{}").strip() or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TTSUnavailable("BYTEDANCE_SEED_AUDIO_WATERMARK_JSON must be valid JSON") from exc
        if not isinstance(value, dict):
            raise TTSUnavailable("BYTEDANCE_SEED_AUDIO_WATERMARK_JSON must be a JSON object")
        return value

    def available(self) -> bool:
        return bool(self.endpoint and self.api_key and self.model)

    def build_payload(self, request: TTSRequest) -> dict[str, object]:
        # Seed Audio uses 0 as the neutral speech-rate value. Convert the
        # provider-neutral speed multiplier to a percentage delta when used.
        speech_rate = round((request.speed - 1.0) * 100)
        return {
            "model": self.model,
            "text_prompt": request.text,
            "audio_config": {
                "format": "mp3",
                "sample_rate": request.sample_rate or 48000,
                "pitch_rate": 0,
                "speech_rate": speech_rate,
                "loudness_rate": 0,
            },
            "watermark": self.watermark,
        }

    @staticmethod
    def _candidate(data: Any) -> str | None:
        if isinstance(data, str):
            return data
        if not isinstance(data, dict):
            return None
        for key in ("audio", "audio_base64", "audio_data", "audio_url", "url"):
            value = data.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = ByteDanceSeedAudioTTSProvider._candidate(value)
                if nested:
                    return nested
        for key in ("data", "result", "response"):
            nested = ByteDanceSeedAudioTTSProvider._candidate(data.get(key))
            if nested:
                return nested
        return None

    @staticmethod
    def _decode_audio(candidate: str) -> tuple[bytes, str] | None:
        value = candidate.strip()
        if value.startswith("data:") and "," in value:
            header, value = value.split(",", 1)
            content_type = header[5:].split(";", 1)[0] or "audio/mpeg"
        else:
            content_type = "audio/mpeg"
        try:
            return base64.b64decode(value, validate=True), content_type
        except (binascii.Error, ValueError):
            return None

    @classmethod
    def _extract_json_audio(cls, body: bytes) -> tuple[bytes, str]:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TTSUnavailable("Seed Audio returned neither audio bytes nor valid JSON") from exc

        candidate = cls._candidate(data)
        if candidate:
            decoded = cls._decode_audio(candidate)
            if decoded:
                return decoded
            if candidate.startswith(("http://", "https://")):
                try:
                    with urllib.request.urlopen(candidate, timeout=90) as response:
                        return response.read(), response.headers.get("Content-Type", "audio/mpeg").split(";", 1)[0]
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                    raise TTSUnavailable(f"Seed Audio audio URL unavailable: {exc}") from exc

        task_id = None
        if isinstance(data, dict):
            task_id = data.get("task_id") or data.get("id")
        if task_id:
            raise TTSUnavailable(
                f"Seed Audio returned async task {task_id}; no polling endpoint is configured for this provider"
            )
        raise TTSUnavailable("Seed Audio response did not contain audio bytes or base64 audio data")

    def extract_audio(self, body: bytes, content_type: str) -> tuple[bytes, str]:
        if content_type.startswith("audio/"):
            return body, content_type.split(";", 1)[0]
        if not content_type and (body.startswith(b"ID3") or body.startswith(b"\xff\xfb")):
            return body, "audio/mpeg"
        return self._extract_json_audio(body)
