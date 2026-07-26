from __future__ import annotations

from statistics import mean

from .models import RhythmBeat, StoryScene

ROLE_CURVES = {
    "hook": ((0.00, "impact", .98), (.12, "reveal", .90), (.44, "contrast", .76), (.82, "question", .62)),
    "setup": ((0.00, "enter", .34), (.24, "orient", .48), (.58, "fact", .61), (.86, "handoff", .70)),
    "explanation": ((0.00, "enter", .46), (.20, "build", .61), (.48, "number", .74), (.78, "turn", .84)),
    "consequence": ((0.00, "enter", .58), (.18, "pressure", .76), (.46, "burden", .92), (.80, "peak", 1.0)),
    "payoff": ((0.00, "callback", .72), (.22, "resolve", .78), (.62, "silence", .38), (.88, "landing", .86)),
}


def compile_rhythm(scene: StoryScene) -> tuple[RhythmBeat, ...]:
    return tuple(RhythmBeat(round(frac * scene.duration, 3), kind, intensity) for frac, kind, intensity in ROLE_CURVES[scene.role])


def story_rhythm_score(all_beats: tuple[tuple[RhythmBeat, ...], ...]) -> float:
    if not all_beats:
        return 0.0
    early = mean(1.0 if beats[0].at <= .12 else 0.0 for beats in all_beats)
    within_scene_variation = mean(max(b.intensity for b in beats) - min(b.intensity for b in beats) for beats in all_beats)
    peaks = [max(b.intensity for b in beats) for beats in all_beats]
    consequence_peak = max(peaks) >= .98 and peaks[-2] == max(peaks)
    payoff_release = min(b.intensity for b in all_beats[-1]) <= .40
    score = early * 30 + min(30, within_scene_variation / .45 * 30) + (22 if consequence_peak else 0) + (18 if payoff_release else 0)
    return round(min(100.0, score), 1)
