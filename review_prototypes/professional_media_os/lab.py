"""Deterministic creative-intelligence lab for isolated review.

The lab demonstrates professional control surfaces: hard gates, independent critics,
visible component utilities, counterfactual preservation, and evaluator calibration.
It performs no model calls and claims no prediction validity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from .contracts import (
    Candidate,
    CandidateEvaluation,
    ContractError,
    EvaluationFinding,
    EvaluationVerdict,
    EvidenceRef,
    TournamentResult,
    ensure_unique_ids,
    stable_hash,
    utc_now_iso,
)


@dataclass(frozen=True)
class EvaluationContext:
    evidence: Mapping[str, EvidenceRef]
    allowed_rights_risks: Tuple[str, ...]
    allowed_formats_by_channel: Mapping[str, Tuple[str, ...]]
    recent_hook_structures_by_channel: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    recent_title_patterns_by_channel: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    minimum_evidence_completeness: float = 0.75
    minimum_media_feasibility: float = 0.60
    maximum_first_proof_ms: int = 5000


class Evaluator(Protocol):
    evaluator_id: str
    version: str

    def evaluate(self, candidate: Candidate, context: EvaluationContext) -> CandidateEvaluation:
        ...


def _evaluation_id(evaluator_id: str, candidate_id: str, version: str) -> str:
    digest = stable_hash(
        {"evaluator_id": evaluator_id, "candidate_id": candidate_id, "version": version}
    )[:16]
    return f"eval-{digest}"


def _finding(
    code: str,
    message: str,
    verdict: EvaluationVerdict,
    confidence: float,
    *,
    evidence_ids: Sequence[str] = (),
    repair_hint: Optional[str] = None,
) -> EvaluationFinding:
    return EvaluationFinding(
        code=code,
        message=message,
        verdict=verdict,
        confidence=confidence,
        evidence_ids=tuple(evidence_ids),
        repair_hint=repair_hint,
    )


class HardConstraintEvaluator:
    evaluator_id = "hard-constraints"
    version = "1.0.0"

    def evaluate(self, candidate: Candidate, context: EvaluationContext) -> CandidateEvaluation:
        findings: List[EvaluationFinding] = []
        genome = candidate.genome

        missing_evidence = sorted(set(candidate.evidence_ids).difference(context.evidence))
        if missing_evidence:
            findings.append(
                _finding(
                    "evidence.missing",
                    f"Candidate references unknown evidence: {', '.join(missing_evidence)}",
                    EvaluationVerdict.BLOCK,
                    1.0,
                    repair_hint="Add immutable evidence records or remove unsupported claims.",
                )
            )

        if not candidate.evidence_ids:
            findings.append(
                _finding(
                    "evidence.empty",
                    "Candidate has no evidence references.",
                    EvaluationVerdict.BLOCK,
                    1.0,
                    repair_hint="Ground the premise and payoff before preview production.",
                )
            )

        if genome.evidence_completeness < context.minimum_evidence_completeness:
            findings.append(
                _finding(
                    "evidence.incomplete",
                    (
                        f"Evidence completeness {genome.evidence_completeness:.2f} is below "
                        f"the {context.minimum_evidence_completeness:.2f} gate."
                    ),
                    EvaluationVerdict.BLOCK,
                    0.98,
                    evidence_ids=candidate.evidence_ids,
                    repair_hint="Resolve unsupported claims or narrow the promise.",
                )
            )

        if genome.rights_risk not in context.allowed_rights_risks:
            findings.append(
                _finding(
                    "rights.disallowed",
                    f"Rights risk '{genome.rights_risk}' is outside the allowed set.",
                    EvaluationVerdict.BLOCK,
                    1.0,
                    repair_hint="Replace the media strategy with approved sources.",
                )
            )

        if genome.media_feasibility < context.minimum_media_feasibility:
            findings.append(
                _finding(
                    "media.infeasible",
                    (
                        f"Media feasibility {genome.media_feasibility:.2f} is below "
                        f"the {context.minimum_media_feasibility:.2f} gate."
                    ),
                    EvaluationVerdict.BLOCK,
                    0.95,
                    repair_hint="Change the visual concept before rendering.",
                )
            )

        allowed_formats = context.allowed_formats_by_channel.get(genome.channel_id)
        if allowed_formats is None:
            findings.append(
                _finding(
                    "identity.channel-unknown",
                    f"No channel contract exists for {genome.channel_id}.",
                    EvaluationVerdict.BLOCK,
                    1.0,
                )
            )
        elif genome.presentation_format not in allowed_formats:
            findings.append(
                _finding(
                    "identity.format-disallowed",
                    (
                        f"Format '{genome.presentation_format}' is not allowed for "
                        f"channel {genome.channel_id}."
                    ),
                    EvaluationVerdict.BLOCK,
                    1.0,
                )
            )

        if not findings:
            findings.append(
                _finding(
                    "constraints.clear",
                    "All hard constraints passed.",
                    EvaluationVerdict.PASS,
                    1.0,
                    evidence_ids=candidate.evidence_ids,
                )
            )

        return CandidateEvaluation(
            evaluation_id=_evaluation_id(self.evaluator_id, candidate.candidate_id, self.version),
            candidate_id=candidate.candidate_id,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.version,
            findings=tuple(findings),
            utility=None,
        )


class PromiseIntegrityEvaluator:
    evaluator_id = "promise-integrity"
    version = "1.0.0"

    def evaluate(self, candidate: Candidate, context: EvaluationContext) -> CandidateEvaluation:
        findings: List[EvaluationFinding] = []
        opening = candidate.opening_line.strip().lower()
        payoff = candidate.payoff_line.strip().lower()
        promise = candidate.promise.strip().lower()

        if len(candidate.opening_line.split()) > 18:
            findings.append(
                _finding(
                    "hook.wordy",
                    "Opening line exceeds 18 words and may delay comprehension.",
                    EvaluationVerdict.WARN,
                    0.80,
                    repair_hint="Preserve the claim while removing setup clauses.",
                )
            )

        overlap = set(promise.split()).intersection(payoff.split())
        semantic_proxy = len(overlap) / max(1, len(set(promise.split())))
        if semantic_proxy < 0.12:
            findings.append(
                _finding(
                    "promise.payoff-disconnect",
                    "The payoff has little lexical connection to the stated promise.",
                    EvaluationVerdict.WARN,
                    0.62,
                    repair_hint="Make the payoff explicitly resolve the viewer question.",
                )
            )

        if opening == payoff:
            findings.append(
                _finding(
                    "narrative.no-progression",
                    "Opening and payoff are identical; the story does not advance.",
                    EvaluationVerdict.BLOCK,
                    0.99,
                    repair_hint="Create a distinct reveal, consequence, or reversal.",
                )
            )

        if not findings:
            findings.append(
                _finding(
                    "promise.coherent",
                    "Opening, promise, and payoff form a coherent progression.",
                    EvaluationVerdict.PASS,
                    0.72,
                )
            )

        utility = max(0.0, min(1.0, 0.55 + semantic_proxy * 0.45 - 0.12 * len(findings)))
        return CandidateEvaluation(
            evaluation_id=_evaluation_id(self.evaluator_id, candidate.candidate_id, self.version),
            candidate_id=candidate.candidate_id,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.version,
            findings=tuple(findings),
            utility=utility,
        )


class FirstSecondsEvaluator:
    evaluator_id = "first-seconds"
    version = "1.0.0"

    def evaluate(self, candidate: Candidate, context: EvaluationContext) -> CandidateEvaluation:
        genome = candidate.genome
        findings: List[EvaluationFinding] = []

        if genome.first_subject_ms > 1000:
            findings.append(
                _finding(
                    "hook.subject-late",
                    f"Primary subject first appears at {genome.first_subject_ms} ms.",
                    EvaluationVerdict.WARN,
                    0.90,
                    repair_hint="Move the recognizable subject into the first second.",
                )
            )

        if genome.first_proof_ms is None:
            findings.append(
                _finding(
                    "hook.proof-unknown",
                    "The first proof time is unknown.",
                    EvaluationVerdict.WARN,
                    1.0,
                    repair_hint="Storyboard the first concrete proof before ranking.",
                )
            )
            proof_component = 0.35
        elif genome.first_proof_ms > context.maximum_first_proof_ms:
            findings.append(
                _finding(
                    "hook.proof-late",
                    (
                        f"First proof at {genome.first_proof_ms} ms exceeds the "
                        f"{context.maximum_first_proof_ms} ms target."
                    ),
                    EvaluationVerdict.WARN,
                    0.88,
                    repair_hint="Open on evidence or bring the proof beat forward.",
                )
            )
            proof_component = max(
                0.0,
                1.0 - genome.first_proof_ms / max(1, context.maximum_first_proof_ms * 3),
            )
        else:
            proof_component = 1.0 - 0.5 * (
                genome.first_proof_ms / max(1, context.maximum_first_proof_ms)
            )

        if not findings:
            findings.append(
                _finding(
                    "hook.first-seconds-clear",
                    "Subject and proof timing satisfy the first-seconds target.",
                    EvaluationVerdict.PASS,
                    0.85,
                )
            )

        subject_component = max(0.0, 1.0 - genome.first_subject_ms / 3000.0)
        utility = max(0.0, min(1.0, subject_component * 0.4 + proof_component * 0.6))
        return CandidateEvaluation(
            evaluation_id=_evaluation_id(self.evaluator_id, candidate.candidate_id, self.version),
            candidate_id=candidate.candidate_id,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.version,
            findings=tuple(findings),
            utility=utility,
        )


class FeasibilityEvaluator:
    evaluator_id = "production-feasibility"
    version = "1.0.0"

    def evaluate(self, candidate: Candidate, context: EvaluationContext) -> CandidateEvaluation:
        genome = candidate.genome
        findings: List[EvaluationFinding] = []

        if genome.estimated_runtime_seconds > 900:
            findings.append(
                _finding(
                    "production.runtime-high",
                    f"Estimated production runtime is {genome.estimated_runtime_seconds:.0f} seconds.",
                    EvaluationVerdict.WARN,
                    0.75,
                    repair_hint="Use a cheaper preview or simplify the visual plan.",
                )
            )
        if genome.estimated_cost > 5.0:
            findings.append(
                _finding(
                    "production.cost-high",
                    f"Estimated provider cost is ${genome.estimated_cost:.2f}.",
                    EvaluationVerdict.WARN,
                    0.75,
                    repair_hint="Reserve expensive generation for the final candidate.",
                )
            )

        if not findings:
            findings.append(
                _finding(
                    "production.feasible",
                    "Candidate is feasible within reference prototype thresholds.",
                    EvaluationVerdict.PASS,
                    0.80,
                )
            )

        runtime_penalty = min(0.45, genome.estimated_runtime_seconds / 3600.0)
        cost_penalty = min(0.35, genome.estimated_cost / 20.0)
        utility = max(
            0.0,
            min(1.0, genome.media_feasibility - runtime_penalty - cost_penalty),
        )
        return CandidateEvaluation(
            evaluation_id=_evaluation_id(self.evaluator_id, candidate.candidate_id, self.version),
            candidate_id=candidate.candidate_id,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.version,
            findings=tuple(findings),
            utility=utility,
        )


class NoveltyEvaluator:
    evaluator_id = "portfolio-novelty"
    version = "1.0.0"

    def evaluate(self, candidate: Candidate, context: EvaluationContext) -> CandidateEvaluation:
        genome = candidate.genome
        recent_hooks = context.recent_hook_structures_by_channel.get(genome.channel_id, ())
        recent_titles = context.recent_title_patterns_by_channel.get(genome.channel_id, ())
        findings: List[EvaluationFinding] = []
        repetition_penalty = 0.0

        hook_repeats = recent_hooks.count(genome.hook_structure)
        title_repeats = recent_titles.count(genome.title_pattern)
        if hook_repeats >= 3:
            repetition_penalty += min(0.35, hook_repeats * 0.07)
            findings.append(
                _finding(
                    "novelty.hook-repeated",
                    f"Hook structure appeared {hook_repeats} times in the recent channel window.",
                    EvaluationVerdict.WARN,
                    0.95,
                    repair_hint="Use a materially different opening strategy.",
                )
            )
        if title_repeats >= 3:
            repetition_penalty += min(0.25, title_repeats * 0.05)
            findings.append(
                _finding(
                    "novelty.title-repeated",
                    f"Title pattern appeared {title_repeats} times in the recent channel window.",
                    EvaluationVerdict.WARN,
                    0.95,
                    repair_hint="Change the information gap, not only individual words.",
                )
            )

        if not findings:
            findings.append(
                _finding(
                    "novelty.clear",
                    "Candidate does not repeat the recent hook or title pattern excessively.",
                    EvaluationVerdict.PASS,
                    0.78,
                )
            )

        utility = max(0.0, min(1.0, genome.novelty_score - repetition_penalty))
        return CandidateEvaluation(
            evaluation_id=_evaluation_id(self.evaluator_id, candidate.candidate_id, self.version),
            candidate_id=candidate.candidate_id,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.version,
            findings=tuple(findings),
            utility=utility,
        )


DEFAULT_EVALUATORS: Tuple[Evaluator, ...] = (
    HardConstraintEvaluator(),
    PromiseIntegrityEvaluator(),
    FirstSecondsEvaluator(),
    FeasibilityEvaluator(),
    NoveltyEvaluator(),
)


@dataclass(frozen=True)
class TournamentBundle:
    result: TournamentResult
    evaluations: Tuple[CandidateEvaluation, ...]


class CandidateTournament:
    """Run independent evaluators and preserve all blocked and rejected alternatives."""

    def __init__(self, evaluators: Sequence[Evaluator] = DEFAULT_EVALUATORS) -> None:
        if not evaluators:
            raise ContractError("candidate tournament requires at least one evaluator")
        evaluator_ids = [item.evaluator_id for item in evaluators]
        if len(evaluator_ids) != len(set(evaluator_ids)):
            raise ContractError("evaluator ids must be unique")
        self.evaluators = tuple(evaluators)

    def run(
        self,
        candidates: Sequence[Candidate],
        context: EvaluationContext,
        *,
        tournament_id: Optional[str] = None,
    ) -> TournamentBundle:
        if not candidates:
            raise ContractError("candidate tournament requires at least one candidate")
        ensure_unique_ids(candidates, "candidate_id")
        hypothesis_ids = {candidate.hypothesis_id for candidate in candidates}
        if len(hypothesis_ids) != 1:
            raise ContractError("one tournament may compare only one editorial hypothesis")

        evaluations: List[CandidateEvaluation] = []
        by_candidate: Dict[str, List[CandidateEvaluation]] = {
            candidate.candidate_id: [] for candidate in candidates
        }
        for candidate in candidates:
            for evaluator in self.evaluators:
                evaluation = evaluator.evaluate(candidate, context)
                evaluations.append(evaluation)
                by_candidate[candidate.candidate_id].append(evaluation)

        utilities: Dict[str, float] = {}
        reasons: Dict[str, Tuple[str, ...]] = {}
        blocked: List[str] = []
        ranked: List[Tuple[float, str]] = []

        for candidate in candidates:
            candidate_evaluations = by_candidate[candidate.candidate_id]
            reason_lines = []
            is_blocked = any(evaluation.blocked for evaluation in candidate_evaluations)
            for evaluation in candidate_evaluations:
                for finding in evaluation.findings:
                    reason_lines.append(
                        f"{evaluation.evaluator_id}:{finding.verdict.value}:{finding.code} — "
                        f"{finding.message}"
                    )
            reasons[candidate.candidate_id] = tuple(reason_lines)

            component_utilities = [
                evaluation.utility
                for evaluation in candidate_evaluations
                if evaluation.utility is not None
            ]
            base_value = candidate.estimated_value / (1.0 + candidate.estimated_value)
            aggregate = (
                mean(component_utilities + [base_value])
                if component_utilities
                else base_value
            )
            aggregate = round(max(0.0, min(1.0, aggregate)), 6)
            utilities[candidate.candidate_id] = aggregate

            if is_blocked:
                blocked.append(candidate.candidate_id)
            else:
                ranked.append((aggregate, candidate.candidate_id))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        ranked_ids = tuple(item[1] for item in ranked)
        blocked_ids = tuple(sorted(blocked))
        selected = ranked_ids[0] if ranked_ids else None
        final_tournament_id = tournament_id or (
            f"tournament-{stable_hash([item.candidate_id for item in candidates])[:16]}"
        )
        result = TournamentResult(
            tournament_id=final_tournament_id,
            ranked_candidate_ids=ranked_ids,
            blocked_candidate_ids=blocked_ids,
            utilities=utilities,
            reasons=reasons,
            evaluator_versions={
                evaluator.evaluator_id: evaluator.version for evaluator in self.evaluators
            },
            selected_candidate_id=selected,
        )
        return TournamentBundle(result=result, evaluations=tuple(evaluations))


@dataclass(frozen=True)
class CalibrationObservation:
    evaluator_id: str
    predicted_probability: float
    outcome: bool
    context_key: str
    observed_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not 0.0 <= self.predicted_probability <= 1.0:
            raise ContractError("predicted_probability must be between 0 and 1")


class CalibrationTracker:
    """Track evaluator confidence quality without granting automatic authority."""

    def __init__(self) -> None:
        self._observations: List[CalibrationObservation] = []

    def add(self, observation: CalibrationObservation) -> None:
        self._observations.append(observation)

    def brier_score(self, evaluator_id: str, *, minimum_observations: int = 10) -> Optional[float]:
        values = [
            item
            for item in self._observations
            if item.evaluator_id == evaluator_id
        ]
        if len(values) < minimum_observations:
            return None
        score = mean(
            (item.predicted_probability - (1.0 if item.outcome else 0.0)) ** 2
            for item in values
        )
        return round(score, 6)

    def count(self, evaluator_id: str) -> int:
        return sum(item.evaluator_id == evaluator_id for item in self._observations)
