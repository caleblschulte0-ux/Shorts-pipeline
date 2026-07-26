from __future__ import annotations

from collections import Counter

from .models import TransitionSpec


def choose_transition(outgoing: dict, incoming: dict, recent: tuple[str, ...] = ()) -> TransitionSpec:
    out_event = str(outgoing.get("visual_event", "")).lower()
    in_event = str(incoming.get("visual_event", "")).lower()
    out_focus = str(outgoing.get("focus", outgoing.get("focal_label", "")))
    in_focus = str(incoming.get("focus", incoming.get("focal_label", "")))
    out_role = str(outgoing.get("role", ""))
    in_role = str(incoming.get("role", ""))

    if in_role == "payoff" and incoming.get("callback_token"):
        candidate = TransitionSpec("callback_return", .34, str(incoming.get("callback_token")), "collapse_to_token", "restore_opening_object", "reverse_whoosh", 99)
    elif out_focus and out_focus == in_focus:
        candidate = TransitionSpec("object_match", .24, out_focus, "push_to_camera", "pull_from_camera", "short_whoosh", 96)
    elif any(token in out_event for token in ("line", "trend")) and any(token in in_event for token in ("stack", "cart", "receipt")):
        candidate = TransitionSpec("data_morph", .32, "latest_value", "line_tip_expands", "physical_object_forms", "elastic_stretch", 94)
    elif any(ch.isdigit() for ch in out_focus) and any(ch.isdigit() for ch in in_focus):
        candidate = TransitionSpec("number_match", .22, in_focus, "number_fills_frame", "same_number_reveals_scene", "number_tick", 91)
    elif out_role == "hook":
        candidate = TransitionSpec("impact_cut", .12, "", "finish_on_impact", "enter_on_reaction", "impact_hit", 88)
    else:
        candidate = TransitionSpec("whip_pan", .20, "", "pan_out", "pan_in", "fast_whoosh", 82)

    counts = Counter(recent[-3:])
    if counts[candidate.kind] >= 2:
        candidate = TransitionSpec("impact_cut", .12, "", "finish_on_impact", "enter_on_reaction", "impact_hit", 84)
    candidate.validate()
    return candidate


def compile_transitions(scenes: tuple[dict, ...]) -> tuple[TransitionSpec, ...]:
    recent: list[str] = []
    result: list[TransitionSpec] = []
    for outgoing, incoming in zip(scenes, scenes[1:]):
        transition = choose_transition(outgoing, incoming, tuple(recent))
        result.append(transition)
        recent.append(transition.kind)
    return tuple(result)


def transition_variety_score(transitions: tuple[TransitionSpec, ...]) -> float:
    if not transitions:
        return 100.0
    kinds = [transition.kind for transition in transitions]
    unique = len(set(kinds)) / len(kinds)
    continuity = sum(transition.continuity_score for transition in transitions) / len(transitions)
    repeat_penalty = max(Counter(kinds).values()) - 1
    return round(max(0.0, min(100.0, unique * 35 + continuity * .65 - repeat_penalty * 8)), 1)
