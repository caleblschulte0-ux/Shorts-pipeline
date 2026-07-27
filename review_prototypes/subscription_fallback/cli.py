from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from .buffer_manager import BufferManager
from .fallback_orchestrator import FallbackOrchestrator
from .fixtures import approve, sample_request


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def demo(workspace: Path) -> int:
    orchestrator = FallbackOrchestrator(workspace)
    result = orchestrator.build_into_buffer(sample_request(), approval=approve)
    claim = orchestrator.claim_next_upload("daily-data")
    report = BufferManager().report("daily-data", orchestrator.queue.items())
    emit({
        "safety": "review-only; posting did not call an AI provider",
        "generation": asdict(result),
        "posting_claim": asdict(claim),
        "buffer": asdict(report),
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    demo_parser = sub.add_parser("demo")
    demo_parser.add_argument("--workspace")
    sub.add_parser("keys")
    queue = sub.add_parser("queue-status")
    queue.add_argument("--workspace", required=True)
    queue.add_argument("--channel", required=True)
    args = parser.parse_args()
    if args.command == "keys":
        emit({
            "required": [],
            "optional": ["GEMINI_API_KEY", "ANTHROPIC_API_KEY"],
            "note": "A Claude consumer subscription is not a GitHub Actions credential and is never required by the posting job.",
        })
        return 0
    if args.command == "demo":
        if args.workspace:
            return demo(Path(args.workspace))
        with tempfile.TemporaryDirectory() as tmp:
            return demo(Path(tmp))
    orchestrator = FallbackOrchestrator(Path(args.workspace))
    emit(asdict(BufferManager().report(args.channel, orchestrator.queue.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
