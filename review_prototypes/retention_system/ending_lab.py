from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import EndingPlan


@dataclass(frozen=True)
class EndingScore:
    ending: EndingPlan
    score: float
    failures: tuple[str, ...]
    reasons: tuple[str, ...]


class EndingLab:
    def generate(
        self,
        *,
        claim: str,
        consequence: str,
        mascot_goal: str,
        final_number: str,
    ) -> tuple[EndingPlan, ...]:
        endings = (
            EndingPlan(
                ending_id="ending-consequence",
                spoken_line=f"That is what {final_number} changes: {consequence}.",
                synthesis=f"connect {claim} to the real-world consequence",
                consequence=consequence,
                mascot_resolution=f"mascot fails at {mascot_goal}, then adapts",
                visual_payoff="impact, reaction, recovery, settle",
                duration_seconds=2.0,
            ),
            EndingPlan(
                ending_id="ending-reframe",
                spoken_line=f"So {final_number} is not trivia. It is the whole story.",
                synthesis=f"reframe {claim} as the explanation for the opening contradiction",
                consequence=consequence,
                mascot_resolution=f"mascot completes {mascot_goal} using the corrected understanding",
                visual_payoff="return to the opening image with the meaning reversed",
                duration_seconds=2.3,
            ),
            EndingPlan(
                ending_id="ending-question",
                spoken_line=f"Would you have guessed {final_number}? Comment below.",
                synthesis="repeat the final number",
                consequence="none",
                mascot_resolution="mascot points at comments",
                visual_payoff="static question card",
                duration_seconds=2.0,
                generic_cta=True,
            ),
        )
        for ending in endings:
            ending.validate()
        return endings

    def score(self, ending: EndingPlan) -> EndingScore:
        failures: list[str] = []
        reasons: list[str] = []
        score = 100.0
        if ending.generic_cta:
            failures.append("generic call-to-action replaces payoff")
        if ending.consequence.strip().lower() in {"", "none", "n/a"}:
            failures.append("ending adds no consequence")
        if "static" in ending.visual_payoff.lower():
            failures.append("ending resolves as a static card")
        if "impact" in ending.visual_payoff.lower():
            reasons.append("contains impact and reaction")
        if "opening" in ending.visual_payoff.lower():
            reasons.append("recontextualizes the opening")
            score += 4.0
        if "completes" in ending.mascot_resolution.lower():
            reasons.append("resolves the mascot goal")
            score += 3.0
        score -= 35.0 * len(failures)
        return EndingScore(ending, max(0.0, min(100.0, score)), tuple(failures), tuple(reasons))

    def select(self, candidates: Iterable[EndingPlan]) -> EndingScore:
        scored = [self.score(candidate) for candidate in candidates]
        eligible = [item for item in scored if not item.failures]
        if not eligible:
            raise ValueError("no ending candidate passes payoff requirements")
        return max(eligible, key=lambda item: (item.score, item.ending.ending_id))
