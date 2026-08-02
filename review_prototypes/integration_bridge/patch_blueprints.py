from __future__ import annotations

from .contracts import MigrationGate, MigrationPhase, MigrationPlan, PatchTarget


def patch_targets() -> tuple[PatchTarget, ...]:
    return (
        PatchTarget(
            0,
            "data_learning/story.py",
            "build",
            "After viz_director.assign, optionally read a prevalidated bridge plan and attach kind/perf_override/plan_locked to each insight; default path remains byte-for-byte behaviorally identical.",
            "QUALITY_BRIDGE_MODE=shadow|apply; default off; reject slug/fingerprint/segment-count mismatch.",
            (
                "off mode produces the current Story object unchanged",
                "shadow mode records proposed overrides without mutating insights",
                "apply mode only accepts production-supported kinds/actions",
            ),
            "unset QUALITY_BRIDGE_MODE and delete the plan sidecar",
            "medium",
        ),
        PatchTarget(
            1,
            "data_learning/studio_render.py",
            "render",
            "Read the attached scene plan when present, preserve existing segment_windows, and append quality_bridge metadata to the render manifest.",
            "manifest extension only in shadow mode; no upload behavior changes.",
            (
                "existing manifest keys remain present and unchanged",
                "showrunner frame sampling still receives segment_windows",
                "manifest includes scene timeline, transition, callback, and audio plan",
            ),
            "ignore quality_bridge metadata and render from current fields",
            "low",
        ),
        PatchTarget(
            2,
            "data_learning/studio_render.py",
            "_build_soundtrack",
            "Accept optional frame-snapped audio placements from the bridge while retaining current synthesized SFX as the fallback.",
            "only allow named cues from a fixed library; clamp timing/gain; preview first.",
            (
                "no cue extends beyond total duration",
                "voice remains primary and loudness-limited",
                "payoff silence and number hits survive final mux",
            ),
            "omit the optional audio plan argument",
            "medium",
        ),
        PatchTarget(
            3,
            "scripts/post_stories.py",
            "main",
            "Pass quality_bridge scene plans into showrunner context and keep PUBLISH FROZEN during shadow comparison.",
            "never set --publish or PUBLISH_ENABLED; showrunner BLOCK remains sovereign.",
            (
                "dry-run writes baseline and bridge context",
                "no uploader is constructed in shadow runs",
                "reviewer can cite scene goal/target/timeline in fixes",
            ),
            "remove quality_bridge from context; no production state changed",
            "low",
        ),
        PatchTarget(
            4,
            "scripts/scene_repair.py",
            "propose",
            "Seed structural candidates from the bridge compiler, then render/score them through the existing blind keep-best machinery.",
            "retain current >0.08 incumbent margin and existing minimal {viz, perf} persisted schema.",
            (
                "three candidates are structurally different",
                "incumbent is retained unless margin exceeds 0.08",
                "no candidate can weaken or bypass showrunner",
            ),
            "fall back to the current VARIANTS table",
            "medium",
        ),
        PatchTarget(
            5,
            "scripts/repair_loop.py",
            "repair",
            "Include hook/data_demo/payoff bridge remedies while preserving bounded attempts, monotone keep-best, and stop reasons.",
            "max-iters remains bounded; verdict comparison is unchanged; no code-edit remedies.",
            (
                "BLOCK is never converted to SHIP by code",
                "a lower-score candidate is discarded",
                "budget exhaustion remains a hold",
            ),
            "restore the current REMEDIES mapping",
            "medium",
        ),
        PatchTarget(
            6,
            "scripts/showrunner_review.py",
            "review_video",
            "Expose bridge-plan adherence as evidence to the brain, but do not alter WEIGHTS, AUTOFAIL_CHECKS, MIN_SCORE, decide_verdict, or fail-closed publish behavior.",
            "contract test forbids edits to sovereign scoring and verdict symbols.",
            (
                "existing calibration tests remain unchanged and green",
                "brain BLOCK remains impossible to override",
                "bridge metadata only improves diagnosis and scene targeting",
            ),
            "stop passing bridge context; scoring remains untouched",
            "high",
        ),
    )


def migration_plan(
    *,
    contracts_locked: bool = True,
    shadow_tests_green: bool = True,
    baseline_preview_saved: bool = False,
    bridge_preview_saved: bool = False,
    full_mp4_watched: bool = False,
    showrunner_two_run_pass: bool = False,
    publish_freeze_verified: bool = True,
    real_channel_holdout: bool = False,
) -> MigrationPlan:
    targets = patch_targets()
    phases = (
        MigrationPhase(0, "Contract lock", "Freeze production symbols and schemas before Claude edits anything.", tuple(t for t in targets if t.phase == 0), (
            MigrationGate("production contract probe", contracts_locked, "all required symbols/SHAs verified"),
            MigrationGate("shadow adapter tests", shadow_tests_green, "duck-typed adapter and non-mutating apply suite"),
        )),
        MigrationPhase(1, "Shadow manifest", "Generate bridge plans and manifests beside the baseline with zero render behavior changes.", tuple(t for t in targets if t.phase in {1, 3}), (
            MigrationGate("baseline preview artifact", baseline_preview_saved, "same story rendered without bridge"),
            MigrationGate("bridge shadow artifact", bridge_preview_saved, "plan and context emitted without applying"),
            MigrationGate("publish freeze", publish_freeze_verified, "PUBLISH FROZEN and no uploader construction"),
        )),
        MigrationPhase(2, "Preview application", "Apply bridge plans to copied/runtime objects only in explicit preview mode.", tuple(t for t in targets if t.phase == 2), (
            MigrationGate("complete MP4 watched", full_mp4_watched, "human/Claude watched the full output, not just frames"),
            MigrationGate("two consecutive showrunner passes", showrunner_two_run_pass, "locked versions, no single-story regression"),
        )),
        MigrationPhase(3, "Repair adoption", "Use bridge candidates inside existing scene-addressable blind keep-best repair.", tuple(t for t in targets if t.phase in {4, 5}), (
            MigrationGate("repair monotonicity proof", shadow_tests_green, "worse candidate rejected and budget bounded"),
            MigrationGate("showrunner sovereignty proof", contracts_locked, "verdict logic unchanged"),
        )),
        MigrationPhase(4, "Diagnostic context", "Give the showrunner richer plans without changing authority or score rules.", tuple(t for t in targets if t.phase == 6), (
            MigrationGate("calibration suite unchanged", contracts_locked, "WEIGHTS/AUTOFAIL/decide_verdict contract locked"),
            MigrationGate("real-channel holdout", real_channel_holdout, "controlled batch beats baseline without guardrail regression"),
        )),
    )
    result = MigrationPlan(phases)
    result.validate()
    return result
