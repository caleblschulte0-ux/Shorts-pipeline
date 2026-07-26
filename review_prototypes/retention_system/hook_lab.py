from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from .models import HookPlan, HookStrategy


_NUMBER = re.compile(r"\d")
_GENERIC = re.compile(r"\b(today|in this video|did you know|let's talk about)\b", re.I)


@dataclass(frozen=True)
class HookScore:
    hook: HookPlan
    score: float
    failures: tuple[str, ...]
    reasons: tuple[str, ...]


class HookLab:
    """Generate structurally distinct hooks and select with hard timing rules."""

    def generate(
        self,
        *,
        claim: str,
        consequential_number: str,
        expectation: str,
        consequence: str,
        mascot_goal: str,
    ) -> tuple[HookPlan, ...]:
        number = consequential_number.strip()
        plans = (
            HookPlan(
                hook_id="hook-consequence",
                strategy=HookStrategy.CONSEQUENCE_FIRST,
                spoken_line=f"{consequence} — because of {number}.",
                visual_action=f"show the consequence immediately, then slam {number} on screen",
                promise=f"explain why {number} causes {consequence}",
                number_present=bool(_NUMBER.search(number)),
                action_start_seconds=0.0,
                reveal_seconds=0.7,
                pattern_key="consequence:number-impact",
            ),
            HookPlan(
                hook_id="hook-contradiction",
                strategy=HookStrategy.CONTRADICTION,
                spoken_line=f"You expect {expectation}. {number} says the opposite.",
                visual_action="split the expectation from the observed result and collide them",
                promise=f"resolve why the expected result fails against {number}",
                number_present=bool(_NUMBER.search(number)),
                action_start_seconds=0.1,
                reveal_seconds=0.9,
                pattern_key="contradiction:collision",
            ),
            HookPlan(
                hook_id="hook-scale",
                strategy=HookStrategy.SCALE_REVEAL,
                spoken_line=f"{number} is bigger than it sounds. Watch this.",
                visual_action="begin at human scale and expand until the true scale overwhelms frame",
                promise=f"make the real scale of {number} understandable",
                number_present=bool(_NUMBER.search(number)),
                action_start_seconds=0.0,
                reveal_seconds=1.2,
                pattern_key="scale:expansion",
            ),
            HookPlan(
                hook_id="hook-failed-attempt",
                strategy=HookStrategy.FAILED_ATTEMPT,
                spoken_line=f"Data tries to {mascot_goal}. Then {number} wrecks the plan.",
                visual_action=f"mascot commits to {mascot_goal}, fails on contact with the data",
                promise=f"show what makes {number} impossible to overcome",
                number_present=bool(_NUMBER.search(number)),
                action_start_seconds=0.0,
                reveal_seconds=1.0,
                pattern_key="failed-attempt:reversal",
            ),
        )
        for plan in plans:
            plan.validate()
        return plans

    def score(
        self,
        hook: HookPlan,
        *,
        recent_pattern_keys: Sequence[str] = (),
    ) -> HookScore:
        failures: list[str] = []
        reasons: list[str] = []
        score = 100.0

        if not hook.number_present:
            failures.append("missing consequential number")
        if hook.action_start_seconds > 0.5:
            failures.append("action begins after 0.5 seconds")
        if hook.reveal_seconds > 1.5:
            failures.append("core reveal lands after 1.5 seconds")
        if _GENERIC.search(hook.spoken_line):
            failures.append("generic introduction language")
        if len(hook.promise.split()) < 5:
            failures.append("viewer promise is too vague")

        if hook.pattern_key in recent_pattern_keys:
            score -= 18.0
            reasons.append("recent hook structure repeated")
        if hook.strategy == HookStrategy.FAILED_ATTEMPT:
            score += 4.0
            reasons.append("contains goal, contact, reversal, and consequence")
        if hook.strategy == HookStrategy.CONTRADICTION:
            score += 3.0
            reasons.append("explicitly breaks an existing expectation")
        if len(hook.spoken_line.split()) > 18:
            score -= 8.0
            reasons.append("spoken hook is wordy")

        score -= 30.0 * len(failures)
        score = max(0.0, min(100.0, score))
        return HookScore(hook, score, tuple(failures), tuple(reasons))

    def select(
        self,
        candidates: Iterable[HookPlan],
        *,
        recent_pattern_keys: Sequence[str] = (),
    ) -> HookScore:
        scored = [
            self.score(candidate, recent_pattern_keys=recent_pattern_keys)
            for candidate in candidates
        ]
        eligible = [item for item in scored if not item.failures]
        if not eligible:
            details = "; ".join(
                f"{item.hook.hook_id}: {', '.join(item.failures)}" for item in scored
            )
            raise ValueError("no eligible hook candidate: " + details)
        return max(eligible, key=lambda item: (item.score, item.hook.hook_id))
