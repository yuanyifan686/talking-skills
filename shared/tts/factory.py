from __future__ import annotations

import importlib
import os

from .base import TTSProvider
from .cosyvoice import CosyVoiceTTSProvider
from .fallback import FallbackTTSProvider
from .local import LocalTTSProvider
from .openai import OpenAITTSProvider
from .seed_audio import ByteDanceSeedAudioTTSProvider
from .volcengine import VolcengineTTSProvider


def get_provider(provider: str | None = None) -> TTSProvider:
    requested = (provider or os.getenv("TTS_PROVIDER", "auto")).strip()
    name = requested.lower()
    providers: dict[str, type[TTSProvider]] = {
        "cosyvoice": CosyVoiceTTSProvider,
        "local": LocalTTSProvider,
        "openai": OpenAITTSProvider,
        "seed-audio": ByteDanceSeedAudioTTSProvider,
        "bytedance-seed-audio": ByteDanceSeedAudioTTSProvider,
        "bytedance": ByteDanceSeedAudioTTSProvider,
        "volcengine": VolcengineTTSProvider,
    }
    if name in {"auto", "default"}:
        return FallbackTTSProvider([
            CosyVoiceTTSProvider(),
            ByteDanceSeedAudioTTSProvider(),
            VolcengineTTSProvider(),
        ])
    if name not in providers:
        if ":" in requested:
            module_name, class_name = requested.rsplit(":", 1)
            provider_class = getattr(importlib.import_module(module_name), class_name)
            instance = provider_class()
            if not isinstance(instance, TTSProvider):
                raise TypeError(f"Custom provider {requested} must inherit TTSProvider")
            return instance
        supported = ", ".join(["auto", *sorted(providers)])
        raise ValueError(f"Unknown TTS provider '{requested}'. Use one of {supported} or module.path:ProviderClass")
    return providers[name]()
