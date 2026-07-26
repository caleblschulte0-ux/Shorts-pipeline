from __future__ import annotations

PATCH_TARGETS = (
    {
        "order": 1,
        "path": "data_learning/story.py",
        "symbols": ["Segment", "Story", "build"],
        "change": "accept optional compiled quality metadata without changing source truth",
        "acceptance": "existing story tests and contract probe pass",
        "rollback": "remove optional metadata fields; serialized story config remains valid",
    },
    {
        "order": 2,
        "path": "data_learning/viz_director.py",
        "symbols": ["assign", "renderable", "KINDS"],
        "change": "consume compiled kind only when renderable and explicitly preview-enabled",
        "acceptance": "fallback and novelty guarantees remain intact",
        "rollback": "disable preview flag and return to current assign behavior",
    },
    {
        "order": 3,
        "path": "data_learning/charts.py",
        "symbols": ["render_story_build", "_perf_action", "FALLBACK"],
        "change": "honor verified perf_override and preserve terminal fallbacks",
        "acceptance": "attachment sidecar, contact coverage, and cadence tests pass",
        "rollback": "ignore perf_override and use current performance_for routing",
    },
    {
        "order": 4,
        "path": "data_learning/studio_render.py",
        "symbols": ["render", "_build_soundtrack", "_plan_events"],
        "change": "read compiled scene/audio/transition metadata in preview mode",
        "acceptance": "matched baseline/shadow MP4s render with publishing frozen",
        "rollback": "unset preview flag; renderer ignores all shadow metadata",
    },
    {
        "order": 5,
        "path": "scripts/showrunner_review.py",
        "symbols": ["review_video", "decide_verdict", "AUTOFAIL_CHECKS"],
        "change": "attach diagnostic metadata only",
        "acceptance": "WEIGHTS, AUTOFAIL_CHECKS, MIN_SCORE, and verdict behavior unchanged",
        "rollback": "drop diagnostic context fields",
    },
    {
        "order": 6,
        "path": "scripts/scene_repair.py",
        "symbols": ["propose", "score_candidate", "VARIANTS"],
        "change": "include bridge-generated structural candidates in blind keep-best review",
        "acceptance": "incumbent is retained unless challenger wins by the existing margin",
        "rollback": "use current VARIANTS table only",
    },
    {
        "order": 7,
        "path": "scripts/repair_loop.py",
        "symbols": ["repair", "pick_remedy", "better"],
        "change": "record bridge evidence while preserving bounded monotone repair",
        "acceptance": "a worse challenger never replaces the incumbent",
        "rollback": "ignore bridge evidence and keep current loop",
    },
)

PHASES = (
    {
        "phase": 0,
        "name": "preflight",
        "commands": [
            "python -m unittest -v review_prototypes.integration_bridge.test_integration_bridge",
            "python -m unittest -v review_prototypes.launch_closure.test_launch_closure",
            "python -m review_prototypes.launch_closure.cli --out /tmp/shorts-launch-rehearsal",
        ],
        "gate": "all frozen contracts and closure gates pass",
        "rollback": "none; read-only",
    },
    {
        "phase": 1,
        "name": "adapter-only patch",
        "commands": ["apply patch targets 1-3 on a separate Claude branch"],
        "gate": "existing production tests plus contract probe pass",
        "rollback": "revert the phase commit",
    },
    {
        "phase": 2,
        "name": "matched dry-run",
        "commands": [
            "render the same slug once as baseline and once with shadow metadata",
            "keep --dry-run and publishing freeze enabled",
        ],
        "gate": "both artifacts exist; source data and narration remain identical",
        "rollback": "unset the preview flag and delete temporary artifacts",
    },
    {
        "phase": 3,
        "name": "complete-video gate",
        "commands": ["run the sovereign showrunner twice on the complete shadow MP4"],
        "gate": "two consecutive real verdicts ship with no auto-fails",
        "rollback": "retain baseline; do not adopt the shadow cut",
    },
    {
        "phase": 4,
        "name": "controlled holdout",
        "commands": ["run a frozen or private holdout before any public release"],
        "gate": "no regression in quality or channel guardrails",
        "rollback": "disable preview integration and restore the prior canonical plan",
    },
)


def validate_launch_plan() -> dict:
    orders = [item["order"] for item in PATCH_TARGETS]
    phase_ids = [item["phase"] for item in PHASES]
    errors = []
    if orders != list(range(1, len(PATCH_TARGETS) + 1)):
        errors.append("patch target order is not contiguous")
    if phase_ids != list(range(len(PHASES))):
        errors.append("phase order is not contiguous")
    for item in PATCH_TARGETS:
        if not item["symbols"] or not item["acceptance"] or not item["rollback"]:
            errors.append(f"incomplete patch target: {item['path']}")
    for phase in PHASES:
        if not phase["commands"] or not phase["gate"] or not phase["rollback"]:
            errors.append(f"incomplete phase: {phase['name']}")
    return {
        "ok": not errors,
        "patch_targets": len(PATCH_TARGETS),
        "phases": len(PHASES),
        "errors": errors,
    }
