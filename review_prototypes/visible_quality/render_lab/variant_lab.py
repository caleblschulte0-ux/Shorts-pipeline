from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Mapping

from .variant_effects import render_variant


@dataclass(frozen=True)
class VariantCandidate:
    name: str
    story_fit: float
    first_frame_energy: float
    physical_causality: float
    information_clarity: float
    novelty: float
    reason: str

    @property
    def score(self) -> float:
        return round(
            self.story_fit*.28 + self.first_frame_energy*.22 + self.physical_causality*.22
            + self.information_clarity*.18 + self.novelty*.10,
            1,
        )

    def to_dict(self) -> dict:
        result = asdict(self)
        result["score"] = self.score
        return result


@dataclass(frozen=True)
class TransitionPlan:
    kind: str
    duration: float
    shared_object: str
    outgoing_action: str
    incoming_action: str
    sound: str

    def validate(self) -> None:
        if not .08 <= self.duration <= .55:
            raise ValueError("transition duration outside Shorts range")
        if not self.shared_object and self.kind != "impact_cut":
            raise ValueError("non-impact transition needs a shared visual object")


def _shape(story: Mapping[str, object]) -> dict[str, object]:
    data = list(story.get("data", ()))
    values = [float(p["value"]) for p in data]
    unit = str(story.get("unit", "")).lower()
    periods = [p.get("period") for p in data]
    return {
        "count": len(data),
        "time_series": len(data) >= 2 and all(p is not None for p in periods),
        "share": unit in {"%", "percent"} and 95 <= sum(values) <= 105,
        "ratio": (max(values)/min(values)) if values and min(values) else 1,
        "money": unit in {"$", "usd", "dollars"},
        "topic": str(story.get("topic", "")).lower(),
    }


def generate_variants(story: Mapping[str, object], recent: Iterable[str] = ()) -> tuple[VariantCandidate, ...]:
    shape = _shape(story)
    recent_set = set(recent)
    variants: list[VariantCandidate] = []
    if shape["time_series"] and shape["money"]:
        variants += [
            VariantCandidate("receipt_roll", 98, 88, 92, 96, 90, "money over time becomes a growing receipt"),
            VariantCandidate("cart_overflow", 93, 94, 98, 82, 95, "the price increase becomes physical weight in a cart"),
        ]
    if shape["share"]:
        variants.append(VariantCandidate("share_squeeze", 99, 92, 96, 98, 91, "the dominant share physically occupies the remaining space"))
    if shape["count"] >= 3:
        variants.append(VariantCandidate("rank_race", 92, 96, 89, 94, 86, "ranking becomes a race and the gap becomes the finish"))
    if shape["ratio"] >= 1.5:
        variants.append(VariantCandidate("scale_collision", 95, 99, 94, 90, 93, "the ratio becomes a literal collision of scale"))
    if not variants:
        variants.append(VariantCandidate("rank_race", 76, 88, 82, 86, 78, "reliable physical ranking fallback"))
    adjusted = []
    for candidate in variants:
        novelty = max(40, candidate.novelty - (35 if candidate.name in recent_set else 0))
        adjusted.append(VariantCandidate(
            candidate.name, candidate.story_fit, candidate.first_frame_energy,
            candidate.physical_causality, candidate.information_clarity, novelty, candidate.reason,
        ))
    return tuple(sorted(adjusted, key=lambda c: c.score, reverse=True))


def choose_variant(story: Mapping[str, object], recent: Iterable[str] = ()) -> VariantCandidate:
    return generate_variants(story, recent)[0]


def render_variant_keyframes(story: Mapping[str, object], variant: str) -> dict[str, str]:
    data = tuple(dict(p) for p in story.get("data", ()))
    title = str(story.get("claim", story.get("topic", "Data story")))
    return {
        "frame_one": render_variant(variant, .04, data, title),
        "effort": render_variant(variant, .55, data, title),
        "payoff": render_variant(variant, 1.0, data, title),
    }


def compile_transition(previous: Mapping[str, object], current: Mapping[str, object]) -> TransitionPlan:
    prev_callback = str(previous.get("callback_token", ""))
    cur_callback = str(current.get("callback_token", ""))
    prev_event = str(previous.get("visual_event", ""))
    cur_event = str(current.get("visual_event", ""))
    prev_focus = str(previous.get("focal_label", previous.get("focus_label", "")))
    cur_focus = str(current.get("focal_label", current.get("focus_label", "")))

    if prev_callback and prev_callback == cur_callback:
        plan = TransitionPlan("callback_return", .42, prev_callback, "freeze_opening_object", "complete_opening_object", "memory_chime")
    elif prev_focus and prev_focus == cur_focus:
        plan = TransitionPlan("object_match_cut", .24, prev_focus, "push_object_to_camera", "pull_same_object_from_camera", "short_whoosh")
    elif any(token in prev_event for token in ("stack", "collision", "slam")):
        plan = TransitionPlan("impact_cut", .12, "", "finish_on_impact", "enter_on_reaction", "impact_hit")
    elif "line" in prev_event and any(token in cur_event for token in ("stack", "cart", "receipt")):
        plan = TransitionPlan("data_morph", .32, "latest_value", "line_tip_expands", "physical_object_forms", "elastic_stretch")
    else:
        shared = prev_focus or cur_focus or "hero_value"
        plan = TransitionPlan("number_match_cut", .20, shared, "number_fills_frame", "number_reveals_next_scene", "number_tick")
    plan.validate()
    return plan


def transition_sequence(scenes: Iterable[Mapping[str, object]]) -> tuple[TransitionPlan, ...]:
    seq = tuple(scenes)
    return tuple(compile_transition(a, b) for a, b in zip(seq, seq[1:]))
