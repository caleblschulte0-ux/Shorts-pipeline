from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .config import LOCAL_TOOLS, PROVIDERS, secret_status
from .creative import CandidateStudio, GlobalIdeaRouter
from .diagnostics import CapabilityTruthReport
from .fixtures import audience_signals, channels, competitor_observations, idea
from .registry import default_registry
from .research import CommentMiner, CompetitorAnalyzer


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def cmd_demo(_: argparse.Namespace) -> int:
    registry = default_registry()
    candidate_set = CandidateStudio().create("Why printers reject full cartridges", subject="Your printer", fact="a full cartridge")
    clusters = CommentMiner().cluster(audience_signals(), minimum_count=1)
    competitor = CompetitorAnalyzer().summarize(competitor_observations())
    route = GlobalIdeaRouter().route(idea(), channels())
    _json({"safety": "review-only; no production imports, network calls, workflows, uploads, or secrets", "capability_count": len(registry.list()), "sample_hooks": [asdict(item) for item in candidate_set.hooks], "audience_clusters": [asdict(item) for item in clusters[:5]], "competitor_pattern": asdict(competitor), "route": asdict(route)})
    return 0


def cmd_keys(_: argparse.Namespace) -> int:
    _json({provider_id: {"purpose": provider.purpose, "cost_class": provider.cost_class.value, "secrets": [secret.name for secret in provider.secrets]} for provider_id, provider in PROVIDERS.items() if provider.secrets})
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    registry = default_registry()
    report = CapabilityTruthReport(registry)
    if args.output: report.write(Path(args.output))
    _json({"prototype_only": True, "capabilities": len(registry.list()), "secret_status": secret_status(), "local_tools": {name: requirement.executable for name, requirement in LOCAL_TOOLS.items()}, "output": args.output or None})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review-only capability studio")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo"); demo.set_defaults(func=cmd_demo)
    keys = sub.add_parser("keys"); keys.set_defaults(func=cmd_keys)
    doctor = sub.add_parser("doctor"); doctor.add_argument("--output", default=""); doctor.set_defaults(func=cmd_doctor)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
