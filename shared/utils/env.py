from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or value.startswith("#"):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_project_env() -> list[Path]:
    """Load local .env files without overriding explicitly exported values."""

    skill_root = Path(__file__).resolve().parents[2]
    project_root = skill_root.parent
    paths = [
        project_root / ".env",
        skill_root / ".env",
        project_root / ".env.local",
        skill_root / ".env.local",
    ]
    values: dict[str, str] = {}
    loaded: list[Path] = []
    for path in paths:
        file_values = _parse_env_file(path)
        if file_values:
            loaded.append(path)
            values.update(file_values)
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return loaded
