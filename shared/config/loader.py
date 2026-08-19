from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from shared.utils.protocol import load_data


ROOT = Path(__file__).resolve().parents[2]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_config(override_path: str | Path | None = None) -> dict[str, Any]:
    config = load_data(ROOT / "config" / "default.yaml")
    if override_path:
        config = deep_merge(config, load_data(override_path))
    return config
