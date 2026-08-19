from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.executor import SkillExecutor
from runtime.pipeline import PipelineRunner
from runtime.providers.base import LLMProvider
from runtime.registry import SkillRegistry
from shared.utils.protocol import response


class QueueProvider(LLMProvider):
    def __init__(self, values: list[str]) -> None:
        self.values = list(values)

    def complete(self, **_: object) -> str:
        if not self.values:
            raise AssertionError("No fake provider response remains")
        return self.values.pop(0)


class RuntimeTests(unittest.TestCase):
    def test_registry_rejects_unknown_action(self):
        errors = SkillRegistry().validate_invocation(
            {"skill": "viral-script", "action": "does-not-exist", "input": {"topic": "AI"}}
        )
        self.assertTrue(any("Unknown action" in error for error in errors))

    def test_catalog_is_loaded_from_skill_references(self):
        catalog = SkillRegistry().catalog("viral-script")
        self.assertGreaterEqual(len(catalog["structures"]), 6)
        self.assertEqual(catalog["delivery_presets"][0]["id"], "sharp")

    def test_viral_pipeline_action_generates_completed_script(self):
        provider = QueueProvider(
            [
                """{
                  "structure": {"id": "cognitive_contrast_upgrade_v1", "reason": "适合认知对比", "match_score": 91},
                  "versions": [{
                    "id": "sharp",
                    "title": "AI真正拉开的差距是什么",
                    "hook": "AI工具用得越多，就真的越厉害吗？",
                    "body": ["很多人忙着收集工具，却没有先找出工作里最重复的问题。", "先选一个每天发生的任务，再让AI稳定完成它。"],
                    "ending": "工具不是能力，把工具放进流程才是能力。",
                    "style": "sharp_opinion"
                  }]
                }"""
            ]
        )
        result = SkillExecutor(provider=provider).invoke(
            {
                "skill": "viral-script",
                "action": "run_pipeline",
                "input": {"topic": "普通人如何学习AI", "duration": 15, "variant_count": 1, "question_hook": True},
            }
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["context"]["project"]["script"]["template_id"], "cognitive_contrast_upgrade_v1")

    def test_score_action_uses_model_judgment_and_deterministic_total(self):
        script = "看完这条视频，你会知道为什么工具越多，结果反而越差。"
        dimension_ids = (
            "interrupt_prediction", "reward_expectation", "loss_aversion", "precise_naming",
            "replicability", "no_fluff", "ai_adaptability", "emotional_intensity",
            "memorability", "shareability",
        )
        dimensions = {
            name: {
                "score": 7,
                "evidence": [{"quote": "看完这条视频", "reason": "原文提供了明确的观看承诺"}],
                "improvement": "增加一个更具体且可执行的交付。",
            }
            for name in dimension_ids
        }
        import json

        result = SkillExecutor(provider=QueueProvider([json.dumps({"dimensions": dimensions}, ensure_ascii=False)])).invoke(
            {"skill": "score-viral-script", "action": "score", "input": {"script": script}}
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["scorecard"]["total"], 70)

    def test_short_video_pipeline_executes_steps_and_score_gate(self):
        class StubExecutor:
            def __init__(self) -> None:
                self.score_calls = 0

            def invoke(self, invocation):
                context = deepcopy(invocation["context"])
                project = context["project"]
                skill = invocation["skill"]
                if skill == "viral-script":
                    project["script"] = {"title": "标题", "content": "原稿", "estimated_duration": 30, "estimated_characters": 160}
                elif skill == "score-viral-script":
                    self.score_calls += 1
                    project["script_score"] = {"total": 75 if self.score_calls == 1 else 84}
                elif skill == "optimize-viral-script":
                    project["script_optimization"] = {"optimized_script": "优化稿"}
                    project["script"]["content"] = "优化稿"
                elif skill == "question-hook":
                    project["hook"] = {"text": "为什么结果会不同？"}
                return response(status="success", state="completed", message="ok", context=context)

        result = PipelineRunner(StubExecutor()).run("short-video", input_data={"topic": "测试主题"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["context"]["project"]["script_score"]["total"], 84)
        self.assertEqual(result["context"]["project"]["script"]["content"], "优化稿")
        self.assertEqual([item["step"] for item in result["data"]["trace"]], ["script", "score", "optimize", "rescore", "hook", "person"])
        self.assertEqual(result["data"]["trace"][-1]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
