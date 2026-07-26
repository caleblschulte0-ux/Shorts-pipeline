from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .choreography import action_repetition, varied_moves
from .models import PreviewBundle, RuntimeScene


@dataclass(frozen=True)
class QualityReport:
    score: float
    dimensions: dict[str, float]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def _scene_occupancy(scene: RuntimeScene) -> float:
    return float(scene.metrics.get("occupancy", 0.0))


def lint_preview(scenes: Iterable[RuntimeScene], opening_callback: str, ending_callback: str) -> QualityReport:
    seq = tuple(scenes)
    failures: list[str] = []
    warnings: list[str] = []
    if not seq:
        return QualityReport(0.0, {}, ("no scenes",), ())

    hook_motion = 100.0 if seq[0].keyframes and seq[0].keyframes[0].at <= .4 else 0.0
    caption_density = mean(min(100, 100 * len(s.captions) / max(1, s.duration / 2.2)) for s in seq)
    occupancy = mean(min(100, _scene_occupancy(s) * 100) for s in seq)
    camera_variety = 100.0 if varied_moves(s.camera_move for s in seq) else 62.0
    action_variety = max(0.0, 100 * (1 - max(0, action_repetition(s.mascot_action for s in seq) - .40)))
    effect_variety = 100 * len(set(s.visual_event for s in seq)) / len(seq)
    callback = 100.0 if opening_callback and opening_callback == ending_callback else 0.0
    sound_sync = mean(100.0 if s.sounds and all(c.sync_target for c in s.sounds) else 35.0 for s in seq)

    dimensions = {
        "hook_motion": hook_motion,
        "caption_rhythm": round(caption_density, 1),
        "useful_occupancy": round(occupancy, 1),
        "camera_variety": camera_variety,
        "mascot_action_variety": round(action_variety, 1),
        "demonstration_variety": round(effect_variety, 1),
        "ending_callback": callback,
        "sound_sync": round(sound_sync, 1),
    }
    if hook_motion < 100:
        failures.append("hook has no visible action by 0.40s")
    if occupancy < 68:
        failures.append("average useful occupancy below 68%")
    if callback < 100:
        failures.append("ending does not resolve opening visual")
    if effect_variety < 70:
        warnings.append("too many scenes reuse the same demonstration")
    if action_variety < 75:
        warnings.append("mascot performance is becoming repetitive")
    if not varied_moves(s.camera_move for s in seq):
        warnings.append("camera move repeats three scenes in a row")

    weights = {
        "hook_motion": .18,
        "caption_rhythm": .12,
        "useful_occupancy": .14,
        "camera_variety": .10,
        "mascot_action_variety": .14,
        "demonstration_variety": .14,
        "ending_callback": .10,
        "sound_sync": .08,
    }
    score = sum(dimensions[k] * w for k, w in weights.items())
    if failures:
        score = min(score, 64.0)
    return QualityReport(round(score, 1), dimensions, tuple(failures), tuple(warnings))


def lint_bundle(bundle: PreviewBundle) -> QualityReport:
    return lint_preview(bundle.scenes, bundle.opening_callback, bundle.ending_callback)
