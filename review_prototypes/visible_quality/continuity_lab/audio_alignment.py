from __future__ import annotations

import re

from .models import AudioCue, AudioPlan, DuckPoint, StoryScene

EVENT_PRIMARY = {
    "collision": "impact_low", "slam": "impact_short", "gap": "elastic_stretch",
    "line": "tension_rise", "trend": "tension_rise", "stack": "weight_clunk",
    "receipt": "paper_roll", "cart": "cart_rattle", "squeeze": "rubber_squeeze",
    "race": "fast_whoosh", "gauge": "dial_snap", "callback": "resolve_chime",
    "opening": "resolve_chime",
}


def _primary(event: str) -> str:
    low = event.lower()
    for token, sound in EVENT_PRIMARY.items():
        if token in low:
            return sound
    return "soft_whoosh"


def _number_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?:\$)?\d[\d,.]*(?:%|×)?", text))[:3]


def _snap(value: float, fps: int = 30) -> float:
    return round(round(value * fps) / fps, 3)


def compile_audio(scene: StoryScene) -> AudioPlan:
    duration = scene.duration
    tokens = _number_tokens(scene.narration)
    primary_at = _snap(0.067 if scene.role == "hook" else min(0.20, duration * 0.055))
    cues: list[AudioCue] = [AudioCue(primary_at, _primary(scene.visual_event), "primary", -8.0, 0.18, -3.0)]
    emphasis_times: list[float] = []
    if tokens:
        usable_start = 0.24 if scene.role == "hook" else 0.45
        usable_end = max(usable_start, duration - 0.72)
        step = (usable_end - usable_start) / max(1, len(tokens))
        for idx, token in enumerate(tokens):
            at = _snap(usable_start + step * (idx + 0.5))
            emphasis_times.append(at)
            cues.append(AudioCue(at, "number_tick", token, -12.0, 0.08, -1.8))
    payoff_silence = None
    if scene.role in {"consequence", "payoff"}:
        silence_end = _snap(duration - 0.42)
        silence_start = _snap(max(0.35, silence_end - 0.24))
        payoff_silence = (silence_start, silence_end)
        kind = "resolve_chime" if scene.role == "payoff" else "weight_hit"
        cues.append(AudioCue(silence_end, kind, "payoff", -7.0, min(0.30, duration - silence_end), -4.0))
    selected: list[AudioCue] = []
    for cue in sorted(cues, key=lambda item: item.at):
        if selected and cue.at - selected[-1].at < 0.075:
            if cue.kind in {"resolve_chime", "weight_hit"}:
                selected[-1] = cue
            continue
        selected.append(cue)
    ducking: list[DuckPoint] = [DuckPoint(0.0, 0.0)]
    for cue in selected:
        ducking.extend((
            DuckPoint(max(0.0, _snap(cue.at - 0.04)), 0.0),
            DuckPoint(cue.at, cue.duck_db),
            DuckPoint(min(duration, _snap(cue.at + cue.duration + 0.05)), 0.0),
        ))
    ducking = sorted({(point.at, point.voice_gain_db) for point in ducking})
    plan = AudioPlan(
        cues=tuple(selected),
        ducking=tuple(DuckPoint(at, gain) for at, gain in ducking),
        emphasis_times=tuple(emphasis_times),
        payoff_silence=payoff_silence,
    )
    plan.validate(duration)
    return plan


def audio_sync_score(plan: AudioPlan, scene: StoryScene) -> float:
    if not plan.cues:
        return 0.0
    score = 35.0
    first = plan.cues[0].at
    score += 20.0 if (scene.role != "hook" or first <= 0.10) else max(0.0, 20 - (first - .10) * 80)
    score += 22.0 if all(any(abs(c.at - target) <= .04 and c.kind == "number_tick" for c in plan.cues) for target in plan.emphasis_times) else 8.0
    score += 12.0 if any(point.voice_gain_db <= -3 for point in plan.ducking) else 0.0
    score += 8.0 if scene.role not in {"consequence", "payoff"} or (plan.payoff_silence and plan.payoff_silence[1] - plan.payoff_silence[0] >= .20) else 0.0
    score += 3.0 if all(b.at - a.at >= .075 for a, b in zip(plan.cues, plan.cues[1:])) else 0.0
    return round(min(100.0, score), 1)
