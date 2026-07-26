from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Sequence

from .content_models import (
    ClaimBinding,
    ContentValidationError,
    Dataset,
    PremiseCandidate,
    Relationship,
    StoryBeat,
    StoryPackage,
    VisualIntent,
    numbers_supported,
)
from .premise_engine import PremisePolicy, hero_point, infer_relationship, rank_candidates


@dataclass(frozen=True)
class CompileRequest:
    slug: str
    datasets: tuple[Dataset, ...]
    target_seconds: float = 38.0
    recent_patterns: tuple[str, ...] = ()
    recent_performances: tuple[str, ...] = ()
    hashtags: tuple[str, ...] = ("data", "facts", "explained", "shorts")


@dataclass(frozen=True)
class CompileResult:
    story: StoryPackage
    rejected_premises: tuple[PremiseCandidate, ...]
    diagnostics: tuple[str, ...]


def _format_value(value: float, unit: str) -> str:
    rounded = int(value) if float(value).is_integer() else round(value, 1)
    if unit.lower() in {"percent", "percentage", "%"}:
        return f"{rounded}%"
    if unit.lower() in {"dollars", "usd", "$"}:
        return f"${rounded:,}"
    return f"{rounded:,} {unit}".strip()


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not value:
        raise ContentValidationError("slug cannot be empty")
    return value


def _claim_id(dataset: Dataset, labels: Sequence[str], role: str) -> str:
    digest = hashlib.sha1(f"{dataset.key}:{','.join(labels)}:{role}".encode()).hexdigest()[:10]
    return f"claim-{digest}"


def _make_claim(
    dataset: Dataset,
    labels: Sequence[str],
    text: str,
    relationship: Relationship,
    role: str,
) -> ClaimBinding:
    values = tuple(dataset.point(label).value for label in labels)
    claim = ClaimBinding(
        claim_id=_claim_id(dataset, labels, role),
        text=text,
        dataset_key=dataset.key,
        point_labels=tuple(labels),
        expected_numbers=values,
        relationship=relationship,
        unit=dataset.unit,
    )
    claim.validate_against(dataset)
    return claim


def _rank_claim(dataset: Dataset, role: str) -> ClaimBinding:
    ordered = sorted(dataset.points, key=lambda point: point.value, reverse=True)
    first = ordered[0]
    second = ordered[1] if len(ordered) > 1 else ordered[0]
    text = (
        f"{first.label} reaches {_format_value(first.value, dataset.unit)}, "
        f"compared with {second.label} at {_format_value(second.value, dataset.unit)}."
    )
    return _make_claim(dataset, (first.label, second.label), text, Relationship.RANKING, role)


def _baseline_claim(dataset: Dataset, role: str) -> ClaimBinding | None:
    if dataset.baseline is None:
        return None
    hero = hero_point(dataset)
    text = f"{hero.label} reaches {_format_value(hero.value, dataset.unit)}."
    return _make_claim(dataset, (hero.label,), text, Relationship.COMPARISON, role)


def _trend_claim(dataset: Dataset, role: str) -> ClaimBinding:
    first = dataset.points[0]
    last = dataset.points[-1]
    text = (
        f"The value moves from {_format_value(first.value, dataset.unit)} in {first.label} "
        f"to {_format_value(last.value, dataset.unit)} in {last.label}."
    )
    return _make_claim(dataset, (first.label, last.label), text, Relationship.TREND, role)


def _claim_for_dataset(dataset: Dataset, role: str) -> ClaimBinding:
    relationship = infer_relationship(dataset)
    if relationship == Relationship.TREND and len(dataset.points) >= 2:
        return _trend_claim(dataset, role)
    if dataset.baseline is not None:
        baseline_claim = _baseline_claim(dataset, role)
        if baseline_claim is not None:
            return baseline_claim
    return _rank_claim(dataset, role)


def _visual_for(claim: ClaimBinding, recent_performances: Iterable[str]) -> VisualIntent:
    recent = set(recent_performances)
    choices = {
        Relationship.TREND: [
            ("resist the moving endpoint", "the line pulls Data forward", "moving_endpoint"),
            ("climb the accelerating line", "Data loses footing at the steepest section", "path"),
            ("hold back the final point", "the endpoint breaks free", "moving_endpoint"),
        ],
        Relationship.RANKING: [
            ("stack the leading categories", "the largest block overwhelms the stack", "bar_face"),
            ("race the top two values", "the leader crosses first", "finish_line"),
            ("balance the ranking", "the largest value tips the platform", "beam"),
        ],
        Relationship.COMPARISON: [
            ("balance the two values", "the heavier side drops", "beam"),
            ("carry both values", "the larger one pulls Data sideways", "grip_points"),
            ("separate the two outcomes", "the gap becomes impossible to bridge", "gap"),
        ],
        Relationship.PART_TO_WHOLE: [
            ("hold the dominant share", "the majority spills over", "container"),
            ("assemble the whole", "one section occupies most of the frame", "slice_edge"),
            ("weigh the shares", "the dominant share pins the scale", "beam"),
        ],
    }
    options = choices.get(claim.relationship, choices[Relationship.COMPARISON])
    selected = next((option for option in options if option[0] not in recent), options[0])
    objective, payoff, affordance = selected
    return VisualIntent(
        relationship=claim.relationship,
        primary_focus=claim.point_labels[0],
        required_affordances=frozenset({affordance, "caption_safe_zone"}),
        forbidden_distortions=frozenset({"change_numeric_order", "invent_values", "hide_source_label"}),
        mascot_objective=objective,
        payoff=payoff,
    )


class StoryCompiler:
    def __init__(self, *, premise_policy: PremisePolicy | None = None) -> None:
        self.premise_policy = premise_policy or PremisePolicy()

    def compile(self, request: CompileRequest) -> CompileResult:
        if not request.datasets:
            raise ContentValidationError("compile request requires at least one dataset")
        slug = _slugify(request.slug)
        premise_rank = rank_candidates(
            request.datasets[0],
            policy=self.premise_policy,
            recent_patterns=request.recent_patterns,
        )
        premise = next((candidate for candidate in premise_rank if candidate.eligible), None)
        if premise is None:
            reasons = sorted(
                {reason for candidate in premise_rank for reason in candidate.rejection_reasons}
            )
            raise ContentValidationError("no premise cleared the editorial floor: " + "; ".join(reasons))

        claims: list[ClaimBinding] = []
        beats: list[StoryBeat] = []
        seconds_per_beat = max(4.0, min(9.0, request.target_seconds / max(len(request.datasets), 2)))
        for index, dataset in enumerate(request.datasets):
            role = "setup" if index == 0 else "escalation" if index < len(request.datasets) - 1 else "synthesis"
            claim = _claim_for_dataset(dataset, role)
            if not numbers_supported(claim.text, claim.expected_numbers):
                raise ContentValidationError(f"claim {claim.claim_id} contains unsupported numbers")
            claims.append(claim)
            visual = _visual_for(claim, request.recent_performances)
            narration = claim.text
            if index == 0:
                narration = f"{premise.hook} {claim.text}"
            elif index == len(request.datasets) - 1:
                narration = f"Here is what changes the story: {claim.text}"
            beats.append(
                StoryBeat(
                    beat_id=f"segment_{index}",
                    role=role,
                    narration=narration,
                    claim_ids=(claim.claim_id,),
                    visual=visual,
                    estimated_seconds=seconds_per_beat,
                )
            )

        if len(beats) == 1:
            only = beats[0]
            beats.append(
                StoryBeat(
                    beat_id="segment_1",
                    role="synthesis",
                    narration=(
                        f"Now put that in context: {claims[0].text} "
                        "That is the reversal the chart makes visible."
                    ),
                    claim_ids=(claims[0].claim_id,),
                    visual=VisualIntent(
                        relationship=only.visual.relationship,
                        primary_focus=only.visual.primary_focus,
                        required_affordances=only.visual.required_affordances,
                        forbidden_distortions=only.visual.forbidden_distortions,
                        mascot_objective="translate the number into a final comparison",
                        payoff="the final relationship lands and Data reacts",
                    ),
                    estimated_seconds=seconds_per_beat,
                )
            )

        hero = hero_point(request.datasets[0])
        closing = (
            f"The number to remember is {_format_value(hero.value, request.datasets[0].unit)} — "
            f"because it changes how {request.datasets[0].title.lower()} looks."
        )
        question = f"Which part of {request.datasets[0].title.lower()} surprised you most?"
        story = StoryPackage(
            slug=slug,
            premise=premise,
            datasets=request.datasets,
            claims=tuple(claims),
            beats=tuple(beats),
            closing=closing,
            question=question,
            hashtags=tuple(dict.fromkeys((*request.hashtags, premise.domain.value, premise.relationship.value))),
        )
        story.validate()
        return CompileResult(
            story=story,
            rejected_premises=tuple(candidate for candidate in premise_rank if candidate != premise),
            diagnostics=(
                f"selected premise {premise.candidate_id} at {premise.score:.1f}",
                f"compiled {len(claims)} source-bound claims",
                f"estimated duration {story.estimated_seconds:.1f}s",
            ),
        )
