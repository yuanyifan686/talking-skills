from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .base import TTSRequest, TTSResult, TTSUnavailable
from .http_provider import JsonHttpTTSProvider


class CosyVoiceTTSProvider(JsonHttpTTSProvider):
    """Provider adapter for a local CosyVoice HTTP service or command wrapper.

    CosyVoice itself remains an optional local runtime. This adapter accepts a
    small provider-neutral HTTP contract or a command template so model weights
    do not need to be copied into the Skill package.
    """

    id = "cosyvoice"

    def __init__(self) -> None:
        self.endpoint = os.getenv("COSYVOICE_TTS_ENDPOINT", "").strip()
        self.token = os.getenv("COSYVOICE_TTS_TOKEN", "").strip()
        self.voice = os.getenv("COSYVOICE_TTS_VOICE", "").strip()
        self.command = self._load_command()
        self.headers = {"Content-Type": "application/json"}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    @staticmethod
    def _load_command() -> list[str]:
        raw = os.getenv("COSYVOICE_TTS_COMMAND_JSON", "").strip()
        if not raw:
            return []
        command = json.loads(raw)
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise TTSUnavailable("COSYVOICE_TTS_COMMAND_JSON must be a JSON string array")
        return command

    def available(self) -> bool:
        return bool(self.command and shutil.which(self.command[0])) or bool(self.endpoint)

    def build_payload(self, request: TTSRequest) -> dict[str, object]:
        return {
            "text": request.text,
            "voice": request.voice or self.voice or None,
            "speed": request.speed,
            "sample_rate": request.sample_rate,
            "format": "mp3",
        }

    def _synthesize_command(self, request: TTSRequest) -> TTSResult:
        self._validate(request)
        values = {
            "text": request.text,
            "output": str(request.output_path),
            "voice": request.voice or self.voice,
            "speed": str(request.speed),
            "sample_rate": str(request.sample_rate),
        }
        try:
            command = [part.format_map(values) for part in self.command]
        except KeyError as exc:
            raise TTSUnavailable(f"Unsupported CosyVoice command placeholder: {exc}") from exc
        try:
            subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise TTSUnavailable(f"CosyVoice command failed: {exc}") from exc
        if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
            raise TTSUnavailable("CosyVoice command did not produce a non-empty output file")
        return TTSResult("cosyvoice", request.output_path, "audio/mpeg", request.output_path.stat().st_size)

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if self.command and shutil.which(self.command[0]):
            return self._synthesize_command(request)
        return super().synthesize(request)
