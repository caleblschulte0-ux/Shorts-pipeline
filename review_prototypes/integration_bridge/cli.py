from __future__ import annotations

import argparse
import json
from pathlib import Path

from .claude_handoff import execution_handoff, markdown_handoff
from .fixtures import archetype_story
from .patch_blueprints import migration_plan
from .production_probe import default_requirements, probe_checkout
from .quality_compiler import compile_bridge
from .story_adapter import adapt_story


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--repo", type=Path, default=Path("."))
    plan = sub.add_parser("plan")
    plan.add_argument("--fixture", choices=("money", "share", "ranking", "comparison", "single"), default="money")
    plan.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.command == "probe":
        report = probe_checkout(args.repo, default_requirements())
        print(json.dumps({
            "passed": report.passed,
            "percent": report.percent,
            "results": [
                {
                    "path": result.path,
                    "passed": result.passed,
                    "sha_matches": result.sha_matches,
                    "symbols_missing": result.symbols_missing,
                    "literals_missing": result.literals_missing,
                }
                for result in report.results
            ],
        }, indent=2))
        return 0 if report.passed else 2

    story = adapt_story(archetype_story(args.fixture))
    bundle = compile_bridge(story)
    # A fixture plan cannot verify a live checkout, so handoff shows the migration
    # gates honestly while still giving Claude the exact adapter payload.
    empty_report = probe_checkout(Path("/__missing_checkout__"), default_requirements())
    migration = migration_plan(contracts_locked=False, shadow_tests_green=True)
    payload = execution_handoff(bundle, empty_report, migration)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.suffix.lower() == ".md":
            args.out.write_text(markdown_handoff(payload), encoding="utf-8")
        else:
            args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
