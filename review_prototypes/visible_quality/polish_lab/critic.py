from __future__ import annotations

from statistics import mean

from .audio import audio_sync_score
from .caption_layout import platform_safe
from .models import StoryPolishBundle
from .tension import tension_score
from .transitions import transition_variety_score


def score_bundle(bundle: StoryPolishBundle) -> tuple[float, dict[str, float], tuple[str, ...]]:
    failures: list[str] = []
    typography_scores = []
    audio_scores = []
    occupancy_scores = []
    for scene in bundle.scenes:
        typography_scores.append(min(100.0, scene.caption.contrast_ratio / 7 * 100))
        audio_scores.append(audio_sync_score(scene.audio, scene.caption))
        occupancy = scene.hero_box.width * scene.hero_box.height / (1080 * 1920)
        occupancy_scores.append(min(100.0, occupancy / .34 * 100))
        if not platform_safe(scene.caption.box):
            failures.append(f"{scene.scene_id}:caption_platform_collision")
        if scene.caption.style.font_size < 36:
            failures.append(f"{scene.scene_id}:caption_too_small")

    transition = transition_variety_score(bundle.transitions)
    tension = tension_score(bundle.tension)
    typography = mean(typography_scores) if typography_scores else 0
    audio = mean(audio_scores) if audio_scores else 0
    occupancy = mean(occupancy_scores) if occupancy_scores else 0
    archetype_coverage = 100.0 if bundle.archetype else 0.0
    callback = 100.0 if bundle.callback_token else 0.0
    dimensions = {
        "typography_legibility": round(typography, 1),
        "audio_sync": round(audio, 1),
        "transition_continuity": transition,
        "tension_arc": tension,
        "useful_occupancy": round(occupancy, 1),
        "archetype_fit": archetype_coverage,
        "callback_payoff": callback,
    }
    weights = {
        "typography_legibility": .18,
        "audio_sync": .14,
        "transition_continuity": .14,
        "tension_arc": .20,
        "useful_occupancy": .12,
        "archetype_fit": .12,
        "callback_payoff": .10,
    }
    score = sum(dimensions[key] * weight for key, weight in weights.items())
    if failures:
        score = min(score, 69.0)
    return round(score, 1), dimensions, tuple(failures)
