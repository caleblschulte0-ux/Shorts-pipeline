from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .contracts import ContractReport, MigrationPlan, QualityBridgeBundle


def execution_handoff(
    bundle: QualityBridgeBundle,
    contracts: ContractReport,
    migration: MigrationPlan,
) -> dict[str, Any]:
    bundle.validate()
    migration.validate()
    return {
        "status": "ready_for_claude_shadow_integration",
        "scope_boundary": {
            "production_modified": False,
            "publishing_enabled": False,
            "showrunner_authority_changed": False,
        },
        "production_contracts": {
            "passed": contracts.passed,
            "percent": contracts.percent,
            "files": [asdict(result) | {"passed": result.passed} for result in contracts.results],
        },
        "bridge_bundle": bundle.to_dict(),
        "migration": {
            "readiness_percent": migration.readiness_percent,
            "next_phase": None if migration.next_phase is None else migration.next_phase.name,
            "phases": [
                {
                    "index": phase.index,
                    "name": phase.name,
                    "purpose": phase.purpose,
                    "ready": phase.ready,
                    "targets": [asdict(target) for target in phase.targets],
                    "gates": [asdict(gate) for gate in phase.gates],
                }
                for phase in migration.phases
            ],
        },
        "first_commands_for_claude": [
            "python -m review_prototypes.integration_bridge.cli probe --repo .",
            "python -m unittest review_prototypes.integration_bridge.test_integration_bridge",
            "python -m review_prototypes.integration_bridge.cli plan --fixture money",
            "render the same slug once with QUALITY_BRIDGE_MODE=off and once with QUALITY_BRIDGE_MODE=shadow",
            "do not enable apply mode until both artifacts and the full MP4 have been reviewed",
        ],
    }


def markdown_handoff(payload: dict[str, Any]) -> str:
    migration = payload["migration"]
    lines = [
        "# Claude Jumpstart — Shadow Integration Bridge",
        "",
        "This is an executable jumping-off point for adapting the review-only quality systems to the real explainer pipeline.",
        "It does not authorize direct production wiring, publishing, or weakening the showrunner.",
        "",
        "## Frozen boundaries",
        "",
        "- Production modified: **false**",
        "- Publishing enabled: **false**",
        "- Showrunner authority changed: **false**",
        f"- Production contract probe: **{payload['production_contracts']['percent']}%**",
        f"- Migration gate readiness: **{migration['readiness_percent']}%**",
        "",
        "## Exact production targets",
        "",
    ]
    for phase in migration["phases"]:
        lines.append(f"### Phase {phase['index']} — {phase['name']}")
        lines.append(phase["purpose"])
        for target in phase["targets"]:
            lines.append(f"- `{target['path']}::{target['symbol']}` — {target['change']}")
            lines.append(f"  - Guard: {target['guard']}")
            lines.append(f"  - Rollback: {target['rollback']}")
        for gate in phase["gates"]:
            mark = "PASS" if gate["passed"] else "BLOCKED"
            lines.append(f"- Gate [{mark}] {gate['name']}: {gate['evidence']}")
        lines.append("")
    lines += [
        "## Rules Claude must preserve",
        "",
        "1. `SHOWRUNNER` remains sovereign and fail-closed on publish runs.",
        "2. The default bridge mode is off; shadow mode may emit evidence but may not alter rendering.",
        "3. Apply mode is preview-only until complete MP4 review and two consecutive showrunner passes.",
        "4. Existing `state/scene_plans/{slug}.json` remains backward compatible with `{viz, perf}`.",
        "5. No media, models, or render artifacts are committed to git.",
    ]
    return "\n".join(lines) + "\n"
