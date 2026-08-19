from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.protocol import response


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


adapter = load_module("generic_talking_adapter", ROOT / "adapters" / "generic" / "adapter.py")
config_loader = load_module("talking_config_loader", ROOT / "shared" / "config" / "loader.py")


class ProtocolAndAdapterTests(unittest.TestCase):
    def test_all_manifests_validate(self):
        discovered = adapter.discover()
        self.assertEqual({item["id"] for item in discovered}, {"viral-script", "score-viral-script", "optimize-viral-script", "question-hook", "person-intro"})
        self.assertTrue(all(item["valid"] for item in discovered))

    def test_prepare_resolves_core_without_copying_logic(self):
        invocation = yaml.safe_load((ROOT / "examples" / "generate-viral-script.yaml").read_text(encoding="utf-8"))
        packet = adapter.prepare(invocation)
        self.assertEqual(packet["status"], "ready")
        self.assertTrue(Path(packet["skill"]["instructions"]).is_file())
        self.assertEqual(packet["invocation"]["input"]["topic"], "AI创业")

    def test_prepare_rejects_action_not_declared_by_manifest(self):
        packet = adapter.prepare({"skill": "viral-script", "action": "does-not-exist", "input": {"topic": "AI"}})
        self.assertEqual(packet["status"], "error")
        self.assertIn("Unknown action", packet["errors"][0])

    def test_action_specific_capability_degradation(self):
        disabled = {name: False for name in ("filesystem", "python", "shell", "ffmpeg", "ffprobe", "network", "image_processing", "video_processing")}
        generate = adapter.prepare({"skill": "question-hook", "action": "generate", "input": {"script": "示例"}, "capabilities": {**disabled, "llm": True}})
        compose = adapter.prepare({"skill": "question-hook", "action": "compose", "input": {"hook": {}, "video": {}}, "capabilities": {**disabled, "llm": True}})
        self.assertEqual(generate["execution_mode"], "full")
        self.assertEqual(compose["execution_mode"], "text_only")

    def test_pipeline_context_schema(self):
        context = yaml.safe_load((ROOT / "examples" / "pipeline-context.yaml").read_text(encoding="utf-8"))
        errors = adapter.validate(context, ROOT / "schemas" / "context.schema.json")
        self.assertEqual(errors, [])

    def test_response_schema_requires_universal_envelope(self):
        valid = {"status": "success", "state": "completed", "message": "ok", "data": {}, "files": [], "next_actions": [], "errors": []}
        self.assertEqual(adapter.validate(valid, ROOT / "schemas" / "response.schema.json"), [])
        self.assertTrue(adapter.validate({"status": "success"}, ROOT / "schemas" / "response.schema.json"))

    def test_response_schema_accepts_human_next_step(self):
        valid = {
            "status": "success",
            "state": "completed",
            "message": "ok",
            "data": {},
            "files": [],
            "next_step": "下一步：检查输出。",
            "next_actions": ["review_output"],
            "errors": [],
        }
        self.assertEqual(adapter.validate(valid, ROOT / "schemas" / "response.schema.json"), [])

    def test_response_builds_next_step_from_machine_action(self):
        result = response(
            status="success",
            state="completed",
            message="done",
            next_actions=[{"skill": "score-viral-script", "action": "score", "reason": "复评"}],
        )
        self.assertEqual(result["next_step"], "下一步：调用 score-viral-script 的 score（复评）。")

    def test_agent_adapters_contain_no_workflow_copy(self):
        for name in ("codex", "claude", "workbuddy"):
            data = yaml.safe_load((ROOT / "adapters" / name / "adapter.yaml").read_text(encoding="utf-8"))
            self.assertIn("extends", data)
            self.assertNotIn("workflow", data)
            self.assertNotIn("templates", data)

    def test_shared_config_loading(self):
        config = config_loader.load_config()
        self.assertEqual(config["protocol_version"], "1.0.0")
        self.assertEqual(config["video"]["intro_duration"], 4)


if __name__ == "__main__":
    unittest.main()
