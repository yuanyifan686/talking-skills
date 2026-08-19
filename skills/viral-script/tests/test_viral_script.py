from __future__ import annotations

import importlib.util
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


workflow = load_module("viral_workflow", SKILL / "scripts" / "workflow.py")
template_store = load_module("template_store", SKILL / "scripts" / "template_store.py")


class ViralScriptTests(unittest.TestCase):
    def test_valid_input_generates_six_varied_titles(self):
        result = workflow.execute({"skill": "viral-script", "action": "generate", "input": {"topic": "AI创业"}})
        self.assertEqual(result["status"], "awaiting_user")
        self.assertEqual(result["state"], "title_selection")
        self.assertEqual(len(result["data"]["titles"]), 6)
        self.assertGreaterEqual(len({item["type"] for item in result["data"]["titles"]}), 5)

    def test_missing_input_requests_topic(self):
        result = workflow.execute({"skill": "viral-script", "action": "generate", "input": {}})
        self.assertEqual(result["state"], "topic")
        self.assertEqual(result["errors"][0]["code"], "missing_topic")

    def test_interactive_workflow_waits_for_choices(self):
        waiting = workflow.execute({"skill": "viral-script", "action": "continue", "state": "title_selection", "input": {}})
        self.assertEqual(waiting["status"], "awaiting_user")
        selected = workflow.execute({"skill": "viral-script", "action": "continue", "state": "title_selection", "input": {"selected_title": 3}})
        self.assertEqual(selected["state"], "style_selection")
        delegated = workflow.execute({"skill": "viral-script", "action": "continue", "state": "style_selection", "input": {"agent_select": True}})
        self.assertEqual(delegated["state"], "script_generation")

    def test_template_loading(self):
        data = yaml.safe_load((SKILL / "references" / "copy_templates.yaml").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["templates"]), 6)
        self.assertTrue(all(item["structure"] for item in data["templates"]))

    def test_invalid_template_and_explicit_save_guard(self):
        invalid = {"id": "Bad-ID"}
        errors = template_store.validate_template(invalid)
        self.assertTrue(errors)
        with tempfile.TemporaryDirectory() as temp_name:
            library = Path(temp_name) / "templates.yaml"
            original = "version: 1.0.0\ntemplates: []\n"
            library.write_text(original, encoding="utf-8")
            valid = {
                "id": "test_template_v1", "name": "测试", "suitable_topics": ["AI"], "platforms": ["generic"],
                "title_formula": ["X"], "hook_formula": ["Y"], "structure": ["hook", "answer"],
                "rhythm": {"pace": "fast"}, "ending_style": ["insight"], "avoid": ["fake_fact"],
            }
            result = template_store.add_template(library, valid, confirm=False)
            self.assertEqual(result["status"], "awaiting_user")
            self.assertEqual(library.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
