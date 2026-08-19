from __future__ import annotations

import re
from dataclasses import dataclass


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ALNUM_RE = re.compile(r"[A-Za-z0-9]")
_SPACE_RE = re.compile(r"\s+")

# These are intentionally conservative, common spoken fillers and compactable
# phrases. The layout layer must never invent a new claim while shortening text.
_COMPRESSION_RULES: tuple[tuple[str, str], ...] = (
    ("为什么现在AI时代", "为什么AI时代"),
    ("为什么在AI时代", "为什么AI时代"),
    ("AI时代这个", "AI时代"),
    ("工具很多但是没什么用", "工具多却没用"),
    ("工具很多但没什么用", "工具多却没用"),
    ("越来越多但是越来越没用", "越多越没用"),
    ("越来越多但越来越没用", "越多越没用"),
    ("你有没有发现", "为什么"),
    ("有没有发现", "为什么"),
    ("到底是", ""),
    ("其实", ""),
    ("真的", ""),
    ("这个", ""),
)


class HookLayoutError(ValueError):
    """Raised when hook text cannot fit inside the configured safe area."""


@dataclass(frozen=True)
class HookLayout:
    raw_text: str
    text: str
    lines: tuple[str, ...]
    font_size: int
    line_spacing: int
    box_border: int
    max_width: int
    safe_margin_x: int
    safe_margin_y: int
    compressed: bool
    compression_actions: tuple[str, ...]
    overflow: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "raw_text": self.raw_text,
            "text": self.text,
            "lines": list(self.lines),
            "font_size": self.font_size,
            "line_spacing": self.line_spacing,
            "box_border": self.box_border,
            "max_width": self.max_width,
            "safe_margin_x": self.safe_margin_x,
            "safe_margin_y": self.safe_margin_y,
            "compressed": self.compressed,
            "compression_actions": list(self.compression_actions),
            "overflow": self.overflow,
        }


def visible_char_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def normalize_hook_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized = "\n".join(_SPACE_RE.sub(" ", line).strip() for line in normalized.split("\n"))
    return normalized


def compress_hook_text(text: str, max_chars: int = 25) -> tuple[str, tuple[str, ...]]:
    """Shorten safe filler and common phrases without changing the claim."""

    original = normalize_hook_text(text)
    compact = original
    actions: list[str] = []
    for source, replacement in _COMPRESSION_RULES:
        if visible_char_count(compact) <= max_chars:
            break
        if source in compact:
            compact = compact.replace(source, replacement)
            actions.append(f"{source}->{replacement or '删除'}")

    # A final hard cap is only a last resort for rendering. It is surfaced in
    # metadata so an agent can replace it with a better semantic rewrite.
    if visible_char_count(compact) > max_chars:
        suffix = "？" if "？" in compact or "?" in compact else ""
        units = list(compact.replace("\n", ""))
        keep = max(1, max_chars - len(suffix))
        compact = "".join(units[:keep]).rstrip("，。！？；：、,!?;:") + suffix
        actions.append(f"hard_cap:{max_chars}")

    if compact and not compact.endswith(("？", "?")):
        compact = compact.rstrip("。！!") + "？"
    return compact, tuple(actions)


def _char_width(character: str, font_size: int) -> float:
    if _CJK_RE.fullmatch(character):
        return float(font_size)
    if _ALNUM_RE.fullmatch(character):
        return font_size * 0.58
    if character.isspace():
        return font_size * 0.35
    return font_size * 0.55


def estimate_line_width(text: str, font_size: int) -> int:
    return round(sum(_char_width(character, font_size) for character in text))


def wrap_hook_text(text: str, font_size: int, max_width: int) -> tuple[str, ...]:
    """Wrap by estimated rendered width while preserving explicit line breaks."""

    lines: list[str] = []
    for paragraph in normalize_hook_text(text).split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for character in paragraph:
            candidate = current + character
            if current and estimate_line_width(candidate, font_size) > max_width:
                # Keep punctuation attached to the preceding phrase when possible.
                if character in "，。！？：；、,.!?;:":
                    current += character
                else:
                    lines.append(current)
                    current = character
            else:
                current = candidate
        if current:
            lines.append(current)
    return tuple(lines or ("",))


def fit_hook_layout(
    text: str,
    width: int,
    height: int,
    *,
    max_width_ratio: float = 0.84,
    safe_margin_x: int = 96,
    safe_margin_y: int = 160,
    min_font_size: int = 32,
    max_font_size: int | None = None,
    max_lines: int = 3,
    max_hook_chars: int = 25,
    auto_compress: bool = True,
) -> HookLayout:
    if width <= 0 or height <= 0:
        raise HookLayoutError("Canvas width and height must be positive")
    raw_text = normalize_hook_text(text)
    if not raw_text:
        raise HookLayoutError("Hook text cannot be empty")
    if max_lines <= 0:
        raise HookLayoutError("max_lines must be positive")

    effective_margin_x = min(max(12, safe_margin_x), max(12, width // 8))
    effective_margin_y = min(max(12, safe_margin_y), max(12, height // 8))
    requested_max_width = round(width * max_width_ratio)
    content_width = min(requested_max_width, width - (2 * effective_margin_x))
    max_font = max(12, max_font_size or round(width * 0.055))
    min_font = max(12, min(min_font_size, max_font))

    if auto_compress:
        display_text, compression_actions = compress_hook_text(raw_text, max_hook_chars)
    else:
        display_text, compression_actions = raw_text, ()

    for font_size in range(max_font, min_font - 1, -1):
        box_border = max(8, round(font_size * 0.35))
        text_width_limit = max(1, content_width - (2 * box_border))
        lines = wrap_hook_text(display_text, font_size, text_width_limit)
        line_spacing = max(3, round(font_size * 0.24))
        text_height = (len(lines) * font_size) + (max(0, len(lines) - 1) * line_spacing)
        measured_width = max((estimate_line_width(line, font_size) for line in lines), default=0)
        available_height = height - (2 * effective_margin_y) - (2 * box_border)
        if len(lines) <= max_lines and measured_width <= text_width_limit and text_height <= available_height:
            return HookLayout(
                raw_text=raw_text,
                text="\n".join(lines),
                lines=lines,
                font_size=font_size,
                line_spacing=line_spacing,
                box_border=box_border,
                max_width=text_width_limit,
                safe_margin_x=effective_margin_x,
                safe_margin_y=effective_margin_y,
                compressed=bool(compression_actions),
                compression_actions=compression_actions,
                overflow=False,
            )

    raise HookLayoutError(
        f"Hook text does not fit safely: canvas={width}x{height}, "
        f"max_lines={max_lines}, min_font_size={min_font}"
    )
