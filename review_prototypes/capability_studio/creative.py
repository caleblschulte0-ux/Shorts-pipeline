from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Mapping, Sequence

from .contracts import ChannelProfile, CreativeVariant, ScoreCard, stable_id


@dataclass(frozen=True)
class CandidateSet:
    premise: str
    hooks: tuple[CreativeVariant, ...]
    titles: tuple[CreativeVariant, ...]
    structures: tuple[CreativeVariant, ...]
    openings: tuple[CreativeVariant, ...]
    endings: tuple[CreativeVariant, ...]


class CandidateStudio:
    def create(self, premise: str, *, subject: str = "This", fact: str = "the result") -> CandidateSet:
        premise = premise.strip()
        hooks = (self._variant("hook", f"{subject} did WHAT?", "Reveal the surprising result immediately", "question"), self._variant("hook", f"{subject} quietly changed everything.", "Before/after evidence in frame one", "reveal"), self._variant("hook", "You were never supposed to notice this.", "Show the hidden mechanism before context", "conflict"), self._variant("hook", f"The number nobody expected: {fact}.", "Large number with an immediate visual comparison", "number"), self._variant("hook", "This looks normal. It isn't.", "Normal image snaps into an annotated evidence view", "pattern-break"))
        titles = (self._variant("title", premise[:90], structure="direct"), self._variant("title", f"The hidden reason behind {subject}", structure="curiosity"), self._variant("title", "What changed — and why it matters", structure="explanation"))
        structures = (self._variant("structure", "Result → evidence → mechanism → consequence", structure="reverse-pyramid"), self._variant("structure", "Question → failed assumption → reveal → proof", structure="mystery"))
        openings = (self._variant("opening", "Side-by-side before and after", "Use exact evidence with a hard visual contrast", "comparison"), self._variant("opening", "One large number over real footage", "Keep the subject visible behind the number", "single-stat"))
        endings = (self._variant("ending", "Return to the opening image with the new meaning exposed", structure="callback"), self._variant("ending", "Show the practical consequence and ask one specific question", structure="consequence-question"))
        return CandidateSet(premise, hooks, titles, structures, openings, endings)

    @staticmethod
    def _variant(kind: str, text: str, visual_brief: str = "", structure: str = "") -> CreativeVariant:
        payload = {"kind": kind, "text": text, "visual": visual_brief, "structure": structure}
        return CreativeVariant(stable_id(kind, payload), kind, text, visual_brief, structure)


@dataclass(frozen=True)
class TournamentResult:
    winner_id: str | None
    ranked_ids: tuple[str, ...]
    rejected: Mapping[str, tuple[str, ...]]
    totals: Mapping[str, float]


class CandidateTournament:
    def rank(self, candidates: Sequence[CreativeVariant], scorecards: Sequence[ScoreCard], weights: Mapping[str, float]) -> TournamentResult:
        by_id = {score.candidate_id: score for score in scorecards}
        rejected: dict[str, tuple[str, ...]] = {}
        totals: dict[str, float] = {}
        for candidate in candidates:
            score = by_id.get(candidate.variant_id)
            if score is None:
                rejected[candidate.variant_id] = ("missing_scorecard",)
                continue
            if score.hard_failures:
                rejected[candidate.variant_id] = score.hard_failures
                continue
            totals[candidate.variant_id] = score.weighted_total(weights) - candidate.estimated_cost
        ranked = tuple(sorted(totals, key=lambda candidate_id: totals[candidate_id], reverse=True))
        return TournamentResult(ranked[0] if ranked else None, ranked, rejected, totals)


@dataclass(frozen=True)
class Idea:
    idea_id: str
    title: str
    summary: str
    topic_tags: tuple[str, ...]
    format_hints: tuple[str, ...]


@dataclass(frozen=True)
class RouteDecision:
    idea_id: str
    channel: str | None
    score: float
    reasons: tuple[str, ...]
    duplicate_of: str | None = None


class GlobalIdeaRouter:
    def route(self, idea: Idea, channels: Sequence[ChannelProfile], prior_ideas: Sequence[Idea] = ()) -> RouteDecision:
        duplicate = self.find_duplicate(idea, prior_ideas)
        if duplicate is not None: return RouteDecision(idea.idea_id, None, 0.0, ("semantic_duplicate",), duplicate.idea_id)
        best_channel: str | None = None
        best_score = float("-inf")
        best_reasons: tuple[str, ...] = ()
        for profile in channels:
            topic_matches = len(set(idea.topic_tags) & set(profile.accepted_topics))
            format_matches = len(set(idea.format_hints) & set(profile.preferred_formats))
            forbidden = set(idea.topic_tags) & set(profile.forbidden_topics)
            score = topic_matches * 3 + format_matches * 2 - len(forbidden) * 100
            reasons = (f"topic_matches={topic_matches}", f"format_matches={format_matches}", f"forbidden={len(forbidden)}")
            if score > best_score: best_channel, best_score, best_reasons = profile.channel, score, reasons
        return RouteDecision(idea.idea_id, best_channel if best_score > 0 else None, best_score, best_reasons)

    def find_duplicate(self, idea: Idea, prior_ideas: Sequence[Idea], *, threshold: float = 0.84) -> Idea | None:
        target = self._normalized(idea.title + " " + idea.summary)
        for prior in prior_ideas:
            if SequenceMatcher(None, target, self._normalized(prior.title + " " + prior.summary)).ratio() >= threshold: return prior
        return None

    @staticmethod
    def _normalized(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


@dataclass(frozen=True)
class PacingDecision:
    second: float
    action: str
    reason: str


class PacingOptimizer:
    def plan(self, duration: float, beats: Sequence[Mapping[str, object]], *, max_static_seconds: float = 2.0) -> tuple[PacingDecision, ...]:
        decisions: list[PacingDecision] = []
        last_change = 0.0
        for beat in beats:
            at = float(beat.get("at", last_change))
            emphasis = bool(beat.get("emphasis", False))
            if at - last_change >= max_static_seconds:
                decisions.append(PacingDecision(at, "visual_change", "maximum static interval reached")); last_change = at
            if emphasis:
                decisions.append(PacingDecision(at, "punch_in_or_evidence_reveal", "narration emphasis")); last_change = at
        if duration - last_change > max_static_seconds:
            decisions.append(PacingDecision(max(last_change + max_static_seconds, duration - 0.5), "ending_change", "avoid static ending"))
        return tuple(decisions)
