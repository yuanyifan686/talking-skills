from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


SECRET_GROUPS = {
    "tts_seed_audio": ("BYTEDANCE_SEED_AUDIO_API_KEY",),
    "tts_volcengine": ("VOLCENGINE_TTS_TOKEN", "VOLCENGINE_TTS_APP_ID"),
    "tts_openai": ("OPENAI_API_KEY",),
    "tts_azure": ("AZURE_SPEECH_KEY",),
    "tts_elevenlabs": ("ELEVENLABS_API_KEY",),
    "tts_aliyun": ("ALIYUN_ACCESS_KEY_ID", "ALIYUN_ACCESS_KEY_SECRET"),
    "tts_tencent": ("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY"),
}


def detect(output_dir: str | Path | None = None) -> dict[str, Any]:
    target = Path(output_dir or ".").resolve()
    secrets = {name: all(bool(os.getenv(key)) for key in keys) for name, keys in SECRET_GROUPS.items()}
    filesystem = target.exists() and os.access(target, os.R_OK | os.W_OK)
    ffmpeg = shutil.which("ffmpeg") is not None
    ffprobe = shutil.which("ffprobe") is not None
    return {
        "llm": os.getenv("TALKING_SKILLS_LLM", "unknown") != "disabled",
        "filesystem": filesystem,
        "python": True,
        "shell": True,
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
        "network": os.getenv("TALKING_SKILLS_NETWORK", "optional").lower() != "disabled",
        "secrets": any(secrets.values()),
        "secret_groups": secrets,
        "image_processing": ffmpeg,
        "video_processing": ffmpeg and ffprobe,
        "python_version": ".".join(map(str, sys.version_info[:3])),
    }


def choose_mode(required: list[str], capabilities: dict[str, Any]) -> str:
    if all(bool(capabilities.get(name)) for name in required):
        return "full"
    execution_capabilities = ("filesystem", "python", "shell", "ffmpeg", "ffprobe", "network", "image_processing", "video_processing")
    if any(bool(capabilities.get(name)) for name in execution_capabilities):
        return "partial"
    return "text_only"


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect agent-neutral Talking Skills capabilities")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--require", action="append", default=[])
    args = parser.parse_args()
    report = detect(args.output_dir)
    report["execution_mode"] = choose_mode(args.require, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
