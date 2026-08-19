from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.executor import SkillExecutor
from runtime.pipeline import PipelineRunner
from runtime.registry import SkillRegistry
from shared.utils.env import load_project_env
from shared.utils.protocol import load_data, print_json


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Agent-agnostic Talking Skills runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("discover")
    catalog = commands.add_parser("catalog")
    catalog.add_argument("skill")
    invoke = commands.add_parser("invoke")
    invoke.add_argument("invocation", type=Path)
    pipeline = commands.add_parser("pipeline")
    pipeline.add_argument("input", type=Path)
    pipeline.add_argument("--id", default="short-video")
    args = parser.parse_args()

    registry = SkillRegistry()
    if args.command == "discover":
        print_json({"skills": registry.discover()})
        return 0
    if args.command == "catalog":
        print_json(registry.catalog(args.skill))
        return 0

    executor = SkillExecutor(registry)
    if args.command == "invoke":
        result = executor.invoke(load_data(args.invocation))
    else:
        payload = load_data(args.input)
        result = PipelineRunner(executor).run(
            args.id,
            input_data=payload.get("input") or payload,
            context=payload.get("context"),
            request_id=payload.get("request_id"),
        )
    print_json(result)
    return 0 if result.get("status") not in {"error", "awaiting_user"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
