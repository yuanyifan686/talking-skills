from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_data(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("YAML input requires PyYAML; JSON remains available without it") from exc
    value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {source}")
    return value


def response(
    *,
    status: str,
    state: str,
    message: str,
    data: dict[str, Any] | None = None,
    files: list[dict[str, Any]] | None = None,
    next_actions: list[Any] | None = None,
    next_step: str | None = None,
    errors: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    resolved_actions = next_actions or []
    if next_step is None:
        next_step = human_next_step(status, resolved_actions)
    result: dict[str, Any] = {
        "protocol_version": "1.0.0",
        "request_id": request_id,
        "status": status,
        "state": state,
        "message": message,
        "data": data or {},
        "files": files or [],
        "next_actions": resolved_actions,
        "next_step": next_step,
        "errors": errors or [],
    }
    if context is not None:
        result["context"] = context
    return result


def human_next_step(status: str, actions: list[Any]) -> str:
    """Create a short user-facing handoff while preserving machine actions."""
    if actions:
        first = actions[0]
        if isinstance(first, dict):
            skill = first.get("skill")
            action = first.get("action")
            reason = first.get("reason")
            if skill and action:
                suffix = f"（{reason}）" if reason else ""
                return f"下一步：调用 {skill} 的 {action}{suffix}。"
        if isinstance(first, str):
            return f"下一步：执行 {first}。"
    if status == "awaiting_user":
        return "下一步：根据提示补充必要信息或完成选择。"
    if status == "partial":
        return "下一步：补齐缺失的能力或素材后继续执行。"
    if status == "error":
        return "下一步：根据错误信息修正输入后重试。"
    return "下一步：检查当前输出；如需继续，请提交下一项任务。"


def print_json(value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(payload.encode("utf-8"))
        sys.stdout.buffer.flush()
    else:
        print(payload, end="")
