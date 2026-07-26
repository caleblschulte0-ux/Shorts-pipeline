from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from .contracts import ProductionScene, ProductionStory, QualityBridgeBundle, SceneOverride


def _shape(scene: ProductionScene) -> str:
    values = scene.values
    periods = sum(value.period is not None for value in values)
    unit = scene.unit.strip().lower()
    total = sum(value.value for value in values)
    if periods >= 2:
        return "trend"
    if len(values) == 1:
        return "single"
    if len(values) == 2:
        return "comparison"
    if unit in {"percent", "%", "rate", "pct", "share"} and 95 <= total <= 105:
        return "share"
    return "ranking"


def _target(scene: ProductionScene) -> str:
    if scene.highlight_label:
        return scene.highlight_label
    if _shape(scene) == "trend":
        return scene.values[-1].label
    return max(scene.values, key=lambda item: item.value).label


def _kind_candidates(scene: ProductionScene) -> tuple[str, ...]:
    shape = _shape(scene)
    role = scene.role
    if shape == "trend":
        return ("timeline", "trend") if role in {"hook", "payoff"} else ("trend", "timeline")
    if shape == "single":
        return ("fill_vessel", "bubbles")
    if shape == "comparison":
        return ("comparison", "pictorial_race", "stack")
    if shape == "share":
        return ("waffle_grid", "share", "stack")
    return ("pictorial_race", "rank", "bubbles")


def _action_candidates(kind: str, role: str) -> tuple[str, ...]:
    if kind in {"trend", "timeline"}:
        return ("drag_line", "pull_down_win")
    if kind in {"waffle_grid", "share", "stack", "fill_vessel"}:
        return ("hoist_stack", "drag_line")
    if kind in {"pictorial_race", "rank", "comparison"}:
        return ("shoved_bar", "drag_line")
    return ("shoved_bar", "hoist_stack")


def _choose_distinct(candidates: tuple[str, ...], recent: list[str], repeat_limit: int = 2) -> str:
    counts = Counter(recent[-3:])
    return min(candidates, key=lambda item: (counts[item] >= repeat_limit, counts[item], candidates.index(item)))


def _duration(scene: ProductionScene) -> float:
    words = max(1, len(scene.sentence.split()))
    return round(max(2.4, min(7.5, words / 2.55 + 0.7)), 2)


def _timeline(kind: str, action: str, duration: float, target: str, role: str, goal: str) -> dict[str, Any]:
    # Mirrors data_learning.scene_timeline.plan_scene without importing production.
    setup_end = 0.18
    effort_end = 0.74
    t_setup = round(setup_end * duration, 2)
    t_payoff = round(effort_end * duration, 2)
    events = [
        {"t": 0.0, "actor": "chart", "action": "enter", "target": target},
        {"t": 0.0, "actor": "data", "action": "grip", "target": target, "contact": "both_hands"},
        {"t": 0.0, "actor": target, "action": "grow", "driver": "data_reveal"},
        {"t": t_setup, "actor": "data", "action": action, "target": target, "driver": target},
        {"t": t_payoff, "actor": "data", "action": "payoff_reaction", "target": target},
        {"t": t_payoff, "actor": "label", "action": "land", "target": target},
        {"t": round(duration, 2), "actor": "chart", "action": "final_state"},
    ]
    if role == "hook":
        events.insert(3, {"t": min(0.22, t_setup), "actor": "chart", "action": "hook_burst", "target": target, "reveal": 0.46})
    return {
        "duration": round(duration, 2),
        "kind": kind,
        "action": action,
        "goal": goal,
        "target": target,
        "phases": {
            "setup": [0.0, t_setup],
            "effort": [t_setup, t_payoff],
            "payoff": [t_payoff, round(duration, 2)],
        },
        "events": sorted(events, key=lambda item: item["t"]),
    }


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"\$?\d[\d,.]*%?", text)))[:3]


def _audio(scene: ProductionScene, duration: float, action: str) -> tuple[dict[str, Any], ...]:
    cues: list[dict[str, Any]] = []
    cues.append({"at": 0.06 if scene.role == "hook" else 0.18, "name": "impact_short" if scene.role == "hook" else "soft_whoosh", "role": "motion", "gain_db": -9.0})
    for index, token in enumerate(_numbers(scene.sentence)[:2]):
        cues.append({"at": round(min(duration - 0.30, 0.42 + index * 0.58), 2), "name": "number_tick", "role": "caption", "token": token, "gain_db": -13.0})
    if scene.role in {"consequence", "payoff"}:
        silence_end = round(max(0.8, duration - 0.55), 2)
        cues.append({"at": silence_end, "name": "resolve_chime" if scene.role == "payoff" else "weight_hit", "role": "payoff", "gain_db": -8.0, "pre_silence_s": 0.18})
    return tuple(sorted(cues, key=lambda cue: cue["at"]))


def _transition(previous: SceneOverride | None, scene: ProductionScene, target: str, kind: str) -> dict[str, Any] | None:
    if previous is None:
        return None
    if scene.role == "payoff":
        return {"kind": "callback_return", "duration": 0.34, "shared_object": previous.callback_token, "sound": "reverse_whoosh"}
    if previous.target == target:
        return {"kind": "object_match", "duration": 0.24, "shared_object": target, "sound": "short_whoosh"}
    if previous.kind in {"trend", "timeline"} and kind in {"stack", "waffle_grid", "share", "pictorial_race"}:
        return {"kind": "data_morph", "duration": 0.32, "shared_object": "latest_value", "sound": "elastic_stretch"}
    return {"kind": "impact_cut", "duration": 0.12, "shared_object": "", "sound": "impact_hit"}


def compile_bridge(story: ProductionStory, version: str = "shadow-v1") -> QualityBridgeBundle:
    story.validate()
    recent_kinds: list[str] = []
    recent_actions: list[str] = []
    callback = f"{story.slug}:opening"
    overrides: list[SceneOverride] = []
    for scene in story.scenes:
        kind = _choose_distinct(_kind_candidates(scene), recent_kinds)
        action = _choose_distinct(_action_candidates(kind, scene.role), recent_actions)
        target = _target(scene)
        duration = _duration(scene)
        goal = {
            "hook": "make the data conflict visible in the first 0.4 seconds",
            "setup": "orient the viewer while maintaining motion",
            "explanation": "make the causal change physically legible",
            "consequence": "convert the number into a felt physical burden",
            "payoff": "resolve the opening object and land the takeaway",
        }[scene.role]
        token = callback if scene.index in {0, len(story.scenes) - 1} else ""
        timeline = _timeline(kind, action, duration, target, scene.role, goal)
        override = SceneOverride(
            segment_index=scene.index,
            kind=kind,
            performance=action,
            role=scene.role,
            target=target,
            goal=goal,
            callback_token=token,
            scene_timeline=timeline,
            audio_cues=_audio(scene, duration, action),
            transition_in=_transition(overrides[-1] if overrides else None, scene, target, kind),
            rationale=(
                f"production-supported {kind} depiction for {_shape(scene)} data",
                f"verified mechanically coupled action {action}",
                "uses existing scene timeline phase boundaries",
            ),
        )
        override.validate()
        overrides.append(override)
        recent_kinds.append(kind)
        recent_actions.append(action)

    payload = {
        "slug": story.slug,
        "title": story.title,
        "hook": story.hook,
        "closing": story.closing,
        "scenes": [
            {"role": scene.role, "topic": scene.topic, "values": [(value.label, value.value, value.period) for value in scene.values]}
            for scene in story.scenes
        ],
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    bundle = QualityBridgeBundle(
        slug=story.slug,
        version=version,
        story_fingerprint=fingerprint,
        overrides=tuple(overrides),
        callback_token=callback,
        supported_by_contracts=(
            "story.Segment.kind",
            "Insight.perf_override",
            "Insight.plan_locked",
            "scene_timeline.plan_scene",
            "studio_render.segment_windows",
            "showrunner sovereign verdict",
        ),
    )
    bundle.validate()
    return bundle
