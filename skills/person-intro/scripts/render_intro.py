from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - text-only callers can still create a plan
    yaml = None

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.media.ffmpeg import escape_filter_path, escape_filter_text, find_cjk_font, probe
from shared.utils.protocol import print_json, response


DEFAULT_STYLE = {
    "professional": {"background": "111827", "panel": "0B1220", "accent": "E5E7EB", "text": "FFFFFF", "animation": "fade_slide"},
    "technology": {"background": "06131F", "panel": "071C2A", "accent": "22D3EE", "text": "F8FAFC", "animation": "scan_fade"},
    "teacher": {"background": "1C1917", "panel": "292524", "accent": "FDBA74", "text": "FFF7ED", "animation": "fade"},
    "entrepreneur": {"background": "17120A", "panel": "2A1B08", "accent": "FBBF24", "text": "FFFBEB", "animation": "rise"},
    "creator": {"background": "1F1018", "panel": "351329", "accent": "FB7185", "text": "FFF1F2", "animation": "pop_fade"},
    "minimal": {"background": "111111", "panel": "1F1F1F", "accent": "FFFFFF", "text": "FFFFFF", "animation": "fade"},
    "corporate": {"background": "0F172A", "panel": "172554", "accent": "93C5FD", "text": "EFF6FF", "animation": "fade_slide"},
}


def load_style(style_id: str) -> dict[str, str]:
    """Load visual settings while keeping a safe fallback for text-only installs."""
    fallback = dict(DEFAULT_STYLE.get(style_id, DEFAULT_STYLE["professional"]))
    reference = Path(__file__).resolve().parent.parent / "references" / "intro_styles.yaml"
    if yaml is None or not reference.is_file():
        return fallback
    try:
        data = yaml.safe_load(reference.read_text(encoding="utf-8")) or {}
        for item in data.get("styles") or []:
            if item.get("id") != style_id:
                continue
            visual = item.get("visual") or {}
            fallback.update({key: str(value).lstrip("#") for key, value in visual.items() if value})
            animation = (item.get("animation") or {}).get("type")
            if animation:
                fallback["animation"] = str(animation)
            break
    except (OSError, TypeError, ValueError):
        pass
    return fallback


def select_lines(person: dict[str, Any], max_lines: int = 4) -> list[str]:
    name = str(person.get("name") or "").strip()
    if not name:
        raise ValueError("person.name is required")
    candidates: list[str] = []
    title = str(person.get("title") or "").strip()
    organization = str(person.get("organization") or "").strip()
    if title and organization:
        candidates.append(f"{title} · {organization}")
    elif title or organization:
        candidates.append(title or organization)
    for field in ("roles", "education", "experience"):
        values = person.get(field) or []
        if isinstance(values, list):
            candidates.extend(str(value).strip() for value in values if str(value).strip())
    tagline = str(person.get("tagline") or "").strip()
    if tagline:
        candidates.append(tagline)
    deduplicated = list(dict.fromkeys(candidates))
    if not deduplicated:
        raise ValueError("At least one supporting identity field is required")
    return [name, *deduplicated[: max(1, max_lines - 1)]]


def resolve_position(position: str, person_position: str | None) -> tuple[str, bool]:
    if position != "auto":
        return position, False
    opposite = {"left": "right", "right": "left", "bottom_left": "bottom_right", "bottom_right": "bottom_left"}
    if person_position in opposite:
        return opposite[person_position], False
    return "bottom_left", True


def draw_filters(
    lines: list[str],
    font: Path,
    position: str,
    width: int,
    height: int,
    duration: float,
    style: dict[str, str] | None = None,
    animation: str | None = None,
) -> str:
    style = style or DEFAULT_STYLE["professional"]
    animation = animation or style.get("animation") or "fade_slide"
    left = position in {"left", "bottom_left"}
    bottom = position in {"bottom_left", "bottom_right"}
    x = "80" if left else "w-tw-80"
    base_y = height - 360 if bottom else 240
    line_offsets = [0, 88, 150, 212]
    filters = []
    intro = min(0.45, max(0.15, duration / 3))
    fade_start = max(intro, duration - 0.5)
    panel_x = "40" if left else "w-780"
    panel_y = str(height - 430 if bottom else 160)
    panel_height = 380
    panel_color = style.get("panel", "0B1220")
    accent = style.get("accent", "FFFFFF")
    text_color = style.get("text", "FFFFFF")
    filters.append(
        f"drawbox=x={panel_x}:y={panel_y}:w=740:h={panel_height}:color={panel_color}@0.78:t=fill:"
        f"enable='between(t,0,{duration})'"
    )
    filters.append(
        f"drawbox=x={panel_x}:y={panel_y}:w=8:h={panel_height}:color={accent}@0.95:t=fill:"
        f"enable='between(t,0,{duration})'"
    )
    if animation == "scan_fade":
        filters.append(
            f"drawbox=x=0:y='if(lt(t,{intro}),h*(t/{intro}),-20)':w=iw:h=6:color={accent}@0.8:t=fill:"
            f"enable='between(t,0,{intro})'"
        )
    for index, line in enumerate(lines):
        size = 64 if index == 0 else 34
        offset = line_offsets[index] if index < len(line_offsets) else line_offsets[-1] + (index - len(line_offsets) + 1) * 62
        static_y = base_y + offset
        lift = 28 if animation in {"fade_slide", "scan_fade", "rise"} else 0
        y = f"{static_y}+if(lt(t,{intro}),{lift}*(1-t/{intro}),0)"
        filters.append(
            "drawtext="
            f"fontfile='{escape_filter_path(font)}':"
            f"text='{escape_filter_text(line)}':expansion=none:fontcolor={accent if index == 0 else text_color}:fontsize={size}:"
            f"x={x}:y='{y}':borderw=1:bordercolor=black@0.25:"
            f"alpha='if(lt(t,{intro}),t/{intro},if(lt(t,{fade_start}),1,max(0,({duration}-t)/0.5)))'"
        )
    return ",".join(filters)


def resolve_assets(args: argparse.Namespace, person: dict[str, Any]) -> dict[str, Path | None]:
    assets = person.get("assets") if isinstance(person.get("assets"), dict) else {}
    logos = person.get("logos") or assets.get("logos") or []
    logo_value = getattr(args, "logo_file", None) or (logos[0] if logos else None)
    values = {
        "avatar": getattr(args, "avatar", None) or assets.get("avatar"),
        "logo": logo_value,
        "background": getattr(args, "background_image", None) or assets.get("background"),
        "font": getattr(args, "font", None) or assets.get("font"),
        "card": getattr(args, "card_image", None) or assets.get("card") or assets.get("card_image"),
    }
    resolved: dict[str, Path | None] = {}
    for key, value in values.items():
        if not value:
            resolved[key] = None
            continue
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(f"{key} asset not found: {path}")
        resolved[key] = path
    return resolved


def _asset_overlay(
    current: str,
    asset_label: str,
    asset_index: int,
    position: str,
    duration: float,
    kind: str,
) -> tuple[str, str]:
    if kind == "avatar":
        scale = "scale=260:260:force_original_aspect_ratio=decrease,pad=260:260:(ow-iw)/2:(oh-ih)/2:color=00000000,format=rgba"
        x = "w-340" if position in {"left", "bottom_left"} else "80"
        y = "120"
    else:
        scale = "scale=220:-1:force_original_aspect_ratio=decrease,format=rgba"
        x = "w-300" if position in {"left", "bottom_left"} else "80"
        y = "70"
    prepared = f"[{asset_index}:v]{scale}[{asset_label}]"
    output = f"[{asset_label}]"
    merged = (
        f"{current}{output}overlay=x={x}:y={y}:eof_action=pass:shortest=1:"
        f"enable='between(t,0,{duration})'[next_{asset_label}]"
    )
    return prepared, (merged, f"[next_{asset_label}]")


def render(args: argparse.Namespace, lines: list[str], resolved_position: str) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required")
    font = find_cjk_font(getattr(args, "font", None))
    if not font:
        raise RuntimeError("A font with Chinese glyphs is required; pass --font")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    style = load_style(getattr(args, "style", "professional"))
    assets = getattr(args, "assets", {}) or {}
    source_video = getattr(args, "source_video", None)
    background_image = assets.get("background")
    avatar = assets.get("avatar")
    logo = assets.get("logo")
    card = assets.get("card")

    command = ["ffmpeg", "-v", "error", "-y"]
    if source_video:
        if not Path(source_video).is_file():
            raise FileNotFoundError(f"Source video not found: {source_video}")
        command += ["-i", str(source_video)]
    elif background_image:
        command += ["-loop", "1", "-i", str(background_image)]
    else:
        background = f"color=c={style.get('background', args.background)}:s={args.width}x{args.height}:r={args.fps}:d={args.duration}"
        command += ["-f", "lavfi", "-i", background]

    asset_indices: dict[str, int] = {}
    for key, path in (("avatar", avatar), ("logo", logo), ("card", card)):
        if path:
            asset_indices[key] = len(asset_indices) + 1
            command += ["-loop", "1", "-i", str(path)]

    if source_video:
        base = f"scale={args.width}:{args.height}:force_original_aspect_ratio=decrease,pad={args.width}:{args.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={args.fps},format=yuv420p"
    else:
        base = f"scale={args.width}:{args.height}:force_original_aspect_ratio=increase,crop={args.width}:{args.height},setsar=1,fps={args.fps},format=yuv420p"
    filter_parts = [f"[0:v]{base}[base0]"]
    current = "[base0]"
    for key in ("avatar", "logo", "card"):
        if key not in asset_indices:
            continue
        if key == "card":
            card_index = asset_indices[key]
            filter_parts.append(
                f"[{card_index}:v]scale=960:-1:force_original_aspect_ratio=decrease,format=rgba[card]"
            )
            filter_parts.append(
                f"{current}[card]overlay=x=(W-w)/2:y=40:eof_action=pass:shortest=1:"
                f"enable='between(t,0,{args.duration})'[next_card]"
            )
            current = "[next_card]"
            continue
        prepared, (merged, next_label) = _asset_overlay(current, key, asset_indices[key], resolved_position, args.duration, key)
        filter_parts.append(prepared)
        filter_parts.append(merged)
        current = next_label
    if "card" in asset_indices:
        filter_parts.append(f"{current}null[vout]")
    else:
        text_filters = draw_filters(
            lines,
            font,
            resolved_position,
            args.width,
            args.height,
            args.duration,
            style,
            getattr(args, "animation", None),
        )
        filter_parts.append(f"{current}{text_filters}[vout]")
    command += ["-filter_complex", ";".join(filter_parts), "-map", "[vout]"]
    if source_video:
        command += ["-map", "0:a?", "-c:a", "aac"]
    else:
        command += ["-an", "-t", str(args.duration)]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(args.output)]
    subprocess.run(command, check=True)
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise RuntimeError("Render did not produce a non-empty file")
    probe(args.output)
    return args.output


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a concise person introduction card")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--person", help="Person JSON object")
    source.add_argument("--person-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-video", type=Path, help="Optional video that receives the intro overlay")
    parser.add_argument("--avatar", type=Path, help="Optional avatar image")
    parser.add_argument("--logo-file", type=Path, help="Optional logo image")
    parser.add_argument("--background-image", type=Path, help="Optional branded background image")
    parser.add_argument("--card-image", type=Path, help="Optional complete person card image to display")
    parser.add_argument("--duration", type=float, default=4.0)
    parser.add_argument("--position", choices=["left", "right", "bottom_left", "bottom_right", "auto"], default="auto")
    parser.add_argument("--person-position", choices=["left", "right", "bottom_left", "bottom_right"])
    parser.add_argument("--animation", default="fade_slide")
    parser.add_argument("--style", default="professional")
    parser.add_argument("--logo", action="store_true", help="Enable logo metadata; use --logo-file to render an image")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--background", default="#111827")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    person = json.loads(args.person if args.person is not None else args.person_file.read_text(encoding="utf-8"))
    try:
        lines = select_lines(person)
    except ValueError as exc:
        print_json(response(status="error", state="content_selection", message="Person intro data is invalid.", errors=[{"code": "invalid_person", "message": str(exc), "recoverable": True}]))
        return 2
    position, fallback = resolve_position(args.position, args.person_position)
    try:
        assets = resolve_assets(args, person)
    except FileNotFoundError as exc:
        print_json(response(status="error", state="rendering", message="Person intro asset is invalid.", errors=[{"code": "missing_asset", "message": str(exc), "recoverable": True}]))
        return 2
    args.assets = assets
    args.font = assets.get("font") or args.font
    spec = {"lines": lines, "duration": args.duration, "position": position, "position_fallback": fallback, "animation": args.animation, "style": args.style, "logo": args.logo or bool(assets.get("logo")), "assets": {key: str(value) if value else None for key, value in assets.items()}, "source_video": str(args.source_video) if args.source_video else None, "width": args.width, "height": args.height, "fps": args.fps}
    if args.plan_only:
        print_json(response(status="partial", state="rendering", message="Person intro plan created; rendering not executed.", data={"person_intro": spec, "skipped": ["video_render"]}, next_actions=["render_person_intro", "review_person_intro"]))
        return 0
    try:
        output = render(args, lines, position)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print_json(response(status="partial", state="rendering", message="Person intro content is ready but rendering failed.", data={"person_intro": spec}, errors=[{"code": "render_failed", "message": str(exc), "recoverable": True}], next_actions=["check_ffmpeg_or_font", "retry_person_intro_render"]))
        return 2
    video_key = "final" if args.source_video else "person_intro"
    next_actions = ["review_final_video", "export_video"] if args.source_video else ["compose_video", "review_person_intro"]
    print_json(response(status="success", state="completed", message="Person intro rendered.", data={"person_intro": spec, "video": {video_key: str(output)}}, files=[{"path": str(output), "kind": "video", "mime_type": "video/mp4", "exists": True}], next_actions=next_actions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
