from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.utils.protocol import load_data
from shared.utils.validation import validate


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    directory: Path
    manifest: dict[str, Any]
    instructions: str
    references: dict[str, Any]


class SkillRegistry:
    """Discover and validate Skills without depending on an Agent adapter."""

    def __init__(self, root: str | Path = ROOT) -> None:
        self.root = Path(root).resolve()
        self.skills_dir = self.root / "skills"
        self.schemas_dir = self.root / "schemas"

    def discover(self) -> list[dict[str, Any]]:
        skills = []
        for path in sorted(self.skills_dir.glob("*/manifest.yaml")):
            manifest = load_data(path)
            errors = validate(manifest, self.schemas_dir / "skill.schema.json")
            skills.append(
                {
                    "id": manifest.get("id"),
                    "name": manifest.get("name"),
                    "version": manifest.get("version"),
                    "description": manifest.get("description"),
                    "actions": manifest.get("actions", []),
                    "valid": not errors,
                    "errors": errors,
                }
            )
        return skills

    def get(self, skill_id: str) -> SkillDefinition:
        directory = self.skills_dir / skill_id
        manifest_path = directory / "manifest.yaml"
        instruction_path = directory / "SKILL.md"
        if not manifest_path.is_file() or not instruction_path.is_file():
            raise KeyError(f"Unknown skill: {skill_id}")

        manifest = load_data(manifest_path)
        errors = validate(manifest, self.schemas_dir / "skill.schema.json")
        if errors:
            raise ValueError("Invalid manifest: " + "; ".join(errors))

        references: dict[str, Any] = {}
        for name, relative in (manifest.get("references") or {}).items():
            source = directory / str(relative)
            if not source.is_file():
                raise ValueError(f"Missing reference for {skill_id}: {relative}")
            references[name] = load_data(source)
        return SkillDefinition(
            id=skill_id,
            directory=directory,
            manifest=manifest,
            instructions=instruction_path.read_text(encoding="utf-8"),
            references=references,
        )

    def validate_invocation(self, invocation: dict[str, Any]) -> list[str]:
        errors = validate(invocation, self.schemas_dir / "invocation.schema.json")
        if errors:
            return errors
        try:
            skill = self.get(str(invocation.get("skill") or ""))
        except (KeyError, ValueError) as exc:
            return [str(exc)]
        action = str(invocation.get("action") or "")
        if action not in skill.manifest.get("actions", []):
            return [f"Unknown action '{action}' for skill '{skill.id}'"]
        return []

    def catalog(self, skill_id: str) -> dict[str, Any]:
        skill = self.get(skill_id)
        if skill_id != "viral-script":
            return {
                "skill": skill_id,
                "manifest": skill.manifest,
                "references": skill.references,
            }

        templates = skill.references.get("templates", {}).get("templates", [])
        deliveries = skill.references.get("deliveries", {}).get("presets", [])
        styles = skill.references.get("styles", {}).get("styles", [])
        structures = []
        for index, template in enumerate(templates, 1):
            if not isinstance(template, dict):
                continue
            structures.append(
                {
                    "id": template.get("id"),
                    "name": template.get("name"),
                    "kicker": template.get("kicker") or f"结构 {index:02d}",
                    "description": template.get("description") or " → ".join(template.get("structure") or []),
                    "chain": template.get("display_chain") or template.get("structure") or [],
                    "color": template.get("color") or "blue",
                }
            )
        return {
            "skill": skill_id,
            "version": skill.manifest.get("version"),
            "structures": structures,
            "delivery_presets": deliveries,
            "style_presets": styles,
        }
