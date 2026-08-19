from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQUIRED = {"id", "name", "suitable_topics", "platforms", "title_formula", "hook_formula", "structure", "rhythm", "ending_style", "avoid"}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Template management requires PyYAML") from exc
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Template library must be a YAML object")
    return value


def validate_template(template: dict[str, Any]) -> list[str]:
    errors = [f"missing field: {name}" for name in sorted(REQUIRED - set(template))]
    template_id = template.get("id")
    if not isinstance(template_id, str) or not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", template_id):
        errors.append("id must use lowercase snake_case")
    for key in ("suitable_topics", "platforms", "title_formula", "hook_formula", "structure", "ending_style", "avoid"):
        if key in template and (not isinstance(template[key], list) or not template[key]):
            errors.append(f"{key} must be a non-empty list")
    return errors


def add_template(library_path: Path, template: dict[str, Any], confirm: bool) -> dict[str, Any]:
    errors = validate_template(template)
    library = load_yaml(library_path)
    templates = library.setdefault("templates", [])
    if any(item.get("id") == template.get("id") for item in templates if isinstance(item, dict)):
        errors.append(f"duplicate template id: {template.get('id')}")
    if errors:
        return {"status": "error", "errors": errors, "saved": False}
    if not confirm:
        return {"status": "awaiting_user", "errors": [], "saved": False, "template": template}
    templates.append(template)
    import yaml  # type: ignore

    library_path.write_text(yaml.safe_dump(library, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"status": "success", "errors": [], "saved": True, "template_id": template["id"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or explicitly add a viral-script template")
    parser.add_argument("template_json", type=Path)
    parser.add_argument("--library", type=Path, default=Path(__file__).parents[1] / "references" / "copy_templates.yaml")
    parser.add_argument("--confirm", action="store_true", help="Required to mutate the template library")
    args = parser.parse_args()
    template = json.loads(args.template_json.read_text(encoding="utf-8"))
    print(json.dumps(add_template(args.library, template, args.confirm), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
