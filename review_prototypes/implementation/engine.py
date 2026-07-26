from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence
import uuid

from .models import AttemptIdentity, SceneCandidate, SceneDiagnosis, Verdict
from .repository import AttemptRecord, AttemptRepository


class Renderer(Protocol):
    def render_baseline(self, slug: str, destination: Path) -> None: ...

    def render_candidate(
        self,
        slug: str,
        incumbent: AttemptRecord,
        candidate: SceneCandidate,
        destination: Path,
    ) -> None: ...


class Judge(Protocol):
    def judge(self, slug: str, rendered_dir: Path) -> Verdict: ...


class CandidateGenerator(Protocol):
    def propose(
        self,
        slug: str,
        diagnosis: SceneDiagnosis,
        incumbent: AttemptRecord,
        *,
        count: int,
    ) -> Sequence[SceneCandidate]: ...


class PreviewRanker(Protocol):
    def select(
        self,
        slug: str,
        diagnosis: SceneDiagnosis,
        candidates: Sequence[SceneCandidate],
    ) -> SceneCandidate: ...


@dataclass(frozen=True)
class CycleStep:
    kind: str
    attempt_id: str | None
    candidate_id: str | None
    detail: str


@dataclass(frozen=True)
class CycleResult:
    slug: str
    run_id: str
    baseline_attempt_id: str
    canonical_attempt_id: str | None
    attempts: tuple[str, ...]
    steps: tuple[CycleStep, ...]
    stopped_reason: str


class RepairEngine:
    def __init__(
        self,
        *,
        repository: AttemptRepository,
        renderer: Renderer,
        judge: Judge,
        candidate_generator: CandidateGenerator,
        preview_ranker: PreviewRanker,
        work_root: Path,
        maximum_repairs: int = 2,
        candidates_per_round: int = 3,
    ) -> None:
        if maximum_repairs < 0:
            raise ValueError("maximum_repairs cannot be negative")
        if candidates_per_round < 2:
            raise ValueError("candidates_per_round must be at least 2")
        self.repository = repository
        self.renderer = renderer
        self.judge = judge
        self.candidate_generator = candidate_generator
        self.preview_ranker = preview_ranker
        self.work_root = Path(work_root)
        self.maximum_repairs = maximum_repairs
        self.candidates_per_round = candidates_per_round

    def run(self, slug: str, *, run_id: str | None = None) -> CycleResult:
        run_id = run_id or uuid.uuid4().hex[:12]
        run_work = self.work_root / slug / run_id
        run_work.mkdir(parents=True, exist_ok=False)
        steps: list[CycleStep] = []
        attempt_ids: list[str] = []

        baseline_id = "attempt_0"
        baseline_dir = run_work / baseline_id
        baseline_dir.mkdir()
        self.renderer.render_baseline(slug, baseline_dir)
        baseline_verdict = self.judge.judge(slug, baseline_dir)
        baseline = self.repository.record(
            identity=AttemptIdentity(slug, run_id, baseline_id),
            rendered_dir=baseline_dir,
            verdict=baseline_verdict,
            parent_attempt_id=None,
            candidate=None,
        )
        attempt_ids.append(baseline_id)
        steps.append(
            CycleStep(
                "baseline_judged",
                baseline_id,
                None,
                (
                    f"{baseline.verdict.decision.value} "
                    f"score={baseline.verdict.score:.1f}"
                ),
            )
        )
        incumbent = baseline

        if incumbent.verdict.decision.value == "ship":
            self.repository.promote(incumbent)
            return self._result(
                slug,
                run_id,
                baseline_id,
                attempt_ids,
                steps,
                "baseline_shipped",
            )

        for iteration in range(1, self.maximum_repairs + 1):
            diagnosis = incumbent.verdict.weakest_scene
            if diagnosis is None:
                steps.append(
                    CycleStep(
                        "stopped",
                        incumbent.identity.attempt_id,
                        None,
                        "missing structured weakest-scene diagnosis",
                    )
                )
                return self._result(
                    slug,
                    run_id,
                    baseline_id,
                    attempt_ids,
                    steps,
                    "missing_diagnosis",
                )

            candidates = tuple(
                self.candidate_generator.propose(
                    slug,
                    diagnosis,
                    incumbent,
                    count=self.candidates_per_round,
                )
            )
            self._validate_candidates(candidates, diagnosis)
            selected = self.preview_ranker.select(
                slug,
                diagnosis,
                candidates,
            )
            if selected.candidate_id not in {
                item.candidate_id for item in candidates
            }:
                raise ValueError(
                    "preview ranker selected an unknown candidate"
                )
            steps.append(
                CycleStep(
                    "candidate_selected",
                    incumbent.identity.attempt_id,
                    selected.candidate_id,
                    selected.rationale,
                )
            )

            attempt_id = f"attempt_{iteration}"
            attempt_dir = run_work / attempt_id
            attempt_dir.mkdir()
            self.renderer.render_candidate(
                slug,
                incumbent,
                selected,
                attempt_dir,
            )
            verdict = self.judge.judge(slug, attempt_dir)
            challenger = self.repository.record(
                identity=AttemptIdentity(slug, run_id, attempt_id),
                rendered_dir=attempt_dir,
                verdict=verdict,
                parent_attempt_id=incumbent.identity.attempt_id,
                candidate=selected,
            )
            attempt_ids.append(attempt_id)
            steps.append(
                CycleStep(
                    "challenger_judged",
                    attempt_id,
                    selected.candidate_id,
                    f"{verdict.decision.value} score={verdict.score:.1f}",
                )
            )

            if challenger.verdict.rank() > incumbent.verdict.rank():
                incumbent = challenger
                steps.append(
                    CycleStep(
                        "challenger_accepted",
                        attempt_id,
                        selected.candidate_id,
                        "complete challenger beat the incumbent",
                    )
                )
            else:
                steps.append(
                    CycleStep(
                        "challenger_rejected",
                        attempt_id,
                        selected.candidate_id,
                        (
                            "incumbent retained; challenger state was not "
                            "promoted"
                        ),
                    )
                )

            if incumbent.verdict.decision.value == "ship":
                self.repository.promote(incumbent)
                return self._result(
                    slug,
                    run_id,
                    baseline_id,
                    attempt_ids,
                    steps,
                    "repaired_to_ship",
                )

        if incumbent.verdict.promotable:
            self.repository.promote(incumbent)
            stopped = "budget_exhausted_best_promoted"
        else:
            stopped = "budget_exhausted_no_promotable_attempt"
        return self._result(
            slug,
            run_id,
            baseline_id,
            attempt_ids,
            steps,
            stopped,
        )

    def _result(
        self,
        slug: str,
        run_id: str,
        baseline_id: str,
        attempts: list[str],
        steps: list[CycleStep],
        reason: str,
    ) -> CycleResult:
        canonical = self.repository.canonical(slug)
        return CycleResult(
            slug=slug,
            run_id=run_id,
            baseline_attempt_id=baseline_id,
            canonical_attempt_id=(
                canonical.identity.attempt_id if canonical else None
            ),
            attempts=tuple(attempts),
            steps=tuple(steps),
            stopped_reason=reason,
        )

    @staticmethod
    def _validate_candidates(
        candidates: Sequence[SceneCandidate],
        diagnosis: SceneDiagnosis,
    ) -> None:
        if len(candidates) < 2:
            raise ValueError(
                "candidate generator must produce at least two candidates"
            )
        ids: set[str] = set()
        structures: set[tuple[str, str]] = set()
        for candidate in candidates:
            candidate.validate()
            if candidate.scene_id != diagnosis.scene_id:
                raise ValueError("candidate targets the wrong scene")
            if candidate.candidate_id in ids:
                raise ValueError("candidate IDs must be unique")
            structure = (
                candidate.visualization,
                candidate.performance_family,
            )
            if structure in structures:
                raise ValueError(
                    "candidates must be structurally distinct"
                )
            ids.add(candidate.candidate_id)
            structures.add(structure)
