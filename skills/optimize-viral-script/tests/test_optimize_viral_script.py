from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


optimizer = load_module("viral_script_optimizer", SKILL / "scripts" / "validate_optimization.py")


def valid_scorecard(default_score: int = 8) -> dict:
    script = "很多人以为工具越多越好，但真正重要的是解决问题。看完你会得到一个方法。"
    dimensions = {}
    for name in optimizer.ALL_DIMENSIONS:
        dimensions[name] = {
            "score": default_score,
            "evidence": [{"quote": "工具越多越好", "reason": "引用原文并对应当前维度的评分判断"}],
            "improvement": None if default_score >= 8 else "补充明确、可执行的表达",
        }
    dimensions["reward_expectation"] = {
        "score": 5,
        "evidence": [{"quote": "看完你会得到一个方法。", "reason": "收益存在但不够具体"}],
        "improvement": "明确说明观众会得到哪一种方法",
    }
    return {"source_script": script, "dimensions": dimensions}


def valid_optimization() -> dict:
    scorecard = valid_scorecard()
    return {
        "source_script": scorecard["source_script"],
        "scorecard": scorecard,
        "optimized_script": "很多人以为工具越多越好，但真正重要的是解决问题。看完你会得到一个三步方法：选问题、选工具、验结果。",
        "mode": "surgical",
        "target_dimensions": ["reward_expectation"],
        "changes": [{
            "dimension": "reward_expectation",
            "before_quote": "看完你会得到一个方法。",
            "after_quote": "看完你会得到一个三步方法：选问题、选工具、验结果。",
            "reason": "把模糊收益改成当前内容可以兑现的具体交付",
            "technique": "name_deliverable",
        }],
        "preserved_constraints": ["central_thesis", "supported_facts"],
    }


class OptimizeViralScriptTests(unittest.TestCase):
    def test_plan_selects_lowest_dimension(self):
        plan, errors = optimizer.build_plan(valid_scorecard())
        self.assertEqual(errors, [])
        self.assertEqual(plan["mode"], "surgical")
        self.assertEqual(plan["target_dimensions"], ["reward_expectation"])

    def test_low_total_uses_rewrite_mode_and_bounded_targets(self):
        scorecard = valid_scorecard(default_score=5)
        plan, errors = optimizer.build_plan(scorecard)
        self.assertEqual(errors, [])
        self.assertEqual(plan["mode"], "rewrite")
        self.assertEqual(len(plan["target_dimensions"]), 4)

    def test_explicit_rewrite_uses_rewrite_target_limit(self):
        requested = list(optimizer.ALL_DIMENSIONS[:4])
        plan, errors = optimizer.build_plan(valid_scorecard(), requested=requested, force_rewrite=True)
        self.assertEqual(errors, [])
        self.assertEqual(plan["mode"], "rewrite")
        self.assertEqual(plan["target_dimensions"], requested)

    def test_valid_revision_has_metrics_and_rescore_handoff(self):
        optimization, errors, warnings = optimizer.validate_revision(valid_optimization())
        self.assertEqual(errors, [])
        self.assertIsInstance(warnings, list)
        self.assertGreater(optimization["metrics"]["optimized_characters"], 0)
        self.assertGreater(optimization["metrics"]["change_ratio"], 0)

    def test_unchanged_script_is_rejected(self):
        value = valid_optimization()
        value["optimized_script"] = value["source_script"]
        _, errors, _ = optimizer.validate_revision(value)
        self.assertTrue(any("must differ" in error for error in errors))

    def test_fabricated_change_quotes_are_rejected(self):
        value = valid_optimization()
        value["changes"][0]["before_quote"] = "原文不存在"
        value["changes"][0]["after_quote"] = "新稿不存在"
        _, errors, _ = optimizer.validate_revision(value)
        self.assertTrue(any("exact source" in error for error in errors))
        self.assertTrue(any("exact optimized" in error for error in errors))

    def test_every_target_requires_change_evidence(self):
        value = valid_optimization()
        value["target_dimensions"].append("emotional_intensity")
        _, errors, _ = optimizer.validate_revision(value)
        self.assertTrue(any("emotional_intensity" in error for error in errors))

    def test_schema_rejects_unknown_output_fields(self):
        value = valid_optimization()
        value["unexpected"] = True
        _, errors, _ = optimizer.validate_revision(value)
        self.assertTrue(errors)

    def test_cli_validation(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "optimization.json"
            path.write_text(json.dumps(valid_optimization(), ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "validate_optimization.py"), "validate", str(path)],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["next_actions"][0]["skill"], "score-viral-script")


if __name__ == "__main__":
    unittest.main()
