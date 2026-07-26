from __future__ import annotations

from statistics import mean
from typing import Mapping

from .audio_alignment import audio_sync_score, compile_audio
from .models import ContinuityBundle, SceneContinuity, StoryScene
from .motion_flow import compile_motion, motion_flow_score
from .occupancy import occupancy_score, solve_layout
from .render import render_scene
from .rhythm import compile_rhythm, story_rhythm_score
from .transition_graph import optimize_transitions, transition_score


def _parse_scenes(raw: Mapping[str, object]) -> tuple[StoryScene, ...]:
    scenes = tuple(StoryScene.from_mapping(scene, index) for index, scene in enumerate(raw.get("scenes", ())))
    if len(scenes) < 3 or scenes[0].role != "hook" or scenes[-1].role != "payoff":
        raise ValueError("story requires hook, body, and payoff")
    return scenes


def compile_bundle(raw: Mapping[str, object]) -> ContinuityBundle:
    slug = str(raw.get("slug", "")).strip()
    archetype = str(raw.get("archetype", "")).strip()
    callback = str(raw.get("callback_token", "")).strip()
    if archetype not in {"money", "share", "ranking", "comparison", "single"}:
        raise ValueError("unsupported archetype")
    scenes = _parse_scenes(raw)
    continuity_scenes: list[SceneContinuity] = []
    motions = []
    previous_exit = None
    for index, scene in enumerate(scenes):
        layout = solve_layout(archetype, scene.role, scene.visual_event)
        audio = compile_audio(scene)
        motion = compile_motion(scene, layout, index, previous_exit)
        previous_exit = motion.exit_edge
        motions.append(motion)
        rhythm = compile_rhythm(scene)
        svg = render_scene(scene, layout, audio, motion, archetype)
        continuity_scenes.append(SceneContinuity(scene, layout, audio, motion, rhythm, svg))
    transitions = optimize_transitions(scenes, tuple(motions))
    dimensions = {
        "audio_synchronization": round(mean(audio_sync_score(item.audio, item.scene) for item in continuity_scenes), 1),
        "transition_continuity": transition_score(transitions),
        "useful_occupancy": round(mean(occupancy_score(item.layout) for item in continuity_scenes), 1),
        "motion_flow": motion_flow_score(tuple(motions)),
        "story_rhythm": story_rhythm_score(tuple(item.rhythm for item in continuity_scenes)),
        "callback_payoff": 100.0 if callback and scenes[0].callback_token == scenes[-1].callback_token == callback else 0.0,
        "archetype_fit": 100.0,
        "deterministic_rendering": 100.0,
    }
    weights = {
        "audio_synchronization": .17,
        "transition_continuity": .17,
        "useful_occupancy": .14,
        "motion_flow": .16,
        "story_rhythm": .14,
        "callback_payoff": .10,
        "archetype_fit": .06,
        "deterministic_rendering": .06,
    }
    failures = []
    for key, threshold in (
        ("audio_synchronization", 92), ("transition_continuity", 90),
        ("useful_occupancy", 90), ("motion_flow", 90), ("story_rhythm", 90),
    ):
        if dimensions[key] < threshold:
            failures.append(f"{key}_below_{threshold}")
    if dimensions["callback_payoff"] < 100:
        failures.append("callback_missing")
    score = sum(dimensions[name] * weight for name, weight in weights.items())
    if failures:
        score = min(score, 69.0)
    bundle = ContinuityBundle(slug, archetype, tuple(continuity_scenes), transitions, callback, round(score, 1), dimensions, tuple(failures))
    bundle.validate()
    return bundle
