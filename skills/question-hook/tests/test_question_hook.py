from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import yaml


SKILL = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hook_module = load_module("question_hook_generator", SKILL / "scripts" / "generate_hook.py")
compose_module = load_module("question_video_composer", SKILL / "scripts" / "compose_video.py")
layout_module = load_module("question_hook_layout", SKILL / "scripts" / "hook_layout.py")


class QuestionHookTests(unittest.TestCase):
    def test_valid_input(self):
        hook = hook_module.build_hook("真正会使用AI的人，并不是每天研究几十种AI工具的人。")
        self.assertEqual(hook["text"], "AI工具用得越多，就真的越厉害吗？")
        self.assertEqual(hook["relation_to_script"], "direct")
        self.assertTrue(8 <= hook_module.chinese_count(hook["text"]) <= 25)

    def test_missing_input(self):
        with self.assertRaises(ValueError):
            hook_module.build_hook("")

    def test_pattern_loading_and_constraints(self):
        data = yaml.safe_load((SKILL / "references" / "hook_patterns.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(data["patterns"]), 8)
        self.assertEqual(data["constraints"]["chinese_characters"]["max"], 25)

    def test_tts_plan_only_degrades_cleanly(self):
        command = [sys.executable, str(SKILL / "scripts" / "tts.py"), "--text", "为什么会这样？", "--output", "unused.mp3", "--plan-only"]
        completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "partial")
        self.assertIn("tts_execution", result["data"]["skipped"])

    def test_hook_layout_wraps_and_fits_safe_area(self):
        layout = layout_module.fit_hook_layout(
            "为什么AI时代工具越来越多，却越来越没用？",
            1080,
            1920,
        )
        self.assertFalse(layout.overflow)
        self.assertLessEqual(len(layout.lines), 3)
        self.assertLessEqual(max(layout_module.estimate_line_width(line, layout.font_size) for line in layout.lines), layout.max_width)
        self.assertGreaterEqual(layout.safe_margin_x, 12)
        self.assertGreaterEqual(layout.safe_margin_y, 12)

    def test_hook_layout_compresses_common_long_phrase(self):
        layout = layout_module.fit_hook_layout(
            "为什么现在AI时代这个工具越来越多但是越来越没什么用呢？",
            1080,
            1920,
        )
        self.assertTrue(layout.compressed)
        self.assertTrue(layout.compression_actions)
        self.assertLessEqual(layout_module.visible_char_count(layout.text), 25)

    def test_hook_layout_rejects_unfit_text(self):
        with self.assertRaises(layout_module.HookLayoutError):
            layout_module.fit_hook_layout(
                "这是一个很长很长很长很长很长很长很长的问题？",
                120,
                120,
                max_lines=1,
                min_font_size=12,
                max_hook_chars=80,
            )

    def test_auto_tts_provider_orders_local_before_cloud(self):
        from shared.tts.factory import get_provider

        provider = get_provider("auto")
        self.assertEqual(provider.id, "auto")
        self.assertEqual([item.id for item in provider.providers], ["cosyvoice", "seed-audio", "volcengine"])

    def test_seed_audio_builds_supplied_api_contract(self):
        from shared.tts.base import TTSRequest
        from shared.tts.seed_audio import ByteDanceSeedAudioTTSProvider

        with mock.patch.dict(
            "os.environ",
            {
                "BYTEDANCE_SEED_AUDIO_API_KEY": "test-only-key",
                "BYTEDANCE_SEED_AUDIO_ENDPOINT": "https://example.test/tts",
            },
            clear=False,
        ):
            provider = ByteDanceSeedAudioTTSProvider()
            payload = provider.build_payload(TTSRequest("为什么现在AI工具很多却没什么用？", Path("hook.mp3")))
        self.assertEqual(provider.headers["X-Api-Key"], "test-only-key")
        self.assertEqual(payload["model"], "seed-audio-1.0")
        self.assertEqual(payload["text_prompt"], "为什么现在AI工具很多却没什么用？")
        self.assertEqual(payload["audio_config"]["format"], "mp3")
        self.assertEqual(payload["audio_config"]["speech_rate"], 0)

    def test_seed_audio_extracts_nested_base64_audio(self):
        import base64
        from shared.tts.seed_audio import ByteDanceSeedAudioTTSProvider

        encoded = base64.b64encode(b"fake-mp3").decode("ascii")
        audio, content_type = ByteDanceSeedAudioTTSProvider._extract_json_audio(
            json.dumps({"data": {"audio": encoded}}).encode("utf-8")
        )
        self.assertEqual(audio, b"fake-mp3")
        self.assertEqual(content_type, "audio/mpeg")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
    def test_actual_video_composition(self):
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            source = temp / "source.mp4"
            output = temp / "final.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x240:r=12:d=0.4",
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-t", "0.4",
                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
            ], check=True)
            args = argparse.Namespace(
                source=source, output=output, intro_type="solid_background", provided_clip=None, audio=None,
                hook_text="为什么会这样？", font=None, duration=0.25, background="black", width=160, height=240, fps=12,
            )
            rendered, commands = compose_module.compose(args)
            self.assertTrue(rendered.is_file() and rendered.stat().st_size > 0)
            self.assertEqual(len(commands), 3)


if __name__ == "__main__":
    unittest.main()
