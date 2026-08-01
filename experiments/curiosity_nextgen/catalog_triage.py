"""Story triage and readiness scoring for the dormant next-generation lab.

This module turns raw story health signals into a deterministic recommendation:
research, author, rewrite, draft-render, quarantine, or production-candidate
review.  It does not mutate the active story catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class TriageAction(str, Enum):
    RESEARCH = "research"
    AUTHOR = "author"
    REWRITE = "rewrite"
    RENDER_DRAFT = "render_draft"
    REVIEW_CANDIDATE = "review_candidate"
    QUARANTINE = "quarantine"
    RETIRE = "retire"


class BlockerSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class StoryBlocker:
    code: str
    severity: BlockerSeverity
    beat_id: str | None = None
    repairable: bool = True


@dataclass(frozen=True)
class StorySignals:
    slug: str
    factual_mode_present: bool
    research_coverage: float
    claim_coverage: float
    visual_plan_coverage: float
    hook_score: float
    payoff_score: float
    novelty_score: float
    personality_score: float
    renderability: float
    estimated_render_seconds: float
    expected_cache_hit_rate: float
    blockers: tuple[StoryBlocker, ...] = ()
    previous_failed_repairs: int = 0
    retired: bool = False

    def __post_init__(self) -> None:
        for name in (
            "research_coverage",
            "claim_coverage",
            "visual_plan_coverage",
            "novelty_score",
            "renderability",
            "expected_cache_hit_rate",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in ("hook_score", "payoff_score", "personality_score"):
            value = getattr(self, name)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"{name} must be between 0 and 10")
        if self.estimated_render_seconds < 0:
            raise ValueError("estimated_render_seconds cannot be negative")
        if self.previous_failed_repairs < 0:
            raise ValueError("previous_failed_repairs cannot be negative")


@dataclass(frozen=True)
class TriagePolicy:
    minimum_research: float = 0.85
    minimum_claim_coverage: float = 1.0
    minimum_visual_plan: float = 0.75
    minimum_renderability: float = 0.72
    minimum_hook: float = 7.0
    minimum_payoff: float = 7.0
    minimum_personality: float = 4.0
    minimum_novelty: float = 0.55
    production_readiness_score: float = 78.0
    draft_readiness_score: float = 62.0
    maximum_failed_repairs: int = 2
    maximum_draft_seconds: float = 480.0


@dataclass(frozen=True)
class StoryTriage:
    slug: str
    action: TriageAction
    readiness_score: float
    hard_blockers: tuple[str, ...]
    soft_gaps: tuple[str, ...]
    strengths: tuple[str, ...]
    recommended_repairs: tuple[str, ...]


_WEIGHTS = {
    "research": 18.0,
    "claims": 18.0,
    "visual_plan": 15.0,
    "hook": 11.0,
    "payoff": 10.0,
    "novelty": 8.0,
    "personality": 8.0,
    "renderability": 8.0,
    "cache": 4.0,
}


def _score(signals: StorySignals) -> float:
    components = {
        "research": signals.research_coverage,
        "claims": signals.claim_coverage,
        "visual_plan": signals.visual_plan_coverage,
        "hook": signals.hook_score / 10.0,
        "payoff": signals.payoff_score / 10.0,
        "novelty": signals.novelty_score,
        "personality": signals.personality_score / 10.0,
        "renderability": signals.renderability,
        "cache": signals.expected_cache_hit_rate,
    }
    raw = sum(_WEIGHTS[name] * components[name] for name in _WEIGHTS)
    high_penalty = sum(6.0 for item in signals.blockers if item.severity is BlockerSeverity.HIGH)
    critical_penalty = sum(18.0 for item in signals.blockers if item.severity is BlockerSeverity.CRITICAL)
    repair_penalty = min(12.0, signals.previous_failed_repairs * 4.0)
    return round(max(0.0, min(100.0, raw - high_penalty - critical_penalty - repair_penalty)), 1)


def triage_story(signals: StorySignals, *, policy: TriagePolicy | None = None) -> StoryTriage:
    policy = policy or TriagePolicy()
    score = _score(signals)
    hard: list[str] = []
    soft: list[str] = []
    strengths: list[str] = []
    repairs: list[str] = []

    if signals.retired:
        return StoryTriage(signals.slug, TriageAction.RETIRE, score, (), (), ("explicitly_retired",), ())

    if not signals.factual_mode_present:
        hard.append("missing_factual_mode")
        repairs.append("declare_factual_mode")
    if signals.research_coverage < policy.minimum_research:
        soft.append("research_incomplete")
        repairs.append("expand_research_package")
    else:
        strengths.append("research_ready")
    if signals.claim_coverage < policy.minimum_claim_coverage:
        hard.append("claim_coverage_incomplete")
        repairs.append("map_all_detected_claims")
    else:
        strengths.append("claims_fully_mapped")
    if signals.visual_plan_coverage < policy.minimum_visual_plan:
        soft.append("visual_plan_incomplete")
        repairs.append("author_missing_visual_beats")
    else:
        strengths.append("visual_plan_ready")
    if signals.renderability < policy.minimum_renderability:
        soft.append("low_renderability")
        repairs.append("replace_unsupported_scene_types")
    else:
        strengths.append("renderer_compatible")
    if signals.hook_score < policy.minimum_hook:
        soft.append("weak_hook")
        repairs.append("rewrite_opening_hook")
    else:
        strengths.append("strong_hook")
    if signals.payoff_score < policy.minimum_payoff:
        soft.append("weak_payoff")
        repairs.append("strengthen_payoff")
    else:
        strengths.append("strong_payoff")
    if signals.personality_score < policy.minimum_personality:
        soft.append("low_personality")
        repairs.append("increase_character_specificity")
    if signals.novelty_score < policy.minimum_novelty:
        soft.append("low_novelty")
        repairs.append("differentiate_visual_grammar")
    if signals.estimated_render_seconds > policy.maximum_draft_seconds:
        soft.append("draft_cost_too_high")
        repairs.append("simplify_draft_profile_or_raise_cache_reuse")

    for blocker in signals.blockers:
        label = f"story_blocker:{blocker.code}"
        if blocker.severity in {BlockerSeverity.CRITICAL, BlockerSeverity.HIGH}:
            hard.append(label)
        else:
            soft.append(label)
        if blocker.repairable:
            repairs.append(f"repair:{blocker.code}")

    critical = any(item.severity is BlockerSeverity.CRITICAL for item in signals.blockers)
    if critical or signals.previous_failed_repairs > policy.maximum_failed_repairs:
        action = TriageAction.QUARANTINE
        if signals.previous_failed_repairs > policy.maximum_failed_repairs:
            hard.append("repair_budget_exhausted")
    elif hard:
        if "missing_factual_mode" in hard or "claim_coverage_incomplete" in hard:
            action = TriageAction.RESEARCH
        else:
            action = TriageAction.REWRITE
    elif score >= policy.production_readiness_score and not soft:
        action = TriageAction.REVIEW_CANDIDATE
    elif score >= policy.draft_readiness_score:
        action = TriageAction.RENDER_DRAFT
    elif signals.research_coverage < policy.minimum_research:
        action = TriageAction.RESEARCH
    elif signals.visual_plan_coverage < policy.minimum_visual_plan:
        action = TriageAction.AUTHOR
    else:
        action = TriageAction.REWRITE

    return StoryTriage(
        slug=signals.slug,
        action=action,
        readiness_score=score,
        hard_blockers=tuple(sorted(set(hard))),
        soft_gaps=tuple(sorted(set(soft))),
        strengths=tuple(sorted(set(strengths))),
        recommended_repairs=tuple(dict.fromkeys(repairs)),
    )


def rank_triage(results: Iterable[StoryTriage]) -> tuple[StoryTriage, ...]:
    action_priority = {
        TriageAction.REVIEW_CANDIDATE: 0,
        TriageAction.RENDER_DRAFT: 1,
        TriageAction.AUTHOR: 2,
        TriageAction.RESEARCH: 3,
        TriageAction.REWRITE: 4,
        TriageAction.QUARANTINE: 5,
        TriageAction.RETIRE: 6,
    }
    return tuple(sorted(results, key=lambda item: (action_priority[item.action], -item.readiness_score, item.slug)))
