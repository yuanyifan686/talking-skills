from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SKILL = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scorer = load_module("viral_script_scorer", SKILL / "scripts" / "score_script.py")


def valid_assessment(score: int = 8) -> dict:
    script = "看完这条视频，你会得到一个三步公式。很多人以为工具越多越厉害，但真正重要的是解决问题。"
    dimensions = {}
    for name in scorer.ALL_DIMENSIONS:
        dimensions[name] = {
            "score": score,
            "evidence": [{"quote": "工具越多越厉害", "reason": "引用原文并对应当前维度的评分判断"}],
            "improvement": None if score >= 8 else "补充一个更明确、可执行的表达",
        }
    return {"source_script": script, "dimensions": dimensions}


class ScoreViralScriptTests(unittest.TestCase):
    def test_valid_input_totals_and_classification(self):
        scorecard, errors, corrections = scorer.normalize(valid_assessment())
        self.assertEqual(errors, [])
        self.assertEqual(corrections, [])
        self.assertEqual(scorecard["subtotals"], {"core": 32, "practicality": 24, "bonus": 24})
        self.assertEqual(scorecard["total"], 80)
        self.assertEqual(scorecard["conclusion"]["level"], "very_high")

    def test_missing_dimension(self):
        assessment = valid_assessment()
        del assessment["dimensions"]["memorability"]
        scorecard, errors, _ = scorer.normalize(assessment)
        self.assertIsNone(scorecard)
        self.assertTrue(any("memorability" in error for error in errors))

    def test_invalid_score_and_missing_improvement(self):
        assessment = valid_assessment()
        assessment["dimensions"]["interrupt_prediction"]["score"] = 11
        assessment["dimensions"]["reward_expectation"]["score"] = 5
        assessment["dimensions"]["reward_expectation"]["improvement"] = None
        _, errors, _ = scorer.normalize(assessment)
        self.assertTrue(any("interrupt_prediction" in error for error in errors))
        self.assertTrue(any("reward_expectation.improvement" in error for error in errors))

    def test_fabricated_evidence_is_rejected(self):
        assessment = valid_assessment()
        assessment["dimensions"]["shareability"]["evidence"][0]["quote"] = "原文中不存在的句子"
        _, errors, _ = scorer.normalize(assessment)
        self.assertTrue(any("exact source quotation" in error for error in errors))

    def test_arithmetic_is_recalculated(self):
        assessment = valid_assessment()
        assessment.update({
            "subtotals": {"core": 4, "practicality": 3, "bonus": 0},
            "total": 7,
            "conclusion": {"level": "insufficient", "label": "错误结论"},
            "strongest_dimensions": [],
            "priority_improvements": [],
        })
        scorecard, errors, corrections = scorer.normalize(assessment)
        self.assertEqual(errors, [])
        self.assertEqual(scorecard["total"], 80)
        self.assertIn("recalculated total", corrections)

    def test_threshold_boundaries(self):
        self.assertEqual(scorer.classify(59)["level"], "insufficient")
        self.assertEqual(scorer.classify(60)["level"], "potential")
        self.assertEqual(scorer.classify(79)["level"], "potential")
        self.assertEqual(scorer.classify(80)["level"], "very_high")

    def test_rubric_loading_and_cli(self):
        rubric = yaml.safe_load((SKILL / "references" / "scoring_rubric.yaml").read_text(encoding="utf-8"))
        self.assertEqual(rubric["total_points"], 100)
        with tempfile.TemporaryDirectory() as temp_name:
            assessment_path = Path(temp_name) / "assessment.json"
            assessment_path.write_text(json.dumps(valid_assessment(), ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(SKILL / "scripts" / "score_script.py"), str(assessment_path)], check=True, capture_output=True, text=True, encoding="utf-8")
            result = json.loads(completed.stdout)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["data"]["scorecard"]["total"], 80)
            self.assertEqual(result["next_actions"][0]["skill"], "question-hook")


if __name__ == "__main__":
    unittest.main()
