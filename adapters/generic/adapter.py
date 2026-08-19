from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.capabilities import choose_mode, detect
from shared.utils.protocol import load_data, print_json
from shared.utils.validation import validate


def discover() -> list[dict[str, Any]]:
    results = []
    schema = ROOT / "schemas" / "skill.schema.json"
    for manifest_path in sorted((ROOT / "skills").glob("*/manifest.yaml")):
        manifest = load_data(manifest_path)
        results.append({
            "id": manifest.get("id"),
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "description": manifest.get("description"),
            "actions": manifest.get("actions", []),
            "valid": not validate(manifest, schema),
            "manifest": str(manifest_path),
        })
    return results


def required_capabilities(manifest: dict[str, Any], action: str | None = None) -> list[str]:
    requirements = (manifest.get("requirements_by_action") or {}).get(action) if action else None
    requirements = requirements or manifest.get("requirements") or {}
    required = list(requirements.get("runtime") or []) + list(requirements.get("binaries") or [])
    permissions = requirements.get("permissions") or {}
    required.extend(name for name, value in permissions.items() if value is True or value == "required")
    services = requirements.get("external_services") or {}
    required.extend(name for name, value in services.items() if value == "required")
    return list(dict.fromkeys(required))


def prepare(invocation: dict[str, Any]) -> dict[str, Any]:
    invocation_errors = validate(invocation, ROOT / "schemas" / "invocation.schema.json")
    skill_id = invocation.get("skill", "")
    skill_dir = ROOT / "skills" / str(skill_id)
    manifest_path = skill_dir / "manifest.yaml"
    instruction_path = skill_dir / "SKILL.md"
    if invocation_errors:
        return {"status": "error", "errors": invocation_errors}
    if not manifest_path.is_file() or not instruction_path.is_file():
        return {"status": "error", "errors": [f"Unknown skill: {skill_id}"]}
    manifest = load_data(manifest_path)
    manifest_errors = validate(manifest, ROOT / "schemas" / "skill.schema.json")
    if manifest_errors:
        return {"status": "error", "errors": manifest_errors}
    action = str(invocation.get("action") or "")
    if action not in manifest.get("actions", []):
        return {"status": "error", "errors": [f"Unknown action '{action}' for skill '{skill_id}'"]}
    capabilities = {**detect(invocation.get("input", {}).get("output_dir") or ROOT / "output"), **(invocation.get("capabilities") or {})}
    required = required_capabilities(manifest, str(invocation.get("action") or ""))
    requested_mode = invocation.get("mode", "auto")
    mode = choose_mode(required, capabilities) if requested_mode == "auto" else requested_mode
    return {
        "status": "ready",
        "protocol_version": manifest.get("protocol_version", "1.0.0"),
        "execution_mode": mode,
        "required_capabilities": required,
        "capabilities": capabilities,
        "skill": {"id": skill_id, "manifest": str(manifest_path), "instructions": str(instruction_path)},
        "invocation": invocation,
        "adapter_contract": "Load the resolved instructions, execute only the requested action, and return the universal response envelope.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic Talking Skills adapter")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("discover")
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("invocation", type=Path)
    validate_parser = subparsers.add_parser("validate-response")
    validate_parser.add_argument("response", type=Path)
    args = parser.parse_args()
    if args.operation == "discover":
        print_json({"skills": discover()})
        return 0
    if args.operation == "prepare":
        result = prepare(load_data(args.invocation))
        print_json(result)
        return 0 if result.get("status") == "ready" else 2
    result = load_data(args.response)
    errors = validate(result, ROOT / "schemas" / "response.schema.json")
    print_json({"valid": not errors, "errors": errors})
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
