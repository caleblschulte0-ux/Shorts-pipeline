from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class AudioBeatKind(str, Enum):
    HOOK = "hook"
    EXPLANATION = "explanation"
    DISCOVERY = "discovery"
    TRANSITION = "transition"
    PAYOFF = "payoff"


@dataclass(frozen=True)
class AudioBeat:
    beat_id: str
    start_seconds: float
    duration_seconds: float
    kind: AudioBeatKind
    narration_energy: float
    music_energy: float
    sfx_count: int = 0
    silence_ms: int = 0
    ducking_db: float = -6.0
    emphasis_hit: bool = False

    def __post_init__(self) -> None:
        if not self.beat_id.strip():
            raise ValueError("beat_id is required")
        if self.start_seconds < 0 or self.duration_seconds <= 0:
            raise ValueError("invalid audio timing")
        for value, name in ((self.narration_energy, "narration_energy"), (self.music_energy, "music_energy")):
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")
        if self.sfx_count < 0 or self.silence_ms < 0:
            raise ValueError("sfx_count and silence_ms must be nonnegative")
        if self.ducking_db > 0:
            raise ValueError("ducking_db must be zero or negative")


@dataclass(frozen=True)
class AudioDefect:
    code: str
    beat_id: str
    severity: int
    detail: str


@dataclass(frozen=True)
class AudioDynamicsReport:
    score: float
    defects: tuple[AudioDefect, ...]
    music_energy_range: float
    total_silence_ms: int
    accented_payoff_count: int


def analyze_audio_dynamics(beats: Iterable[AudioBeat]) -> AudioDynamicsReport:
    items = tuple(sorted(beats, key=lambda item: item.start_seconds))
    if len({item.beat_id for item in items}) != len(items):
        raise ValueError("duplicate beat_id")
    if not items:
        return AudioDynamicsReport(0.0, (AudioDefect("missing_audio_plan", "story", 4, "no audio beats supplied"),), 0.0, 0, 0)

    defects: list[AudioDefect] = []
    penalty = 0.0
    for item in items:
        if item.music_energy >= item.narration_energy and item.ducking_db > -5:
            defects.append(AudioDefect("narration_masking_risk", item.beat_id, 3, "music is not ducked enough under narration"))
            penalty += 0.75
        if item.sfx_count >= 4 and item.duration_seconds <= 6:
            defects.append(AudioDefect("overbusy_sound_design", item.beat_id, 2, "too many effects compete in a short beat"))
            penalty += 0.45
        if abs(item.music_energy - item.narration_energy) >= 5:
            defects.append(AudioDefect("energy_mismatch", item.beat_id, 2, "music and narration imply different emotional intensity"))
            penalty += 0.35
        if item.kind in {AudioBeatKind.HOOK, AudioBeatKind.PAYOFF} and not item.emphasis_hit:
            defects.append(AudioDefect("missing_audio_emphasis", item.beat_id, 3, f"{item.kind.value} lacks a deliberate audio accent"))
            penalty += 0.65

    energies = [item.music_energy for item in items]
    energy_range = max(energies) - min(energies)
    if len(items) >= 5 and energy_range < 2:
        defects.append(AudioDefect("flat_music_arc", "story", 3, "music energy barely changes across the video"))
        penalty += 0.8

    for index in range(len(items) - 2):
        window = items[index:index + 3]
        if all(item.silence_ms == 0 for item in window) and all(item.sfx_count > 0 for item in window):
            defects.append(AudioDefect("no_breathing_room", window[0].beat_id, 2, "three busy beats provide no silence"))
            penalty += 0.45

    total_silence = sum(item.silence_ms for item in items)
    runtime = max(item.start_seconds + item.duration_seconds for item in items)
    if runtime >= 60 and total_silence < 800:
        defects.append(AudioDefect("insufficient_global_silence", "story", 2, "the soundtrack never creates enough contrast"))
        penalty += 0.45

    payoff_count = sum(1 for item in items if item.kind is AudioBeatKind.PAYOFF and item.emphasis_hit)
    defects.sort(key=lambda item: (-item.severity, item.beat_id, item.code))
    return AudioDynamicsReport(round(max(0.0, 10.0 - penalty), 3), tuple(defects), round(energy_range, 3), total_silence, payoff_count)
