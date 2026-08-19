from __future__ import annotations

import json
import os
import shutil
import subprocess

from .base import TTSProvider, TTSRequest, TTSResult, TTSUnavailable


class LocalTTSProvider(TTSProvider):
    id = "local"

    def _command(self) -> list[str]:
        raw = os.getenv("TALKING_SKILLS_LOCAL_TTS_COMMAND_JSON", "")
        if not raw:
            return []
        command = json.loads(raw)
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise TTSUnavailable("TALKING_SKILLS_LOCAL_TTS_COMMAND_JSON must be a JSON string array")
        return command

    def available(self) -> bool:
        command = self._command()
        return bool(command and shutil.which(command[0]))

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self._validate(request)
        command = self._command()
        if not command or not shutil.which(command[0]):
            raise TTSUnavailable("Local TTS command is not configured or executable")
        values = {
            "text": request.text,
            "output": str(request.output_path),
            "voice": request.voice or "",
            "speed": str(request.speed),
            "sample_rate": str(request.sample_rate),
        }
        subprocess.run([part.format_map(values) for part in command], check=True)
        if not request.output_path.is_file() or request.output_path.stat().st_size == 0:
            raise TTSUnavailable("Local TTS command did not produce a non-empty output file")
        return TTSResult(self.id, request.output_path, "audio/mpeg", request.output_path.stat().st_size)
