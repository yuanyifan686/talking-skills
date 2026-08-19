from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.tts import TTSRequest, TTSUnavailable, get_provider
from shared.utils.protocol import print_json, response


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize hook audio through a provider-neutral TTS interface")
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--voice")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    plan = {"provider": args.provider, "voice": args.voice, "speed": args.speed, "sample_rate": args.sample_rate, "output": str(args.output)}
    if args.plan_only:
        print_json(response(status="partial", state="tts", message="TTS plan created; synthesis not executed.", data={"tts": plan, "skipped": ["tts_execution"]}, next_actions=["synthesize_tts", "compose_video"]))
        return 0
    try:
        result = get_provider(args.provider).synthesize(TTSRequest(args.text, args.output, args.voice, args.speed, args.sample_rate))
    except (TTSUnavailable, ValueError, OSError) as exc:
        print_json(response(status="partial", state="tts", message="TTS not executed.", data={"tts": plan, "skipped": ["tts_execution"]}, errors=[{"code": "tts_unavailable", "message": str(exc), "recoverable": True}], next_actions=["check_tts_provider", "retry_tts"]))
        return 2
    print_json(response(status="success", state="intro_render", message="Hook audio synthesized.", data={"tts": {**plan, "bytes": result.bytes_written, "content_type": result.content_type}}, files=[{"path": str(result.output_path), "kind": "audio", "mime_type": result.content_type, "exists": True}], next_actions=["compose_video"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
