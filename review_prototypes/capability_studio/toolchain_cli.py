from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .integration_compiler import SceneBuildRequest, ToolchainIntegrationCompiler
from .scene_router import RunnerProfile, SceneIntent, SceneKind
from .toolchain_catalog import TOOL_BY_ID, ToolchainDoctor, optional_secret_names, required_secret_names


def _dump(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def catalog() -> list[dict[str, object]]:
    return [asdict(TOOL_BY_ID[key]) for key in sorted(TOOL_BY_ID)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Review-only free toolchain planner")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    sub.add_parser("doctor")
    sub.add_parser("keys")
    route = sub.add_parser("route")
    route.add_argument("--scene-id", default="scene_1")
    route.add_argument("--kind", choices=[kind.value for kind in SceneKind], required=True)
    route.add_argument("--duration", type=float, default=5.0)
    route.add_argument("--rights-verified", action="store_true")
    route.add_argument("--allow-heavy", action="store_true")
    route.add_argument("--allow-gpu", action="store_true")
    plan = sub.add_parser("plan")
    plan.add_argument("--spec", required=True, help="JSON scene-build request")
    args = parser.parse_args()

    if args.command == "catalog":
        _dump(catalog())
    elif args.command == "doctor":
        _dump(ToolchainDoctor().as_dicts())
    elif args.command == "keys":
        _dump({"required": required_secret_names(), "optional": optional_secret_names()})
    elif args.command == "route":
        intent = SceneIntent(args.scene_id, SceneKind(args.kind), args.duration, rights_verified=args.rights_verified)
        runner = RunnerProfile.all_planned(allow_heavy=args.allow_heavy, allow_gpu=args.allow_gpu)
        _dump(asdict(ToolchainIntegrationCompiler().router.route(intent, runner)))
    elif args.command == "plan":
        payload = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        intent_payload = payload.pop("intent")
        intent_payload["kind"] = SceneKind(intent_payload["kind"])
        request = SceneBuildRequest(intent=SceneIntent(**intent_payload), **payload)
        runner = RunnerProfile.all_planned(allow_heavy=True, allow_gpu=True)
        compiled = ToolchainIntegrationCompiler().compile(request, runner)
        _dump({"decision": asdict(compiled.decision), "plans": [asdict(item) for item in compiled.plans], "artifacts": dict(compiled.artifacts), "production_wiring": compiled.production_wiring})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
