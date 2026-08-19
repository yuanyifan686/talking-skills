from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from shared.media.ffmpeg import escape_filter_path, find_cjk_font, has_audio, probe
from shared.utils.protocol import print_json, response
from hook_layout import HookLayout, HookLayoutError, fit_hook_layout


def video_filter(width: int, height: int, fps: int) -> str:
    return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def prepare_hook_layout(args: argparse.Namespace) -> tuple[HookLayout | None, Path | None]:
    if not args.hook_text:
        return None, None
    font = find_cjk_font(args.font)
    if not font:
        raise RuntimeError("Hook text rendering requires a CJK font; pass --font")
    layout = fit_hook_layout(
        args.hook_text,
        args.width,
        args.height,
        max_width_ratio=getattr(args, "max_width_ratio", 0.84),
        safe_margin_x=getattr(args, "safe_margin_x", 96),
        safe_margin_y=getattr(args, "safe_margin_y", 160),
        min_font_size=getattr(args, "min_font_size", 32),
        max_font_size=getattr(args, "max_font_size", None),
        max_lines=getattr(args, "max_lines", 3),
        max_hook_chars=getattr(args, "max_hook_chars", 25),
        auto_compress=not getattr(args, "no_auto_compress", False),
    )
    return layout, font


def compose(args: argparse.Namespace) -> tuple[Path, list[list[str]]]:
    if not args.source.is_file():
        raise FileNotFoundError(f"Source video not found: {args.source}")
    if args.intro_type == "provided_clip" and (not args.provided_clip or not args.provided_clip.is_file()):
        raise FileNotFoundError("provided_clip intro requires --provided-clip")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    hook_layout, hook_font = prepare_hook_layout(args)
    setattr(args, "hook_layout", hook_layout.as_dict() if hook_layout else None)
    with tempfile.TemporaryDirectory(prefix="talking-skills-") as temp_name:
        temp = Path(temp_name)
        intro = temp / "intro.mp4"
        normalized = temp / "source.mp4"
        vf = video_filter(args.width, args.height, args.fps)
        if args.intro_type == "provided_clip":
            intro_input = ["-i", str(args.provided_clip)]
        elif args.intro_type == "freeze_frame":
            frame = temp / "frame.jpg"
            frame_command = ["ffmpeg", "-v", "error", "-y", "-i", str(args.source), "-frames:v", "1", str(frame)]
            commands.append(frame_command)
            run(frame_command)
            intro_input = ["-loop", "1", "-i", str(frame)]
        else:
            intro_input = ["-f", "lavfi", "-i", f"color=c={args.background}:s={args.width}x{args.height}:r={args.fps}:d={args.duration}"]

        audio_args: list[str]
        audio_map: list[str]
        if args.audio and args.audio.is_file():
            audio_args = ["-i", str(args.audio)]
            audio_map = ["-map", "0:v:0", "-map", "1:a:0"]
        else:
            audio_args = ["-f", "lavfi", "-t", str(args.duration), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            audio_map = ["-map", "0:v:0", "-map", "1:a:0"]
        if hook_layout and hook_font:
            hook_file = temp / "hook.txt"
            hook_file.write_text(hook_layout.text, encoding="utf-8")
            vf += ",drawtext=" + (
                f"fontfile='{escape_filter_path(hook_font)}':textfile='{escape_filter_path(hook_file)}':"
                f"fontcolor=white:fontsize={hook_layout.font_size}:line_spacing={hook_layout.line_spacing}:"
                f"x=(w-tw)/2:y=(h-th)/2:box=1:boxcolor=black@0.42:boxborderw={hook_layout.box_border}"
            )
        intro_command = ["ffmpeg", "-v", "error", "-y", *intro_input, *audio_args, *audio_map, "-t", str(args.duration), "-vf", vf, "-c:v", "libx264", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(intro)]
        commands.append(intro_command)
        run(intro_command)

        source_audio_args = [] if has_audio(args.source) else ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        source_map = ["-map", "0:v:0", "-map", "0:a:0?"] if not source_audio_args else ["-map", "0:v:0", "-map", "1:a:0"]
        normalize_command = ["ffmpeg", "-v", "error", "-y", "-i", str(args.source), *source_audio_args, *source_map, "-vf", video_filter(args.width, args.height, args.fps), "-c:v", "libx264", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(normalized)]
        commands.append(normalize_command)
        run(normalize_command)

        concat_file = temp / "concat.txt"
        concat_file.write_text(f"file '{intro.as_posix()}'\nfile '{normalized.as_posix()}'\n", encoding="utf-8")
        concat_command = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(args.output)]
        commands.append(concat_command)
        run(concat_command)
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise RuntimeError("Composition did not produce a non-empty file")
    probe(args.output)
    return args.output, commands


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepend a question intro to a source video")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--intro-type", choices=["freeze_frame", "solid_background", "provided_clip"], default="solid_background")
    parser.add_argument("--provided-clip", type=Path)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--hook-text", default="")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--background", default="#111827")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-width-ratio", type=float, default=0.84)
    parser.add_argument("--safe-margin-x", type=int, default=96)
    parser.add_argument("--safe-margin-y", type=int, default=160)
    parser.add_argument("--min-font-size", type=int, default=32)
    parser.add_argument("--max-font-size", type=int)
    parser.add_argument("--max-lines", type=int, default=3)
    parser.add_argument("--max-hook-chars", type=int, default=25)
    parser.add_argument("--no-auto-compress", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        hook_layout, _ = prepare_hook_layout(args)
    except (HookLayoutError, RuntimeError) as exc:
        print_json(response(status="error", state="composition", message="Hook text layout validation failed.", errors=[{"code": "hook_layout_invalid", "message": str(exc), "recoverable": True}]))
        return 2
    plan = {
        "intro_type": args.intro_type,
        "source": str(args.source),
        "output": str(args.output),
        "audio": str(args.audio) if args.audio else None,
        "hook_text": args.hook_text,
        "font": str(args.font) if args.font else None,
        "duration": args.duration,
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "layout": hook_layout.as_dict() if hook_layout else None,
    }
    if args.plan_only:
        print_json(response(status="partial", state="composition", message="Composition plan created; video not rendered.", data={"video_plan": plan, "skipped": ["video_render"]}, next_actions=["render_video", "create_person_intro"]))
        return 0
    try:
        output, commands = compose(args)
    except (OSError, RuntimeError, HookLayoutError, subprocess.CalledProcessError) as exc:
        print_json(response(status="partial", state="composition", message="Video composition was not completed.", data={"video_plan": plan}, errors=[{"code": "composition_failed", "message": str(exc), "recoverable": True}], next_actions=["check_ffmpeg_or_assets", "retry_compose"]))
        return 2
    print_json(response(status="success", state="completed", message="Question intro and source video composed.", data={"video": {**plan, "hooked": str(output)}, "commands_executed": len(commands)}, files=[{"path": str(output), "kind": "video", "mime_type": "video/mp4", "exists": True}], next_actions=["create_person_intro", "review_hooked_video"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
