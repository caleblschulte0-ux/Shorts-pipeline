from __future__ import annotations

from pathlib import Path

from .media import ARCHETYPES, content_fingerprint, motion_ratio, probe_clip, render_rehearsal_clip
from .reviewer import preserve_sovereign_block, structural_repair_candidates, two_pass_review, review_metrics
from .state_restore import apply_shadow_plan, canonical_hash, restore_original


def _story_fixture(archetype: str) -> dict:
    return {
        "slug": f"launch-{archetype}",
        "hook": f"{archetype} hook",
        "segments": [
            {"kind": "bubbles", "sentence": "baseline", "plan_locked": False},
            {"kind": "trend", "sentence": "consequence", "plan_locked": False},
        ],
    }


def _shadow_plan(archetype: str) -> dict:
    first = structural_repair_candidates(archetype)[0]
    return {"segments": [{"index": 0, "kind": first["viz"], "perf_override": first["perf"]}]}


def run_archetype_rehearsal(workdir: Path, archetype: str) -> dict:
    adir = workdir / archetype
    baseline_path = render_rehearsal_clip(adir / "baseline.mp4", archetype=archetype, shadow=False)
    shadow_path = render_rehearsal_clip(adir / "shadow.mp4", archetype=archetype, shadow=True)
    shadow_rerun_path = render_rehearsal_clip(adir / "shadow_rerun.mp4", archetype=archetype, shadow=True)
    baseline_probe = probe_clip(baseline_path)
    baseline_probe["motion_ratio"] = motion_ratio(baseline_path)
    shadow_probe = probe_clip(shadow_path)
    shadow_probe["motion_ratio"] = motion_ratio(shadow_path)
    baseline_verdict = review_metrics(baseline_probe)
    shadow_review = two_pass_review(shadow_probe)
    repair = preserve_sovereign_block(baseline_verdict, structural_repair_candidates(archetype))
    story = _story_fixture(archetype)
    changed, receipt = apply_shadow_plan(story, _shadow_plan(archetype))
    restored = restore_original(changed, receipt)
    return {
        "archetype": archetype,
        "baseline": {
            "probe": baseline_probe,
            "verdict": baseline_verdict,
            "fingerprint": content_fingerprint(baseline_path),
        },
        "shadow": {
            "probe": shadow_probe,
            "review": shadow_review,
            "fingerprint": content_fingerprint(shadow_path),
            "rerun_fingerprint": content_fingerprint(shadow_rerun_path),
        },
        "improvement": {
            "motion_delta": round(shadow_probe["motion_ratio"] - baseline_probe["motion_ratio"], 3),
            "score_delta": shadow_review["passes"][0]["score"] - baseline_verdict["score"],
        },
        "repair": repair,
        "rollback": {
            "before_hash": receipt["before_hash"],
            "changed_hash": receipt["after_hash"],
            "restored_hash": canonical_hash(restored),
            "verified": canonical_hash(restored) == receipt["before_hash"],
        },
    }


def run_all_rehearsals(workdir: Path) -> list[dict]:
    return [run_archetype_rehearsal(workdir, archetype) for archetype in ARCHETYPES]
