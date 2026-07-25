"""Review-only end-to-end quality orchestration blueprint.

NOT WIRED INTO THE PIPELINE.

The collaborators are Protocols and must be injected by a caller. This module does
not know how to render, judge, persist, or publish anything. It demonstrates the
control flow Claude should eventually implement against the live interfaces:

baseline -> diagnose -> generate structural candidates -> preview -> rank ->
full rerender -> compare complete attempts -> promote winner or retain incumbent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, Sequence


class VerdictClass(str, Enum):
    REJECT = "reject"
    HOLD = "hold"
    SHIP = "ship"


@dataclass(frozen=True)
class RepairTarget:
    scene_id: str
    scene_index: int
    start_seconds: float
    end_seconds: float
    failure_class: str
    visible_evidence: str
    root_cause: str
    repair_goal: str

    def validate(self) -> None:
        if not self.scene_id:
            raise ValueError("repair target requires scene_id")
        if self.scene_index < 0:
            raise ValueError("repair target requires non-negative scene_index")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("repair target requires a positive time range")
        if not self.failure_class or not self.visible_evidence or not self.repair_goal:
            raise ValueError("repair target is missing structured diagnosis fields")


@dataclass(frozen=True)
class ScenePlan:
    candidate_id: str
    scene_id: str
    visualization: str
    performance_family: str
    camera_purpose: str
    payoff: str
    semantic_rationale: str
    lineage: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactBundle:
    attempt_id: str
    story_slug: str
    plan_hash: str
    video_hash: str
    manifest_hash: str
    video_location: str
    plan_location: str

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("attempt_id", self.attempt_id),
                ("story_slug", self.story_slug),
                ("plan_hash", self.plan_hash),
                ("video_hash", self.video_hash),
                ("manifest_hash", self.manifest_hash),
                ("video_location", self.video_location),
                ("plan_location", self.plan_location),
            )
            if not value
        ]
        if missing:
            raise ValueError("artifact bundle missing: " + ", ".join(missing))


@dataclass(frozen=True)
class ScenePreview:
    candidate: ScenePlan
    preview_hash: str
    preview_location: str
    objective_passed: bool
    objective_failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateRanking:
    ordered_candidate_ids: tuple[str, ...]
    reasons: Mapping[str, str]
    watched_previews: bool
    judge_version: str


@dataclass(frozen=True)
class FullVerdict:
    verdict: VerdictClass
    score: float
    lowest_dimension: float
    hard_failures: tuple[str, ...]
    weakest_scene: RepairTarget | None
    watched_video: bool
    primary_judge_version: str
    adversarial_judge_version: str
    adversarial_objections: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return (
            self.verdict == VerdictClass.SHIP
            and self.watched_video
            and not self.hard_failures
            and not self.adversarial_objections
        )


@dataclass(frozen=True)
class Attempt:
    artifacts: ArtifactBundle
    verdict: FullVerdict
    parent_attempt_id: str | None
    applied_candidates: tuple[str, ...]


@dataclass(frozen=True)
class CycleEvent:
    kind: str
    iteration: int
    detail: str
    attempt_id: str | None = None
    candidate_id: str | None = None


@dataclass(frozen=True)
class CycleReport:
    story_slug: str
    incumbent_attempt_id: str
    canonical_attempt_id: str
    attempts: tuple[Attempt, ...]
    events: tuple[CycleEvent, ...]
    stopped_reason: str
    promoted: bool


class CandidateSource(Protocol):
    def propose(
        self,
        story_slug: str,
        target: RepairTarget,
        *,
        incumbent: Attempt,
        count: int,
    ) -> Sequence[ScenePlan]: ...


class Renderer(Protocol):
    def render_baseline(self, story_slug: str) -> ArtifactBundle: ...

    def render_scene_preview(
        self,
        story_slug: str,
        candidate: ScenePlan,
    ) -> ScenePreview: ...

    def render_full_attempt(
        self,
        story_slug: str,
        *,
        incumbent: Attempt,
        candidate: ScenePlan,
        iteration: int,
    ) -> ArtifactBundle: ...


class Judge(Protocol):
    def judge_full(self, artifacts: ArtifactBundle) -> FullVerdict: ...

    def rank_previews(
        self,
        target: RepairTarget,
        previews: Sequence[ScenePreview],
    ) -> CandidateRanking: ...


class AttemptStore(Protocol):
    def save_attempt(self, attempt: Attempt) -> None: ...

    def promote(self, attempt_id: str) -> None: ...

    def canonical_attempt_id(self, story_slug: str) -> str | None: ...


class OrchestrationError(RuntimeError):
    pass


def attempt_rank(attempt: Attempt) -> tuple[int, int, float, float]:
    verdict_rank = {
        VerdictClass.REJECT: 0,
        VerdictClass.HOLD: 1,
        VerdictClass.SHIP: 2,
    }[attempt.verdict.verdict]
    return (
        verdict_rank,
        1 if not attempt.verdict.hard_failures else 0,
        attempt.verdict.score,
        attempt.verdict.lowest_dimension,
    )


def choose_attempt(incumbent: Attempt, challenger: Attempt) -> Attempt:
    """Compare complete attempts; ties retain the incumbent."""

    return challenger if attempt_rank(challenger) > attempt_rank(incumbent) else incumbent


class QualityOrchestrator:
    def __init__(
        self,
        *,
        renderer: Renderer,
        judge: Judge,
        candidates: CandidateSource,
        store: AttemptStore,
        candidates_per_round: int = 3,
        maximum_repairs: int = 2,
    ) -> None:
        if candidates_per_round < 2:
            raise ValueError("at least two structural candidates are required")
        if maximum_repairs < 0:
            raise ValueError("maximum_repairs cannot be negative")
        self.renderer = renderer
        self.judge = judge
        self.candidates = candidates
        self.store = store
        self.candidates_per_round = candidates_per_round
        self.maximum_repairs = maximum_repairs

    def run(self, story_slug: str) -> CycleReport:
        events: list[CycleEvent] = []
        attempts: list[Attempt] = []

        baseline_artifacts = self.renderer.render_baseline(story_slug)
        baseline_artifacts.validate()
        baseline_verdict = self.judge.judge_full(baseline_artifacts)
        baseline = Attempt(
            artifacts=baseline_artifacts,
            verdict=baseline_verdict,
            parent_attempt_id=None,
            applied_candidates=(),
        )
        self.store.save_attempt(baseline)
        attempts.append(baseline)
        events.append(
            CycleEvent(
                kind="baseline_judged",
                iteration=0,
                detail=(
                    f"{baseline_verdict.verdict.value} score={baseline_verdict.score:.1f}"
                ),
                attempt_id=baseline.artifacts.attempt_id,
            )
        )

        incumbent = baseline
        if baseline.verdict.eligible:
            self.store.promote(baseline.artifacts.attempt_id)
            return CycleReport(
                story_slug=story_slug,
                incumbent_attempt_id=baseline.artifacts.attempt_id,
                canonical_attempt_id=baseline.artifacts.attempt_id,
                attempts=tuple(attempts),
                events=tuple(events),
                stopped_reason="baseline_shipped",
                promoted=True,
            )

        for iteration in range(1, self.maximum_repairs + 1):
            target = incumbent.verdict.weakest_scene
            if target is None:
                events.append(
                    CycleEvent(
                        kind="repair_stopped",
                        iteration=iteration,
                        detail="blocked verdict lacks structured weakest-scene diagnosis",
                        attempt_id=incumbent.artifacts.attempt_id,
                    )
                )
                break
            target.validate()

            plans = tuple(
                self.candidates.propose(
                    story_slug,
                    target,
                    incumbent=incumbent,
                    count=self.candidates_per_round,
                )
            )
            if len(plans) < 2:
                raise OrchestrationError(
                    "candidate source did not produce structurally distinct alternatives"
                )
            if len({plan.candidate_id for plan in plans}) != len(plans):
                raise OrchestrationError("candidate IDs must be unique")

            previews: list[ScenePreview] = []
            for plan in plans:
                preview = self.renderer.render_scene_preview(story_slug, plan)
                previews.append(preview)
                events.append(
                    CycleEvent(
                        kind=(
                            "preview_eligible"
                            if preview.objective_passed
                            else "preview_rejected"
                        ),
                        iteration=iteration,
                        detail=(
                            "objective checks passed"
                            if preview.objective_passed
                            else ", ".join(preview.objective_failures)
                        ),
                        attempt_id=incumbent.artifacts.attempt_id,
                        candidate_id=plan.candidate_id,
                    )
                )

            eligible_previews = tuple(
                preview for preview in previews if preview.objective_passed
            )
            if not eligible_previews:
                events.append(
                    CycleEvent(
                        kind="repair_stopped",
                        iteration=iteration,
                        detail="all candidate previews failed objective checks",
                        attempt_id=incumbent.artifacts.attempt_id,
                    )
                )
                break

            ranking = self.judge.rank_previews(target, eligible_previews)
            if not ranking.watched_previews:
                events.append(
                    CycleEvent(
                        kind="repair_stopped",
                        iteration=iteration,
                        detail="preview judge did not watch candidates",
                        attempt_id=incumbent.artifacts.attempt_id,
                    )
                )
                break

            eligible_by_id = {
                preview.candidate.candidate_id: preview
                for preview in eligible_previews
            }
            winner_id = next(
                (
                    candidate_id
                    for candidate_id in ranking.ordered_candidate_ids
                    if candidate_id in eligible_by_id
                ),
                None,
            )
            if winner_id is None:
                raise OrchestrationError(
                    "vision ranking did not name an eligible candidate"
                )
            selected = eligible_by_id[winner_id].candidate
            events.append(
                CycleEvent(
                    kind="candidate_selected",
                    iteration=iteration,
                    detail=ranking.reasons.get(winner_id, "vision-ranked winner"),
                    attempt_id=incumbent.artifacts.attempt_id,
                    candidate_id=winner_id,
                )
            )

            challenger_artifacts = self.renderer.render_full_attempt(
                story_slug,
                incumbent=incumbent,
                candidate=selected,
                iteration=iteration,
            )
            challenger_artifacts.validate()
            challenger_verdict = self.judge.judge_full(challenger_artifacts)
            challenger = Attempt(
                artifacts=challenger_artifacts,
                verdict=challenger_verdict,
                parent_attempt_id=incumbent.artifacts.attempt_id,
                applied_candidates=(
                    *incumbent.applied_candidates,
                    selected.candidate_id,
                ),
            )
            self.store.save_attempt(challenger)
            attempts.append(challenger)
            events.append(
                CycleEvent(
                    kind="challenger_judged",
                    iteration=iteration,
                    detail=(
                        f"{challenger_verdict.verdict.value} "
                        f"score={challenger_verdict.score:.1f}"
                    ),
                    attempt_id=challenger.artifacts.attempt_id,
                    candidate_id=selected.candidate_id,
                )
            )

            winner = choose_attempt(incumbent, challenger)
            if winner is challenger:
                incumbent = challenger
                events.append(
                    CycleEvent(
                        kind="challenger_became_incumbent",
                        iteration=iteration,
                        detail="complete challenger attempt beat incumbent",
                        attempt_id=challenger.artifacts.attempt_id,
                    )
                )
            else:
                events.append(
                    CycleEvent(
                        kind="challenger_rejected",
                        iteration=iteration,
                        detail="incumbent retained; challenger state not promoted",
                        attempt_id=challenger.artifacts.attempt_id,
                    )
                )

            if incumbent.verdict.eligible:
                break

        self.store.promote(incumbent.artifacts.attempt_id)
        canonical = self.store.canonical_attempt_id(story_slug)
        if canonical != incumbent.artifacts.attempt_id:
            raise OrchestrationError("store did not promote complete winning attempt")

        stopped = (
            "winner_shipped"
            if incumbent.verdict.eligible
            else "repair_budget_exhausted_or_unrepairable"
        )
        return CycleReport(
            story_slug=story_slug,
            incumbent_attempt_id=baseline.artifacts.attempt_id,
            canonical_attempt_id=incumbent.artifacts.attempt_id,
            attempts=tuple(attempts),
            events=tuple(events),
            stopped_reason=stopped,
            promoted=True,
        )
