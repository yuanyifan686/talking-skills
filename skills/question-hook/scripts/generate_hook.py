from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.protocol import print_json, response


def chinese_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def infer_topic(script: str, explicit_topic: str | None) -> str:
    if explicit_topic and explicit_topic.strip():
        return explicit_topic.strip().rstrip("？?！!。")
    if re.search(r"AI.*工具|工具.*AI", script, re.I):
        return "AI工具"
    sentence = re.split(r"[。！？!?，,]", script.strip())[0]
    cleaned = re.sub(r"^(很多人|真正|其实|你会发现|我觉得)", "", sentence).strip()
    return cleaned[:10] or "这件事"


def build_hook(script: str, hook_type: str = "auto", topic: str | None = None) -> dict[str, object]:
    if not script.strip():
        raise ValueError("script cannot be empty")
    subject = infer_topic(script, topic)
    selected = hook_type
    if hook_type == "auto":
        selected = "cognitive_conflict" if re.search(r"不是|并不是|反而|真正", script) else "why"
    if subject == "AI工具" and selected in {"cognitive_conflict", "contrast"}:
        text = "AI工具用得越多，就真的越厉害吗？"
    else:
        formulas = {
            "why": f"为什么{subject}，结果总和想象中不一样？",
            "contrast": f"{subject}越多，结果就真的越好吗？",
            "benefit": f"普通人怎样做好{subject}，少走弯路？",
            "trend": f"未来{subject}，真正拉开差距的是什么？",
            "identity": f"同样面对{subject}，为什么结果完全不同？",
            "either_or": f"面对{subject}，你会坚持还是放弃？",
            "result_suspense": f"把{subject}做到极致，结果真的更好吗？",
            "cognitive_conflict": f"关于{subject}，你相信的可能一直是错的吗？",
        }
        text = formulas.get(selected, formulas["why"])
    if chinese_count(text) > 25:
        subject = subject[:6]
        text = f"为什么{subject}，结果反而不一样？"
    if chinese_count(text) < 8:
        text = f"为什么{subject}总和想象中不一样？"
    return {
        "text": text,
        "type": selected,
        "estimated_duration": round(chinese_count(text) / 4.5, 1),
        "relation_to_script": "direct",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an agent-neutral question hook")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--script")
    source.add_argument("--script-file", type=Path)
    parser.add_argument("--topic")
    parser.add_argument("--type", default="auto", choices=["auto", "why", "contrast", "benefit", "trend", "identity", "either_or", "result_suspense", "cognitive_conflict"])
    args = parser.parse_args()
    script = args.script if args.script is not None else args.script_file.read_text(encoding="utf-8")
    hook = build_hook(script, args.type, args.topic)
    print_json(response(status="success", state="completed", message="Question hook generated.", data={"hook": hook}, next_actions=["synthesize_hook", "compose_video"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
