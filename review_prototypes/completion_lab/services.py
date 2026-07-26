from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from .models import Fault, RenderBundle, StorySpec, Verdict, sha256_file


class SyntheticRenderer:
    version = "synthetic-renderer-v1"

    def __init__(self, fault: Fault = Fault.NONE) -> None:
        self.fault = fault

    def render(self, story: StorySpec, destination: Path, *, attempt_id: str) -> RenderBundle:
        if self.fault is Fault.RENDER_CRASH:
            raise RuntimeError("synthetic renderer crash")
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        plan_path = destination / "scene_plan.json"
        video_path = destination / "video.mp4"
        plan_path.write_text(json.dumps(story.canonical_payload(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
        payload = hashlib.sha256((story.digest + attempt_id).encode("utf-8")).digest() * 8
        if self.fault is not Fault.MISSING_VIDEO:
            video_path.write_bytes(payload)
        bundle = RenderBundle(
            story_slug=story.slug,
            attempt_id=attempt_id,
            directory=destination,
            video_path=video_path,
            plan_path=plan_path,
            video_hash=sha256_file(video_path) if video_path.exists() else "missing",
            plan_hash=sha256_file(plan_path),
            renderer_version=self.version,
        )
        return bundle


class SyntheticJudge:
    version = "synthetic-judge-v1"

    def __init__(self, fault: Fault = Fault.NONE) -> None:
        self.fault = fault

    def judge(self, story: StorySpec, render: RenderBundle) -> Verdict | dict[str, object]:
        render.validate()
        tensions = [beat.tension for beat in story.beats]
        mascot_diversity = len({beat.mascot_action for beat in story.beats})
        score = min(98.0, 88.0 + mascot_diversity + max(tensions) * 5)
        verdict = Verdict(
            score=round(score, 1),
            lowest_dimension=9.0,
            effective_fps=30.0,
            duplicate_ratio=0.03,
            watched_video=True,
            hard_failures=(),
            judge_version=self.version,
        )
        from .faults import apply_verdict_fault

        return apply_verdict_fault(verdict, self.fault)


class FailingRenderer:
    version = ""

    def render(self, story: StorySpec, destination: Path, *, attempt_id: str) -> RenderBundle:
        raise RuntimeError("contract renderer failure")


class FailingJudge:
    version = ""

    def judge(self, story: StorySpec, render: RenderBundle) -> Verdict:
        return replace(
            Verdict(90, 9, 30, 0.03, True, (), "bad"),
            watched_video=False,
        )
