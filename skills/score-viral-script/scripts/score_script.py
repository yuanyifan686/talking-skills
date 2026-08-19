from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.protocol import print_json, response


CORE = ("interrupt_prediction", "reward_expectation", "loss_aversion", "precise_naming")
PRACTICALITY = ("replicability", "no_fluff", "ai_adaptability")
BONUS = ("emotional_intensity", "memorability", "shareability")
ALL_DIMENSIONS = CORE + PRACTICALITY + BONUS
NAMES = {
    "interrupt_prediction": "打断预测",
    "reward_expectation": "奖励期待",
    "loss_aversion": "损失厌恶",
    "precise_naming": "精准命名",
    "replicability": "可复制性",
    "no_fluff": "无废话程度",
    "ai_adaptability": "AI适配性",
    "emotional_intensity": "情绪强度",
    "memorability": "记忆点",
    "shareability": "传播性",
}


def classify(total: int) -> dict[str, str]:
    if total >= 80:
        return {"level": "very_high", "label": "爆款潜力极高，可直接复用"}
    if total >= 60:
        return {"level": "potential", "label": "有爆款潜力，需优化1-2个维度"}
    return {"level": "insufficient", "label": "不具备爆款潜质，建议重新创作"}


def schema_errors(value: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return []
    schema = json.loads((ROOT / "schemas" / "score.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(map(str, error.path)) or '$'}: {error.message}" for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path))]


def validate_semantics(scorecard: dict[str, Any], strict_evidence: bool = True) -> list[str]:
    errors: list[str] = []
    script = scorecard.get("source_script")
    if not isinstance(script, str) or not script.strip():
        errors.append("source_script is required")
        script = ""
    dimensions = scorecard.get("dimensions")
    if not isinstance(dimensions, dict):
        return [*errors, "dimensions must be an object"]
    missing = [dimension for dimension in ALL_DIMENSIONS if dimension not in dimensions]
    extra = [dimension for dimension in dimensions if dimension not in ALL_DIMENSIONS]
    errors.extend(f"missing dimension: {dimension}" for dimension in missing)
    errors.extend(f"unknown dimension: {dimension}" for dimension in extra)
    for dimension in ALL_DIMENSIONS:
        item = dimensions.get(dimension)
        if not isinstance(item, dict):
            continue
        minimum = 0 if dimension in BONUS else 1
        score = item.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not minimum <= score <= 10:
            errors.append(f"{dimension}.score must be an integer from {minimum} to 10")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{dimension}.evidence requires at least one item")
        else:
            for index, entry in enumerate(evidence):
                if not isinstance(entry, dict):
                    errors.append(f"{dimension}.evidence[{index}] must be an object")
                    continue
                quote = entry.get("quote")
                reason = entry.get("reason")
                if not isinstance(quote, str) or not quote.strip():
                    errors.append(f"{dimension}.evidence[{index}].quote is required")
                elif strict_evidence and quote not in script:
                    errors.append(f"{dimension}.evidence[{index}].quote is not an exact source quotation")
                if not isinstance(reason, str) or len(reason.strip()) < 4:
                    errors.append(f"{dimension}.evidence[{index}].reason is too short")
        improvement = item.get("improvement")
        if isinstance(score, int) and score < 8 and (not isinstance(improvement, str) or not improvement.strip()):
            errors.append(f"{dimension}.improvement is required when score is below 8")
    return errors


def calculated_fields(scorecard: dict[str, Any]) -> dict[str, Any]:
    dimensions = scorecard["dimensions"]
    core = sum(dimensions[name]["score"] for name in CORE)
    practicality = sum(dimensions[name]["score"] for name in PRACTICALITY)
    bonus = sum(dimensions[name]["score"] for name in BONUS)
    total = core + practicality + bonus
    ranked = sorted(ALL_DIMENSIONS, key=lambda name: (-dimensions[name]["score"], ALL_DIMENSIONS.index(name)))
    weak = sorted((name for name in ALL_DIMENSIONS if dimensions[name]["score"] < 8), key=lambda name: (dimensions[name]["score"], ALL_DIMENSIONS.index(name)))
    priority_improvements = list(
        dict.fromkeys(dimensions[name]["improvement"].strip() for name in weak)
    )[:3]
    return {
        "subtotals": {"core": core, "practicality": practicality, "bonus": bonus},
        "total": total,
        "conclusion": classify(total),
        "strongest_dimensions": [NAMES[name] for name in ranked[:3]],
        "priority_improvements": priority_improvements,
    }


def normalize(scorecard: dict[str, Any], strict_evidence: bool = True) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors = [*schema_errors(scorecard), *validate_semantics(scorecard, strict_evidence)]
    if errors:
        return None, list(dict.fromkeys(errors)), []
    result = deepcopy(scorecard)
    calculated = calculated_fields(result)
    corrections = []
    for field, value in calculated.items():
        if field in result and result[field] != value:
            corrections.append(f"recalculated {field}")
        result[field] = value
    result["rubric_version"] = "1.0.0"
    return result, [], corrections


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and total a viral spoken-script assessment")
    parser.add_argument("assessment", type=Path, help="Scorecard JSON file")
    parser.add_argument("--allow-nonexact-evidence", action="store_true")
    args = parser.parse_args()
    assessment = json.loads(args.assessment.read_text(encoding="utf-8"))
    scorecard, errors, corrections = normalize(assessment, strict_evidence=not args.allow_nonexact_evidence)
    if errors:
        print_json(response(status="error", state="validation", message="Scorecard validation failed.", errors=[{"code": "invalid_scorecard", "message": error, "recoverable": True} for error in errors]))
        return 2
    next_actions = (
        [{"skill": "question-hook", "action": "generate", "reason": "The score gate passed."}]
        if scorecard["total"] >= 80
        else [{"skill": "optimize-viral-script", "action": "optimize", "reason": "Improve the weakest scored dimensions."}]
    )
    print_json(response(status="success", state="completed", message="Scorecard validated and totaled.", data={"scorecard": scorecard, "corrections": corrections}, next_actions=next_actions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
