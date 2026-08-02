from __future__ import annotations

from .models import AudioCue, AudioPlan, CaptionLayout

EVENT_SOUNDS = {
    "collision": ("impact_low", "impact"),
    "slam": ("impact_short", "impact"),
    "gap": ("elastic_stretch", "motion"),
    "line": ("rising_tension", "motion"),
    "trend": ("rising_tension", "motion"),
    "stack": ("weight_clunk", "impact"),
    "receipt": ("paper_roll", "texture"),
    "cart": ("cart_rattle", "texture"),
    "squeeze": ("rubber_squeeze", "motion"),
    "race": ("fast_whoosh", "motion"),
    "callback": ("resolve_chime", "payoff"),
    "opening": ("resolve_chime", "payoff"),
}


def _event_sound(event: str) -> tuple[str, str]:
    low = event.lower()
    for token, value in EVENT_SOUNDS.items():
        if token in low:
            return value
    return "soft_whoosh", "motion"


def compile_audio(event: str, caption: CaptionLayout, duration: float, role: str) -> AudioPlan:
    cues: list[AudioCue] = []
    primary_name, primary_role = _event_sound(event)
    primary_at = 0.06 if role == "hook" else min(0.28, duration * 0.10)
    cues.append(AudioCue(primary_at, primary_name, primary_role, -8.0, 0.20, -2.5))

    for idx, _token in enumerate(caption.emphasis[:2]):
        at = min(duration - 0.25, caption.start + 0.34 + idx * 0.48)
        cues.append(AudioCue(at, "number_tick", "caption", -13.0, 0.09, -1.5))

    payoff_silence = None
    if role in {"consequence", "payoff"} and duration >= 2.0:
        silence_end = max(0.6, duration - 0.58)
        silence_start = max(0.3, silence_end - 0.18)
        payoff_silence = (round(silence_start, 2), round(silence_end, 2))
        payoff_name = "resolve_chime" if role == "payoff" else "weight_hit"
        cues.append(AudioCue(round(silence_end, 2), payoff_name, "payoff", -7.0, min(0.32, duration-silence_end), -3.5))

    priority = {"payoff": 4, "impact": 3, "caption": 2, "motion": 1, "texture": 0}
    selected: list[AudioCue] = []
    for cue in sorted(cues, key=lambda c: (c.at, -priority.get(c.role, 0))):
        if selected and abs(cue.at - selected[-1].at) < 0.07:
            if priority.get(cue.role, 0) > priority.get(selected[-1].role, 0):
                selected[-1] = cue
            continue
        selected.append(cue)

    plan = AudioPlan(
        duration=duration,
        cues=tuple(sorted(selected, key=lambda cue: cue.at)),
        payoff_silence=payoff_silence,
        integrated_lufs_target=-14.0,
        true_peak_dbtp=-1.2,
    )
    plan.validate()
    return plan


def audio_sync_score(plan: AudioPlan, caption: CaptionLayout) -> float:
    if not plan.cues:
        return 0.0
    emphasis_hits = sum(
        1 for token_index, _ in enumerate(caption.emphasis[:2])
        if any(cue.role == "caption" and cue.at >= caption.start for cue in plan.cues[token_index:])
    )
    first_motion = min(cue.at for cue in plan.cues)
    score = 55.0
    score += min(25.0, emphasis_hits * 12.5)
    score += 15.0 if first_motion <= 0.30 else max(0, 15 - (first_motion - .30) * 30)
    score += 5.0 if plan.payoff_silence else 0.0
    return round(min(100.0, score), 1)
