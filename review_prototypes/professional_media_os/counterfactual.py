"""Counterfactual preview comparisons for the isolated prototype.

The module does not claim to forecast platform performance. It provides a contract for
comparing controlled creative changes and preserving uncertainty, model version, and
training-data maturity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Mapping, Optional, Protocol, Sequence, Tuple

from .contracts import Candidate, ContentGenome, ContractError, stable_hash


@dataclass(frozen=True)
class Prediction:
    predictor_id: str
    predictor_version: str
    candidate_id: str
    expected_utility: float
    lower_bound: float
    upper_bound: float
    maturity_label: str
    components: Mapping[str, float]
    warnings: Tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("expected_utility", "lower_bound", "upper_bound"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ContractError(f"{name} must be between 0 and 1")
        if self.lower_bound > self.expected_utility or self.expected_utility > self.upper_bound:
            raise ContractError("prediction bounds must contain the expected utility")


class Predictor(Protocol):
    predictor_id: str
    version: str

    def predict(self, candidate: Candidate) -> Prediction:
        ...


class TransparentHeuristicPredictor:
    """Visible baseline used only to exercise the counterfactual contract."""

    predictor_id = "transparent-heuristic"
    version = "1.0.0"

    def predict(self, candidate: Candidate) -> Prediction:
        genome = candidate.genome
        proof_timing = 0.35
        warnings = [
            "Reference heuristic only; it is not calibrated to live audience outcomes.",
        ]
        if genome.first_proof_ms is not None:
            proof_timing = max(0.0, 1.0 - genome.first_proof_ms / 8000.0)
        else:
            warnings.append("First proof time is unknown.")

        subject_timing = max(0.0, 1.0 - genome.first_subject_ms / 3000.0)
        pacing = max(0.0, min(1.0, 1.0 - abs(genome.average_shot_seconds - 1.5) / 4.0))
        reveal = max(0.0, min(1.0, 1.0 - abs(genome.reveal_position - 0.72) / 0.72))
        components = {
            "evidence": genome.evidence_completeness,
            "media_feasibility": genome.media_feasibility,
            "novelty": genome.novelty_score,
            "proof_timing": proof_timing,
            "subject_timing": subject_timing,
            "pacing": pacing,
            "reveal_position": reveal,
        }
        expected = sum(components.values()) / len(components)
        uncertainty = 0.25
        return Prediction(
            predictor_id=self.predictor_id,
            predictor_version=self.version,
            candidate_id=candidate.candidate_id,
            expected_utility=round(expected, 6),
            lower_bound=round(max(0.0, expected - uncertainty), 6),
            upper_bound=round(min(1.0, expected + uncertainty), 6),
            maturity_label="uncalibrated-reference",
            components=components,
            warnings=tuple(warnings),
        )


@dataclass(frozen=True)
class CounterfactualChange:
    name: str
    genome_updates: Mapping[str, object]
    rationale: str


@dataclass(frozen=True)
class CounterfactualResult:
    scenario_id: str
    change_name: str
    baseline_prediction: Prediction
    changed_prediction: Prediction
    expected_delta: float
    interval_overlap: bool
    decision_note: str


class CounterfactualRunner:
    def __init__(self, predictor: Predictor) -> None:
        self.predictor = predictor

    def run(
        self,
        candidate: Candidate,
        changes: Sequence[CounterfactualChange],
    ) -> Tuple[CounterfactualResult, ...]:
        if not changes:
            raise ContractError("at least one counterfactual change is required")
        baseline = self.predictor.predict(candidate)
        results = []
        for index, change in enumerate(changes, start=1):
            changed_genome = self._replace_genome(candidate.genome, change.genome_updates)
            changed_candidate = replace(
                candidate,
                candidate_id=f"{candidate.candidate_id}-cf{index}",
                genome=changed_genome,
                parent_candidate_id=candidate.candidate_id,
            )
            prediction = self.predictor.predict(changed_candidate)
            delta = prediction.expected_utility - baseline.expected_utility
            overlap = not (
                prediction.lower_bound > baseline.upper_bound
                or baseline.lower_bound > prediction.upper_bound
            )
            if overlap:
                note = (
                    "Prediction intervals overlap; treat this as a preview hypothesis, not a winner."
                )
            elif delta > 0:
                note = "Changed scenario is directionally stronger under this predictor."
            else:
                note = "Changed scenario is directionally weaker under this predictor."
            results.append(
                CounterfactualResult(
                    scenario_id=f"scenario-{stable_hash((candidate.candidate_id, change.name, index))[:16]}",
                    change_name=change.name,
                    baseline_prediction=baseline,
                    changed_prediction=prediction,
                    expected_delta=round(delta, 6),
                    interval_overlap=overlap,
                    decision_note=note,
                )
            )
        return tuple(results)

    @staticmethod
    def _replace_genome(
        genome: ContentGenome,
        updates: Mapping[str, object],
    ) -> ContentGenome:
        allowed_fields = set(genome.__dataclass_fields__)
        unknown = sorted(set(updates).difference(allowed_fields))
        if unknown:
            raise ContractError(f"unknown genome fields in counterfactual: {unknown}")
        protected = {"genome_id", "channel_id", "schema_version", "created_at"}
        forbidden = sorted(set(updates).intersection(protected))
        if forbidden:
            raise ContractError(f"counterfactual cannot alter identity fields: {forbidden}")
        new_id = f"{genome.genome_id}-cf-{stable_hash(updates)[:10]}"
        return replace(genome, genome_id=new_id, **dict(updates))
