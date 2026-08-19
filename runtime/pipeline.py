from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from shared.utils.protocol import load_data, response

from .registry import ROOT


def _get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _condition(expression: str | None, context: dict[str, Any]) -> bool:
    if not expression:
        return True
    match = re.fullmatch(r"\s*([a-zA-Z0-9_.]+)\s*(?:(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?))?\s*", expression)
    if not match:
        raise ValueError(f"Unsupported pipeline condition: {expression}")
    value = _get_path(context, match.group(1))
    operator = match.group(2)
    if not operator:
        return bool(value)
    try:
        left = float(value)
        right = float(match.group(3))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Pipeline condition is not numeric: {expression}") from exc
    return {
        "<": left < right,
        "<=": left <= right,
        ">": left > right,
        ">=": left >= right,
        "==": left == right,
        "!=": left != right,
    }[operator]


class PipelineRunner:
    """Execute declarative Skill steps using only the universal protocol."""

    def __init__(self, executor: Any, root: str | Path = ROOT) -> None:
        self.executor = executor
        self.root = Path(root).resolve()

    def run(
        self,
        pipeline_id: str = "short-video",
        *,
        input_data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        source = self.root / "config" / "pipelines" / f"{pipeline_id}.yaml"
        if not source.is_file():
            return response(
                status="error",
                state="pipeline_validation",
                message="Pipeline 不存在。",
                errors=[{"code": "unknown_pipeline", "message": pipeline_id, "recoverable": True}],
                request_id=request_id,
            )
        definition = load_data(source)
        invocation_input = deepcopy(input_data or {})
        pipeline_context = deepcopy(context or {"project": {}})
        pipeline_context.setdefault("protocol_version", "1.0.0")
        project = pipeline_context.setdefault("project", {})
        for key in ("topic", "platform", "person"):
            if key in invocation_input:
                project[key] = deepcopy(invocation_input[key])
        if isinstance(invocation_input.get("video"), dict):
            project["video"] = deepcopy(invocation_input["video"])

        trace: list[dict[str, Any]] = []
        partial = False
        last_data: dict[str, Any] = {}
        for step in definition.get("steps") or []:
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("id") or "step")
            try:
                should_run = _condition(step.get("when"), pipeline_context)
            except ValueError as exc:
                return response(
                    status="error",
                    state="pipeline_validation",
                    message="Pipeline 条件无效。",
                    data={"trace": trace},
                    errors=[{"code": "invalid_condition", "message": str(exc), "recoverable": False}],
                    context=pipeline_context,
                    request_id=request_id,
                )
            if not should_run:
                trace.append({"step": step_id, "status": "skipped", "reason": step.get("when")})
                continue

            step_input = {**invocation_input, **(step.get("input") or {})}
            result = self.executor.invoke(
                {
                    "protocol_version": "1.0.0",
                    "request_id": f"{request_id}:{step_id}" if request_id else step_id,
                    "skill": step.get("skill"),
                    "action": step.get("action"),
                    "mode": invocation_input.get("mode", "auto"),
                    "input": step_input,
                    "context": pipeline_context,
                }
            )
            trace.append(
                {
                    "step": step_id,
                    "skill": step.get("skill"),
                    "action": step.get("action"),
                    "status": result.get("status"),
                    "state": result.get("state"),
                    "message": result.get("message"),
                }
            )
            if isinstance(result.get("context"), dict):
                pipeline_context = result["context"]
            if isinstance(result.get("data"), dict):
                last_data = result["data"]
            if result.get("status") == "partial":
                partial = True
            if result.get("status") in {"error", "awaiting_user"}:
                return response(
                    status=result["status"],
                    state=f"pipeline:{step_id}",
                    message=f"Pipeline 在 {step_id} 步停止：{result.get('message', '')}",
                    data={"trace": trace, "step_result": result},
                    errors=result.get("errors") or [],
                    context=pipeline_context,
                    request_id=request_id,
                )

        return response(
            status="partial" if partial else "success",
            state="completed",
            message="短视频 Skill Pipeline 已执行完成。" if not partial else "文本 Pipeline 已完成，部分媒体步骤按能力降级。",
            data={"pipeline": definition.get("id"), "trace": trace, "last_result": last_data},
            next_actions=["review_pipeline_output", "complete_skipped_media_steps"] if partial else ["review_pipeline_output", "export_or_publish"],
            context=pipeline_context,
            request_id=request_id,
        )
