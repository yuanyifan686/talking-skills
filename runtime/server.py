from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.executor import SkillExecutor
from runtime.pipeline import PipelineRunner
from runtime.registry import SkillRegistry
from shared.utils.env import load_project_env


class RuntimeApplication:
    def __init__(self) -> None:
        self.registry = SkillRegistry()
        self.executor = SkillExecutor(self.registry)
        self.pipeline = PipelineRunner(self.executor)

    def get(self, path: str) -> tuple[int, dict[str, Any]]:
        if path == "/health":
            provider = self.executor.provider
            return 200, {
                "status": "ok",
                "service": "talking-skills-runtime",
                "provider": provider.__class__.__name__,
                "provider_configured": bool(getattr(provider, "configured", True)),
                "skills": len(self.registry.discover()),
            }
        if path == "/skills":
            return 200, {"skills": self.registry.discover()}
        if path.startswith("/catalog/"):
            try:
                return 200, self.registry.catalog(path.removeprefix("/catalog/"))
            except (KeyError, ValueError) as exc:
                return 404, {"error": str(exc)}
        return 404, {"error": "Not found"}

    def post(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if path == "/invoke":
            result = self.executor.invoke(payload)
            return (400 if result.get("status") == "error" else 200), result
        if path.startswith("/pipelines/"):
            pipeline_id = path.removeprefix("/pipelines/")
            result = self.pipeline.run(
                pipeline_id,
                input_data=payload.get("input") or {},
                context=payload.get("context"),
                request_id=payload.get("request_id"),
            )
            return (400 if result.get("status") == "error" else 200), result
        return 404, {"error": "Not found"}


def make_handler(application: RuntimeApplication):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TalkingSkillsRuntime/1.0"

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(204, {})

        def do_GET(self) -> None:  # noqa: N802
            status, payload = application.get(urlparse(self.path).path)
            self._send(status, payload)

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._send(400, {"error": f"Invalid JSON: {exc}"})
                return
            status, result = application.post(urlparse(self.path).path, payload)
            self._send(status, result)

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("[talking-skills] " + format % args + "\n")

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Talking Skills local HTTP runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_project_env()
    application = RuntimeApplication()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(application))
    print(f"Talking Skills Runtime listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
