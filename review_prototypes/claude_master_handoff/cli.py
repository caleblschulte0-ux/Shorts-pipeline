from __future__ import annotations

import argparse
import json
from pathlib import Path

from .catalog import build_master_handoff
from .validator import manifest_as_dict, validate_master_handoff, write_json


def _summary() -> dict:
    handoff = build_master_handoff()
    return {
        "schema_version": handoff.schema_version,
        "branch": handoff.branch,
        "pull_request": handoff.pull_request,
        "status": handoff.status,
        "components": len(handoff.components),
        "adoption_phases": len(handoff.phases),
        "risks": len(handoff.risks),
        "sacred_guards": len(handoff.sacred_guards),
        "decision_routes": handoff.decision_routes,
        "first_session_commands": list(handoff.first_session_commands),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and inspect the Claude master handoff.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary")

    validate = sub.add_parser("validate")
    validate.add_argument("--repo", type=Path, default=None)
    validate.add_argument("--out", type=Path, default=None)

    emit = sub.add_parser("emit-manifest")
    emit.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "summary":
        print(json.dumps(_summary(), indent=2, sort_keys=True))
        return 0
    if args.command == "validate":
        report = validate_master_handoff(args.repo)
        if args.out:
            write_json(args.out, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report.ok else 2
    if args.command == "emit-manifest":
        write_json(args.out, manifest_as_dict())
        print(args.out)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
