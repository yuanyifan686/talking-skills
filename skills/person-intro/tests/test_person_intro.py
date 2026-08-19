from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
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


intro_module = load_module("person_intro_renderer", SKILL / "scripts" / "render_intro.py")


class PersonIntroTests(unittest.TestCase):
    def setUp(self):
        self.person = {
            "name": "袁艺凡", "title": "FDE 前沿部署工程师", "organization": "示例机构",
            "roles": ["技术顾问"], "education": ["维多利亚大学计算机系"],
            "experience": ["加拿大海外6年工作经验"], "tagline": "让技术真正落地",
        }

    def test_valid_input_selects_at_most_four_lines(self):
        lines = intro_module.select_lines(self.person)
        self.assertEqual(lines[0], "袁艺凡")
        self.assertLessEqual(len(lines), 4)
        self.assertIn("FDE 前沿部署工程师", lines[1])

    def test_missing_input(self):
        with self.assertRaises(ValueError):
            intro_module.select_lines({"name": ""})

    def test_style_loading(self):
        data = yaml.safe_load((SKILL / "references" / "intro_styles.yaml").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["styles"]), 7)
        self.assertTrue(all(item["layout"]["max_lines"] <= 4 for item in data["styles"]))

    def test_auto_position_and_fallback(self):
        self.assertEqual(intro_module.resolve_position("auto", "left"), ("right", False))
        self.assertEqual(intro_module.resolve_position("auto", None), ("bottom_left", True))

    def test_user_assets_are_resolved_from_person_data(self):
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            avatar = temp / "avatar.png"
            logo = temp / "logo.png"
            background = temp / "background.jpg"
            font = temp / "font.ttf"
            for path in (avatar, logo, background, font):
                path.write_bytes(b"asset")
            person = {
                **self.person,
                "assets": {
                    "avatar": str(avatar),
                    "logos": [str(logo)],
                    "background": str(background),
                    "font": str(font),
                },
            }
            args = argparse.Namespace(avatar=None, logo_file=None, background_image=None, font=None)
            assets = intro_module.resolve_assets(args, person)
            self.assertEqual(assets["avatar"], avatar)
            self.assertEqual(assets["logo"], logo)
            self.assertEqual(assets["background"], background)
            self.assertEqual(assets["font"], font)

    def test_missing_user_asset_is_recoverable(self):
        args = argparse.Namespace(avatar=None, logo_file=None, background_image=None, font=None)
        with self.assertRaises(FileNotFoundError):
            intro_module.resolve_assets(args, {**self.person, "assets": {"avatar": "missing/avatar.png"}})

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
    def test_actual_render_when_cjk_font_exists(self):
        font = intro_module.find_cjk_font(None)
        if not font:
            self.skipTest("CJK font unavailable")
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "intro.mp4"
            args = argparse.Namespace(output=output, source_video=None, duration=0.25, font=font, background="black", width=320, height=568, fps=12)
            rendered = intro_module.render(args, intro_module.select_lines(self.person), "bottom_left")
            self.assertTrue(rendered.is_file() and rendered.stat().st_size > 0)
            source = Path(temp_name) / "source.mp4"
            final = Path(temp_name) / "final.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x568:r=12:d=0.35", "-c:v", "libx264", str(source)], check=True)
            overlay_args = argparse.Namespace(output=final, source_video=source, duration=0.25, font=font, background="black", width=320, height=568, fps=12)
            overlaid = intro_module.render(overlay_args, intro_module.select_lines(self.person), "bottom_left")
            self.assertTrue(overlaid.is_file() and overlaid.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
