from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
import shutil

from .config import FREE_STACK_OPTIONAL_SECRETS, LOCAL_TOOLS
from .free_pipeline import FreeFirstPipelinePlanner, FreePipelineProject


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def cmd_plan(args: argparse.Namespace) -> int:
    blueprint = FreeFirstPipelinePlanner().build(FreePipelineProject(args.topic, args.channel, args.format, args.duration, args.allow_authorized_web_video))
    _json(asdict(blueprint))
    return 0


def cmd_keys(_: argparse.Namespace) -> int:
    _json({"required_for_new_free_stack": [], "optional_free_api_keys": FREE_STACK_OPTIONAL_SECRETS, "existing_useful_keys": ["YOUTUBE_API_KEY", "PEXELS_API_KEY"]})
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    module_names = {"pillow": "PIL", "moviepy": "moviepy", "opentimelineio": "opentimelineio", "clip": "transformers", "mediapipe": "mediapipe", "sam2": "sam2"}
    report = {}
    for tool_id, requirement in LOCAL_TOOLS.items():
        if tool_id in module_names:
            available = importlib.util.find_spec(module_names[tool_id]) is not None
        else:
            available = shutil.which(requirement.executable) is not None
        report[tool_id] = {"available": available, "executable": requirement.executable, "optional": requirement.optional, "install_hint": requirement.install_hint}
    _json({"review_only": True, "production_wiring": False, "tools": report})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review-only free capability stack")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--topic", required=True)
    plan.add_argument("--channel", required=True)
    plan.add_argument("--format", default="narrated_explainer")
    plan.add_argument("--duration", type=int, default=45)
    plan.add_argument("--allow-authorized-web-video", action="store_true")
    plan.set_defaults(func=cmd_plan)
    keys = subparsers.add_parser("keys")
    keys.set_defaults(func=cmd_keys)
    doctor = subparsers.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
