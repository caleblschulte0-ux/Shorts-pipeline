from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .models import MotionPlan, StoryScene, TransitionBridge


@dataclass(frozen=True)
class _Candidate:
    bridge: TransitionBridge
    base_score: float


def _candidates(out_scene: StoryScene, in_scene: StoryScene, out_motion: MotionPlan, in_motion: MotionPlan) -> tuple[_Candidate, ...]:
    result: list[_Candidate] = []
    if in_scene.role == "payoff" and in_scene.callback_token:
        result.append(_Candidate(TransitionBridge("callback_return", .34, in_scene.callback_token, out_motion.exit_edge, in_motion.entry_edge, "reverse_whoosh", 99), 110))
    if out_scene.focus == in_scene.focus:
        result.append(_Candidate(TransitionBridge("object_match", .24, in_scene.focus, out_motion.exit_edge, in_motion.entry_edge, "short_whoosh", 97), 102))
    if any(token in out_scene.visual_event.lower() for token in ("line", "trend")) and any(token in in_scene.visual_event.lower() for token in ("stack", "cart", "receipt", "object")):
        result.append(_Candidate(TransitionBridge("data_morph", .32, "latest_value", out_motion.exit_edge, in_motion.entry_edge, "elastic_stretch", 96), 100))
    if any(ch.isdigit() for ch in out_scene.focus) and any(ch.isdigit() for ch in in_scene.focus):
        result.append(_Candidate(TransitionBridge("number_match", .22, in_scene.focus, out_motion.exit_edge, in_motion.entry_edge, "number_tick", 94), 96))
    if out_motion.exit_edge == in_motion.entry_edge:
        result.append(_Candidate(TransitionBridge("momentum_match", .20, in_scene.focus, out_motion.exit_edge, in_motion.entry_edge, "fast_whoosh", 95), 98))
    if out_scene.role == "hook":
        result.append(_Candidate(TransitionBridge("impact_cut", .12, "", out_motion.exit_edge, in_motion.entry_edge, "impact_hit", 89), 88))
    result.append(_Candidate(TransitionBridge("focus_pull", .24, in_scene.focus, out_motion.exit_edge, in_motion.entry_edge, "focus_whoosh", 87), 84))
    for item in result:
        item.bridge.validate()
    return tuple(result)


def optimize_transitions(scenes: tuple[StoryScene, ...], motions: tuple[MotionPlan, ...]) -> tuple[TransitionBridge, ...]:
    candidates = [_candidates(a, b, ma, mb) for a, b, ma, mb in zip(scenes, scenes[1:], motions, motions[1:])]
    states: dict[tuple[str, ...], tuple[float, tuple[TransitionBridge, ...]]] = {(): (0.0, ())}
    for edge_candidates in candidates:
        next_states: dict[tuple[str, ...], tuple[float, tuple[TransitionBridge, ...]]] = {}
        for history, (score, path) in states.items():
            counts = Counter(history)
            for candidate in edge_candidates:
                repeat_penalty = counts[candidate.bridge.kind] * 18
                direction_bonus = 8 if candidate.bridge.outgoing_edge == candidate.bridge.incoming_edge else 0
                total = score + candidate.base_score + direction_bonus - repeat_penalty
                new_history = (history + (candidate.bridge.kind,))[-2:]
                current = next_states.get(new_history)
                if current is None or total > current[0]:
                    next_states[new_history] = (total, path + (candidate.bridge,))
        states = next_states
    return max(states.values(), key=lambda item: item[0])[1] if states else ()


def transition_score(transitions: tuple[TransitionBridge, ...]) -> float:
    if not transitions:
        return 100.0
    continuity = sum(t.continuity_score for t in transitions) / len(transitions)
    kinds = [t.kind for t in transitions]
    variety = len(set(kinds)) / len(kinds)
    direction = sum(t.outgoing_edge == t.incoming_edge for t in transitions) / len(transitions)
    repeat_penalty = max(Counter(kinds).values()) - 1
    score = continuity * .68 + variety * 20 + direction * 12 - repeat_penalty * 5
    return round(max(0.0, min(100.0, score)), 1)
