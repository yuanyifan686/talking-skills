from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class TTSUnavailable(RuntimeError):
    """Raised when a configured TTS provider cannot execute."""


@dataclass(frozen=True)
class TTSRequest:
    text: str
    output_path: Path
    voice: str | None = None
    speed: float = 1.0
    sample_rate: int = 24000


@dataclass(frozen=True)
class TTSResult:
    provider: str
    output_path: Path
    content_type: str
    bytes_written: int


class TTSProvider(ABC):
    id: str

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def synthesize(self, request: TTSRequest) -> TTSResult:
        raise NotImplementedError

    def _validate(self, request: TTSRequest) -> None:
        if not request.text.strip():
            raise ValueError("TTS text cannot be empty")
        if request.speed <= 0:
            raise ValueError("TTS speed must be positive")
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
