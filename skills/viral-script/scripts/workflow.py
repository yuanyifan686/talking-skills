from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.protocol import print_json, response


TITLE_BUILDERS = (
    ("counter_intuitive", lambda topic: f"为什么我越来越不建议你盲目追求{topic}？"),
    ("cognitive_conflict", lambda topic: f"真正决定{topic}结果的，可能不是努力"),
    ("benefit_conflict", lambda topic: f"普通人做好{topic}，最该抓住哪一步？"),
    ("identity_conflict", lambda topic: f"同样面对{topic}，为什么有人越走越顺？"),
    ("trend_judgment", lambda topic: f"未来围绕{topic}，真正拉开差距的是什么？"),
    ("result_suspense", lambda topic: f"把{topic}做到极致以后，结果真的更好吗？"),
)


def clean_topic(value: Any) -> str:
    return re.sub(r"[？?！!。]+$", "", str(value or "").strip())


def title_response(invocation: dict[str, Any]) -> dict[str, Any]:
    input_data = invocation.get("input") or {}
    context = invocation.get("context") or {}
    topic = clean_topic(input_data.get("topic") or context.get("project", {}).get("topic"))
    if not topic:
        return response(
            status="awaiting_user",
            state="topic",
            message="请提供一个口播主题。",
            errors=[{"code": "missing_topic", "message": "Topic is required", "recoverable": True}],
        )
    titles = [{"index": index, "text": builder(topic), "type": kind} for index, (kind, builder) in enumerate(TITLE_BUILDERS, 1)]
    return response(
        status="awaiting_user",
        state="title_selection",
        message="已生成 6 个标题，请选择一个，或明确授权 Agent 代选。",
        data={"topic": topic, "titles": titles},
        next_actions=[{"skill": "viral-script", "action": "continue", "reason": "select_title"}],
        context={**context, "project": {**context.get("project", {}), "topic": topic}},
        request_id=invocation.get("request_id"),
    )


def continue_response(invocation: dict[str, Any]) -> dict[str, Any]:
    state = invocation.get("state")
    input_data = invocation.get("input") or {}
    if state == "title_selection":
        selected = input_data.get("selected_title")
        delegated = bool(input_data.get("agent_select"))
        if selected is None and not delegated:
            return response(status="awaiting_user", state=state, message="请选标题，或授权 Agent 代选。")
        return response(
            status="awaiting_user",
            state="style_selection",
            message="标题已确认，请选择口播风格，或授权 Agent 代选。",
            data={"selected_title": selected or 1, "selection_source": "agent" if delegated else "user"},
            next_actions=[{"skill": "viral-script", "action": "continue", "reason": "select_style"}],
            request_id=invocation.get("request_id"),
        )
    if state == "style_selection":
        style = input_data.get("selected_style")
        delegated = bool(input_data.get("agent_select"))
        if not style and not delegated:
            return response(status="awaiting_user", state=state, message="请选择风格，或授权 Agent 代选。")
        return response(
            status="partial",
            state="script_generation",
            message="选择已完整，可由执行 Agent 依据 SKILL.md 生成正文。",
            data={"selected_style": style or "natural_chat", "selection_source": "agent" if delegated else "user"},
            next_actions=[{"skill": "viral-script", "action": "continue", "reason": "generate_script_with_llm"}],
            request_id=invocation.get("request_id"),
        )
    return response(
        status="error",
        state=str(state or "unknown"),
        message="不支持的继续状态。",
        errors=[{"code": "invalid_state", "message": f"Cannot continue from {state}", "recoverable": True}],
    )


def execute(invocation: dict[str, Any]) -> dict[str, Any]:
    action = invocation.get("action")
    if action == "generate":
        return title_response(invocation)
    if action == "continue":
        return continue_response(invocation)
    return response(
        status="error",
        state="invalid_action",
        message="此确定性工作流脚本只处理 generate 和 continue。",
        errors=[{"code": "invalid_action", "message": str(action), "recoverable": False}],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic viral-script state transitions")
    parser.add_argument("invocation", help="Invocation JSON string or path")
    args = parser.parse_args()
    candidate = Path(args.invocation)
    payload = json.loads(candidate.read_text(encoding="utf-8") if candidate.is_file() else args.invocation)
    print_json(execute(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
