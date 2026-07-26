from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Mapping

from .content_models import ContentDomain, Dataset, PremiseCandidate, Relationship


_TENSION_RE = re.compile(
    r"\b(but|actually|instead|even though|despite|more than|less than|twice|half|"
    r"hidden|wrong|myth|never|still|only|bigger|smaller|faster|slower|older|you think)\b",
    re.I,
)
_NUMBER_RE = re.compile(r"\d")
_GENERIC_TITLE_RE = re.compile(r"^[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,4}$")


DOMAIN_KEYWORDS: Mapping[ContentDomain, frozenset[str]] = {
    ContentDomain.SCIENCE: frozenset({"science", "physics", "chemical", "element", "energy", "temperature"}),
    ContentDomain.SPACE: frozenset({"space", "planet", "star", "moon", "galaxy", "orbit", "universe"}),
    ContentDomain.NATURE: frozenset({"animal", "ocean", "forest", "species", "nature", "earth", "climate"}),
    ContentDomain.HUMAN_BODY: frozenset({"body", "brain", "blood", "heart", "human", "cell", "organ"}),
    ContentDomain.HISTORY: frozenset({"history", "ancient", "war", "empire", "century", "year"}),
    ContentDomain.GEOGRAPHY: frozenset({"country", "city", "continent", "population", "land", "map"}),
    ContentDomain.TECHNOLOGY: frozenset({"technology", "computer", "chip", "internet", "robot", "ai"}),
    ContentDomain.ECONOMICS: frozenset({"price", "cost", "income", "wage", "rent", "mortgage", "inflation", "money"}),
}

FINANCE_WORDS = DOMAIN_KEYWORDS[ContentDomain.ECONOMICS]
VISUAL_WORDS = frozenset(
    {"rise", "fall", "grow", "shrink", "rank", "share", "double", "half", "largest", "smallest", "faster", "slower"}
)


@dataclass(frozen=True)
class PremisePolicy:
    minimum_score: float = 68.0
    dry_economics_penalty: float = 18.0
    generic_title_penalty: float = 24.0
    repeated_pattern_penalty: float = 10.0
    require_number: bool = True
    require_reversal: bool = True


def infer_domain(*texts: str) -> ContentDomain:
    tokens = set(re.findall(r"[a-z]+", " ".join(texts).lower()))
    best = (0, ContentDomain.GENERAL)
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = len(tokens & keywords)
        if score > best[0]:
            best = (score, domain)
    return best[1]


def infer_relationship(dataset: Dataset) -> Relationship:
    labels = [point.label for point in dataset.points]
    numeric_labels = sum(bool(re.fullmatch(r"(?:19|20)\d{2}", label.strip())) for label in labels)
    if numeric_labels >= max(2, len(labels) // 2):
        return Relationship.TREND
    if dataset.baseline is not None:
        return Relationship.COMPARISON
    if dataset.unit.lower() in {"percent", "percentage", "%", "share"} and max(
        point.value for point in dataset.points
    ) <= 100:
        return Relationship.PART_TO_WHOLE
    if len(dataset.points) == 2:
        return Relationship.COMPARISON
    return Relationship.RANKING


def hero_point(dataset: Dataset):
    if dataset.baseline is not None:
        return max(dataset.points, key=lambda point: abs(point.value - dataset.baseline.value))
    values = [point.value for point in dataset.points]
    midpoint = (min(values) + max(values)) / 2
    return max(dataset.points, key=lambda point: abs(point.value - midpoint))


def _format_value(value: float, unit: str) -> str:
    rounded = int(value) if float(value).is_integer() else round(value, 1)
    lower = unit.lower()
    if lower in {"percent", "percentage", "%"}:
        return f"{rounded}%"
    if lower in {"dollars", "usd", "$"}:
        return f"${rounded:,}"
    return f"{rounded:,} {unit}".strip()


def generate_candidates(dataset: Dataset, *, count: int = 6) -> tuple[PremiseCandidate, ...]:
    hero = hero_point(dataset)
    relationship = infer_relationship(dataset)
    domain = infer_domain(dataset.title, dataset.notes, " ".join(point.label for point in dataset.points))
    value = _format_value(hero.value, dataset.unit)
    baseline = dataset.baseline
    baseline_phrase = (
        f" while the baseline is {_format_value(baseline.value, dataset.unit)}"
        if baseline is not None
        else ""
    )
    templates = [
        (
            f"{hero.label} Didn't Just Change — It Hit {value}",
            f"You think {dataset.title.lower()} moved a little. {hero.label} reached {value}{baseline_phrase}.",
            "the change was modest",
            f"the standout value is {value}",
            "the scale is large enough to change how the viewer understands the subject",
            "expectation_reversal",
        ),
        (
            f"The {value} Number Hiding Inside {dataset.title}",
            f"The number most people miss is {value}: {hero.label}{baseline_phrase}.",
            "the headline tells the whole story",
            "one value dominates the interpretation",
            "the hidden number provides a specific reveal",
            "hidden_number",
        ),
        (
            f"Why {hero.label} Is the Outlier at {value}",
            f"Most of this chart looks normal. Then {hero.label} jumps to {value}.",
            "the categories move together",
            f"{hero.label} separates at {value}",
            "the outlier creates an immediate visual contrast",
            "outlier_reveal",
        ),
        (
            f"{dataset.title}: The Part Everyone Underestimates",
            f"The part everyone underestimates is {hero.label}: {value}.",
            "the familiar explanation is sufficient",
            f"{hero.label} carries the consequential value {value}",
            "the viewer gets a concrete correction rather than trivia",
            "underestimated_part",
        ),
        (
            f"This Chart Changes When {hero.label} Hits {value}",
            f"Watch the chart when {hero.label} reaches {value}. The whole comparison changes.",
            "the ranking is stable",
            "one value changes the visual hierarchy",
            "the reveal is naturally animated",
            "chart_turn",
        ),
        (
            f"{value} Is Bigger Than It Sounds",
            f"{value} sounds abstract until you compare {hero.label} with everything else.",
            "the number is easy to dismiss",
            "the comparison makes its scale obvious",
            "the story converts an abstract value into a visible relationship",
            "scale_translation",
        ),
    ]
    candidates: list[PremiseCandidate] = []
    for index, (title, hook, expectation, reversal, stakes, visual) in enumerate(templates[:count]):
        digest = hashlib.sha1(f"{dataset.key}:{index}:{title}".encode()).hexdigest()[:10]
        candidates.append(
            PremiseCandidate(
                candidate_id=f"premise-{digest}",
                title=title,
                hook=hook,
                expectation=expectation,
                reversal=reversal,
                stakes=stakes,
                hero_number=hero.value,
                hero_label=hero.label,
                unit=dataset.unit,
                domain=domain,
                relationship=relationship,
                visual_form=visual,
            )
        )
    return tuple(candidates)


def score_candidate(
    candidate: PremiseCandidate,
    dataset: Dataset,
    *,
    policy: PremisePolicy | None = None,
    recent_patterns: Iterable[str] = (),
) -> PremiseCandidate:
    policy = policy or PremisePolicy()
    combined = f"{candidate.title} {candidate.hook} {candidate.expectation} {candidate.reversal} {candidate.stakes}"
    lower = combined.lower()
    components: dict[str, float] = {}
    reasons: list[str] = []
    rejections: list[str] = []

    components["specificity"] = 18.0 if _NUMBER_RE.search(combined) else 0.0
    if components["specificity"]:
        reasons.append("contains a consequential number")
    elif policy.require_number:
        rejections.append("premise has no consequential number")

    has_reversal = bool(_TENSION_RE.search(combined)) or bool(candidate.expectation and candidate.reversal)
    components["reversal"] = 22.0 if has_reversal else 4.0
    if has_reversal:
        reasons.append("states an expectation and reversal")
    elif policy.require_reversal:
        rejections.append("premise lacks a clear expectation reversal")

    hero_values = [point.value for point in dataset.points]
    spread = max(hero_values) - min(hero_values)
    denom = max(abs(max(hero_values)), abs(min(hero_values)), 1.0)
    spread_ratio = min(1.0, spread / denom)
    components["data_tension"] = round(8.0 + 14.0 * spread_ratio, 2)
    if spread_ratio >= 0.35:
        reasons.append("dataset contains a strong visible contrast")

    visual_tokens = set(re.findall(r"[a-z]+", lower))
    components["visualizability"] = 16.0 if (visual_tokens & VISUAL_WORDS or candidate.visual_form) else 6.0
    stakes_words = {"changes", "cost", "risk", "scale", "dominates", "outlier", "underestimates", "whole"}
    components["stakes"] = 14.0 if visual_tokens & stakes_words or len(candidate.stakes.split()) >= 8 else 7.0

    source_score = {"official": 10.0, "primary": 9.0, "secondary": 7.0}.get(
        dataset.source.officiality.value, 0.0
    )
    components["source_strength"] = source_score
    if source_score == 0:
        rejections.append("dataset source is not publishable")

    penalty = 0.0
    title_words = candidate.title.split()
    if (
        len(title_words) <= 5
        and _GENERIC_TITLE_RE.fullmatch(candidate.title)
        and not _NUMBER_RE.search(candidate.title)
        and not _TENSION_RE.search(candidate.title)
    ):
        penalty += policy.generic_title_penalty
        rejections.append("title reads like a generic searchable noun phrase")

    finance_hits = len(visual_tokens & FINANCE_WORDS)
    if candidate.domain == ContentDomain.ECONOMICS and finance_hits >= 2 and not has_reversal:
        penalty += policy.dry_economics_penalty
        rejections.append("dry economics premise without a counterintuitive angle")

    if candidate.visual_form in set(recent_patterns):
        penalty += policy.repeated_pattern_penalty
        reasons.append("penalized for repeating a recent premise pattern")

    total = round(max(0.0, min(100.0, sum(components.values()) - penalty)), 2)
    if total < policy.minimum_score:
        rejections.append(f"score {total:.1f} is below minimum {policy.minimum_score:.1f}")
    return PremiseCandidate(
        **{
            **candidate.__dict__,
            "score": total,
            "score_reasons": tuple(reasons),
            "rejection_reasons": tuple(dict.fromkeys(rejections)),
        }
    )


def rank_candidates(
    dataset: Dataset,
    *,
    policy: PremisePolicy | None = None,
    recent_patterns: Iterable[str] = (),
    count: int = 6,
) -> tuple[PremiseCandidate, ...]:
    scored = [
        score_candidate(candidate, dataset, policy=policy, recent_patterns=recent_patterns)
        for candidate in generate_candidates(dataset, count=count)
    ]
    return tuple(sorted(scored, key=lambda item: (item.eligible, item.score), reverse=True))
