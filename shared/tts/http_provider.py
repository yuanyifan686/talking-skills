from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .base import TTSProvider, TTSRequest, TTSResult, TTSUnavailable


class JsonHttpTTSProvider(TTSProvider):
    endpoint: str
    headers: dict[str, str]

    def build_payload(self, request: TTSRequest) -> dict[str, Any]:
        raise NotImplementedError

    def extract_audio(self, body: bytes, content_type: str) -> tuple[bytes, str]:
        if content_type.startswith("audio/"):
            return body, content_type.split(";", 1)[0]
        data = json.loads(body.decode("utf-8"))
        candidate = data.get("audio") or data.get("data") or data.get("audio_data")
        if isinstance(candidate, dict):
            candidate = candidate.get("audio") or candidate.get("data")
        if not isinstance(candidate, str):
            raise TTSUnavailable("TTS response did not contain audio bytes or base64 audio data")
        return base64.b64decode(candidate), "audio/mpeg"

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self._validate(request)
        if not self.available():
            raise TTSUnavailable(f"{self.id} provider is not configured")
        payload = json.dumps(self.build_payload(request), ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(self.endpoint, data=payload, headers=self.headers, method="POST")
        try:
            with urllib.request.urlopen(http_request, timeout=90) as response:
                audio, content_type = self.extract_audio(response.read(), response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise TTSUnavailable(f"{self.id} returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise TTSUnavailable(f"{self.id} endpoint unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TTSUnavailable(f"{self.id} request timed out") from exc
        request.output_path.write_bytes(audio)
        return TTSResult(self.id, request.output_path, content_type, len(audio))
