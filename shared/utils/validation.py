from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def validate(instance: dict[str, Any], schema_path: str | Path) -> list[str]:
    """Validate a protocol object while retaining a lightweight fallback."""

    source = Path(schema_path)
    schema = json.loads(source.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
        from referencing import Registry, Resource  # type: ignore
    except ImportError:
        missing = [name for name in schema.get("required", []) if name not in instance]
        return [f"missing required key: {name}" for name in missing]

    resources = []
    for candidate in (ROOT / "schemas").glob("*.json"):
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
        resources.append((loaded.get("$id", candidate.as_uri()), Resource.from_contents(loaded)))
    validator = jsonschema.Draft202012Validator(
        schema,
        registry=Registry().with_resources(resources),
    )
    return [
        f"{'/'.join(map(str, error.path)) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]
