from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class EmotionalState(str, Enum):
    CURIOUS = "curious"
    CONFIDENT = "confident"
    CONFUSED = "confused"
    WORRIED = "worried"
    FRUSTRATED = "frustrated"
    SURPRISED = "surprised"
    RELIEVED = "relieved"
    DELIGHTED = "delighted"
    DETERMINED = "determined"


@dataclass(frozen=True)
class CharacterBeat:
    beat_id: str
    character_id: str
    state: EmotionalState
    action: str
    goal: str
    obstacle: str = ""
    consequence: str = ""
    callback_key: str = ""
    intensity: float = 5.0

    def __post_init__(self) -> None:
        for name in ("beat_id", "character_id", "action", "goal"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        if not 0 <= self.intensity <= 10:
            raise ValueError("intensity must be between 0 and 10")


@dataclass(frozen=True)
class PersonalityPolicy:
    minimum_states: int = 3
    minimum_actions: int = 3
    minimum_state_changes: int = 2
    maximum_repeated_action: int = 2
    require_obstacle: bool = True
    require_consequence: bool = True
    require_callback_resolution: bool = True


@dataclass(frozen=True)
class PersonalityDefect:
    code: str
    beat_ids: tuple[str, ...]
    explanation: str
    suggested_change: str


@dataclass(frozen=True)
class PersonalityReport:
    score: float
    distinct_states: int
    distinct_actions: int
    state_changes: int
    callback_resolution_rate: float
    defects: tuple[PersonalityDefect, ...]


def analyze_personality_arc(
    beats: Iterable[CharacterBeat],
    *,
    policy: PersonalityPolicy | None = None,
) -> PersonalityReport:
    policy = policy or PersonalityPolicy()
    ordered = tuple(beats)
    if not ordered:
        return PersonalityReport(0.0, 0, 0, 0, 0.0, (
            PersonalityDefect("missing_character_arc", (), "no character actions are defined", "add a setup, attempt, obstacle, reaction, and payoff"),
        ))
    if len({beat.beat_id for beat in ordered}) != len(ordered):
        raise ValueError("duplicate beat_id")

    defects: list[PersonalityDefect] = []
    states = {beat.state for beat in ordered}
    normalized_actions = [" ".join(beat.action.lower().split()) for beat in ordered]
    action_counts = Counter(normalized_actions)
    state_changes = sum(1 for previous, current in zip(ordered, ordered[1:]) if previous.state != current.state)

    if len(states) < policy.minimum_states:
        defects.append(PersonalityDefect(
            "emotionally_flat",
            tuple(beat.beat_id for beat in ordered),
            "the character does not move through enough distinct emotional states",
            "add a visible shift such as confidence to confusion, worry to discovery, or frustration to relief",
        ))
    if len(set(normalized_actions)) < policy.minimum_actions:
        defects.append(PersonalityDefect(
            "action_repetition",
            tuple(beat.beat_id for beat in ordered),
            "the character repeats too few types of action",
            "replace pointing or standing with attempts, mistakes, decisions, comparisons, physical consequences, or callbacks",
        ))
    if state_changes < policy.minimum_state_changes:
        defects.append(PersonalityDefect(
            "insufficient_emotional_progression",
            tuple(beat.beat_id for beat in ordered),
            "the emotional state does not visibly evolve with the story",
            "tie emotional changes to new information, obstacles, and the final answer",
        ))

    for action, count in action_counts.items():
        if count > policy.maximum_repeated_action:
            beat_ids = tuple(beat.beat_id for beat, normalized in zip(ordered, normalized_actions) if normalized == action)
            defects.append(PersonalityDefect(
                "overused_character_action",
                beat_ids,
                f"the action '{action}' appears {count} times",
                "replace repeated staging with a new purposeful action that changes the situation",
            ))

    if policy.require_obstacle and not any(beat.obstacle.strip() for beat in ordered):
        defects.append(PersonalityDefect(
            "no_obstacle",
            tuple(beat.beat_id for beat in ordered),
            "the character never encounters a visible obstacle",
            "show a failed assumption, physical limitation, cost, confusion, or contradiction",
        ))
    if policy.require_consequence and not any(beat.consequence.strip() for beat in ordered):
        defects.append(PersonalityDefect(
            "no_consequence",
            tuple(beat.beat_id for beat in ordered),
            "the character's actions do not visibly cause anything",
            "make an action change an object, number, relationship, risk, or emotional state",
        ))

    opened_callbacks = Counter(beat.callback_key for beat in ordered if beat.callback_key and not beat.consequence.strip())
    closed_callbacks = Counter(beat.callback_key for beat in ordered if beat.callback_key and beat.consequence.strip())
    total_callbacks = sum(opened_callbacks.values())
    resolved = sum(min(opened_callbacks[key], closed_callbacks[key]) for key in opened_callbacks)
    callback_rate = 1.0 if total_callbacks == 0 else resolved / total_callbacks
    if policy.require_callback_resolution and total_callbacks and callback_rate < 1.0:
        unresolved = tuple(sorted(key for key in opened_callbacks if closed_callbacks[key] < opened_callbacks[key]))
        defects.append(PersonalityDefect(
            "unresolved_character_callback",
            unresolved,
            "a setup action or emotional beat is not paid off",
            "return to the same object, choice, expression, or problem in the payoff",
        ))

    base = (
        min(10.0, len(states) / policy.minimum_states * 8.0) * 0.25
        + min(10.0, len(set(normalized_actions)) / policy.minimum_actions * 8.0) * 0.25
        + min(10.0, state_changes / policy.minimum_state_changes * 8.0) * 0.2
        + min(10.0, sum(beat.intensity for beat in ordered) / len(ordered)) * 0.15
        + callback_rate * 10.0 * 0.15
    )
    score = max(0.0, min(10.0, base - len(defects) * 0.65))

    return PersonalityReport(
        score=round(score, 3),
        distinct_states=len(states),
        distinct_actions=len(set(normalized_actions)),
        state_changes=state_changes,
        callback_resolution_rate=round(callback_rate, 3),
        defects=tuple(defects),
    )
