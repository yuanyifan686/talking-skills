from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.protocol import print_json, response


SCORER_PATH = ROOT / "skills" / "score-viral-script" / "scripts" / "score_script.py"
SPEC = importlib.util.spec_from_file_location("score_viral_script_dependency", SCORER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load score dependency: {SCORER_PATH}")
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)

ALL_DIMENSIONS = scorer.ALL_DIMENSIONS
PLACEHOLDER_PATTERN = re.compile(r"(?:\[TODO|<TODO|待补充|此处填写|完整原文)", re.IGNORECASE)


def schema_errors(value: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # type: ignore
        from referencing import Registry, Resource  # type: ignore
    except ImportError:
        return []
    schema = json.loads((ROOT / "schemas" / "optimization.schema.json").read_text(encoding="utf-8"))
    resources = []
    for candidate in (ROOT / "schemas").glob("*.json"):
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
        resources.append((loaded.get("$id", candidate.as_uri()), Resource.from_contents(loaded)))
    validator = jsonschema.Draft202012Validator(schema, registry=Registry().with_resources(resources))
    return [
        f"{'/'.join(map(str, error.path)) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    ]


def _scorecard(value: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict):
        return None, ["scorecard must be an object"]
    normalized, errors, _ = scorer.normalize(value)
    return normalized, [f"scorecard: {error}" for error in errors]


def mode_for(scorecard: dict[str, Any], force_rewrite: bool = False) -> str:
    if force_rewrite or scorecard["total"] < 60:
        return "rewrite"
    if scorecard["total"] < 80:
        return "surgical"
    return "polish"


def select_targets(
    scorecard: dict[str, Any],
    requested: list[str] | None = None,
    max_targets: int | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if requested:
        unknown = [name for name in requested if name not in ALL_DIMENSIONS]
        if unknown:
            return [], [f"unknown target dimension: {name}" for name in unknown]
        targets = list(dict.fromkeys(requested))
    else:
        targets = sorted(
            (name for name in ALL_DIMENSIONS if scorecard["dimensions"][name]["score"] < 8),
            key=lambda name: (scorecard["dimensions"][name]["score"], ALL_DIMENSIONS.index(name)),
        )
        if not targets:
            targets = sorted(ALL_DIMENSIONS, key=lambda name: (scorecard["dimensions"][name]["score"], ALL_DIMENSIONS.index(name)))
    mode = mode_for(scorecard)
    default_limits = {"polish": 1, "surgical": 2, "rewrite": 4}
    limit = max_targets if max_targets is not None else default_limits[mode]
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        errors.append("max_targets must be a positive integer")
        return [], errors
    return targets[:limit], errors


def build_plan(
    scorecard_value: dict[str, Any],
    requested: list[str] | None = None,
    max_targets: int | None = None,
    force_rewrite: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    scorecard, errors = _scorecard(scorecard_value)
    if errors or scorecard is None:
        return None, errors
    effective_max_targets = 4 if force_rewrite and max_targets is None else max_targets
    targets, target_errors = select_targets(scorecard, requested, effective_max_targets)
    if target_errors:
        return None, target_errors
    mode = mode_for(scorecard, force_rewrite=force_rewrite)
    plan = {
        "mode": mode,
        "baseline_total": scorecard["total"],
        "target_score": 8,
        "target_dimensions": targets,
        "instructions": [
            {
                "dimension": name,
                "baseline_score": scorecard["dimensions"][name]["score"],
                "improvement": scorecard["dimensions"][name].get("improvement") or "Make one bounded, evidence-preserving improvement.",
            }
            for name in targets
        ],
    }
    return plan, []


def _character_count(text: str) -> int:
    return len(re.sub(r"[\s#*_`>]", "", text))


def validate_revision(value: dict[str, Any], max_change_ratio: float = 0.65) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(value, dict):
        return None, ["optimization must be an object"], []

    source = value.get("source_script")
    optimized = value.get("optimized_script")
    if not isinstance(source, str) or not source.strip():
        errors.append("source_script is required")
        source = ""
    if not isinstance(optimized, str) or not optimized.strip():
        errors.append("optimized_script is required")
        optimized = ""
    if source and optimized and source.strip() == optimized.strip():
        errors.append("optimized_script must differ from source_script")
    if optimized and PLACEHOLDER_PATTERN.search(optimized):
        errors.append("optimized_script contains a placeholder")

    scorecard, score_errors = _scorecard(value.get("scorecard"))
    errors.extend(score_errors)
    if scorecard is not None and source and scorecard["source_script"] != source:
        errors.append("scorecard.source_script must exactly match source_script")

    mode = value.get("mode")
    if mode not in {"polish", "surgical", "rewrite"}:
        errors.append("mode must be polish, surgical, or rewrite")

    targets = value.get("target_dimensions")
    if not isinstance(targets, list) or not targets:
        errors.append("target_dimensions requires at least one dimension")
        targets = []
    else:
        if len(targets) != len(set(targets)):
            errors.append("target_dimensions must be unique")
        errors.extend(f"unknown target dimension: {name}" for name in targets if name not in ALL_DIMENSIONS)

    changes = value.get("changes")
    covered: set[str] = set()
    if not isinstance(changes, list) or not changes:
        errors.append("changes requires at least one item")
        changes = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            errors.append(f"changes[{index}] must be an object")
            continue
        dimension = change.get("dimension")
        before = change.get("before_quote")
        after = change.get("after_quote")
        reason = change.get("reason")
        if dimension not in ALL_DIMENSIONS:
            errors.append(f"changes[{index}].dimension is invalid")
        else:
            covered.add(dimension)
            if dimension not in targets:
                errors.append(f"changes[{index}].dimension is not a target dimension")
        if not isinstance(before, str) or not before.strip():
            errors.append(f"changes[{index}].before_quote is required")
        elif before not in source:
            errors.append(f"changes[{index}].before_quote is not an exact source quotation")
        if not isinstance(after, str) or not after.strip():
            errors.append(f"changes[{index}].after_quote is required")
        elif after not in optimized:
            errors.append(f"changes[{index}].after_quote is not an exact optimized quotation")
        if isinstance(before, str) and isinstance(after, str) and before.strip() and before == after:
            errors.append(f"changes[{index}] must show an actual textual change")
        if not isinstance(reason, str) or len(reason.strip()) < 4:
            errors.append(f"changes[{index}].reason is too short")
    for target in targets:
        if target in ALL_DIMENSIONS and target not in covered:
            errors.append(f"target dimension has no change evidence: {target}")

    if errors:
        return None, list(dict.fromkeys(errors)), warnings

    similarity = SequenceMatcher(None, source, optimized).ratio()
    change_ratio = 1 - similarity
    if mode in {"polish", "surgical"} and change_ratio > max_change_ratio:
        warnings.append(f"change_ratio {change_ratio:.3f} exceeds the suggested {max_change_ratio:.3f} for {mode} mode")
    source_characters = _character_count(source)
    optimized_characters = _character_count(optimized)
    result = deepcopy(value)
    result["scorecard"] = scorecard
    result["metrics"] = {
        "source_characters": source_characters,
        "optimized_characters": optimized_characters,
        "estimated_duration": round(optimized_characters / 5.2, 1),
        "similarity": round(similarity, 4),
        "change_ratio": round(change_ratio, 4),
    }
    result["warnings"] = warnings
    contract_errors = schema_errors(result)
    if contract_errors:
        return None, contract_errors, warnings
    return result, [], warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or validate a score-driven spoken-script optimization")
    subparsers = parser.add_subparsers(dest="action", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("scorecard", type=Path)
    plan_parser.add_argument("--target", action="append", dest="targets")
    plan_parser.add_argument("--max-targets", type=int)
    plan_parser.add_argument("--rewrite", action="store_true")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("optimization", type=Path)
    validate_parser.add_argument("--max-change-ratio", type=float, default=0.65)

    args = parser.parse_args()
    payload = json.loads((args.scorecard if args.action == "plan" else args.optimization).read_text(encoding="utf-8"))
    if args.action == "plan":
        plan, errors = build_plan(payload, args.targets, args.max_targets, force_rewrite=args.rewrite)
        if errors:
            print_json(response(status="error", state="planning", message="Optimization planning failed.", errors=[{"code": "invalid_scorecard", "message": error, "recoverable": True} for error in errors]))
            return 2
        print_json(response(status="success", state="planning", message="Optimization plan created.", data={"plan": plan}))
        return 0

    optimization, errors, warnings = validate_revision(payload, max_change_ratio=args.max_change_ratio)
    if errors:
        print_json(response(status="error", state="validation", message="Optimization validation failed.", errors=[{"code": "invalid_optimization", "message": error, "recoverable": True} for error in errors]))
        return 2
    print_json(response(
        status="success",
        state="completed",
        message="Script optimization evidence validated.",
        data={"optimization": optimization, "warnings": warnings},
        next_actions=[{"skill": "score-viral-script", "action": "score", "reason": "Measure the optimized script with the same rubric."}],
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
