from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def find_cjk_font(explicit: str | Path | None = None) -> Path | None:
    candidates = [
        Path(explicit) if explicit else None,
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc",
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def escape_filter_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def escape_filter_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def probe(path: str | Path) -> dict[str, Any]:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is not available")
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def has_audio(path: str | Path) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe(path).get("streams", []))


def duration(path: str | Path) -> float:
    value = probe(path).get("format", {}).get("duration", 0)
    return float(value or 0)
