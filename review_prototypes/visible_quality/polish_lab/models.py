from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def overlaps(self, other: "Box", padding: float = 0.0) -> bool:
        return not (
            self.right + padding <= other.x
            or other.right + padding <= self.x
            or self.bottom + padding <= other.y
            or other.bottom + padding <= self.y
        )

    def inside(self, width: float, height: float) -> bool:
        return self.x >= 0 and self.y >= 0 and self.right <= width and self.bottom <= height


@dataclass(frozen=True)
class CaptionStyle:
    font_size: int
    line_height: int
    weight: int
    align: str
    enter: str
    exit: str
    background_opacity: float


@dataclass(frozen=True)
class CaptionLayout:
    text: str
    box: Box
    style: CaptionStyle
    emphasis: tuple[str, ...]
    contrast_ratio: float
    start: float
    end: float

    def validate(self, canvas=(1080, 1920)) -> None:
        if not self.box.inside(*canvas):
            raise ValueError("caption outside canvas")
        if self.contrast_ratio < 4.5:
            raise ValueError("caption contrast below 4.5:1")
        if not 30 <= self.style.font_size <= 112:
            raise ValueError("caption font size outside supported range")
        if self.end <= self.start:
            raise ValueError("caption timing invalid")


@dataclass(frozen=True)
class AudioCue:
    at: float
    name: str
    role: str
    gain_db: float
    duration: float
    duck_voice_db: float = 0.0


@dataclass(frozen=True)
class AudioPlan:
    duration: float
    cues: tuple[AudioCue, ...]
    payoff_silence: tuple[float, float] | None
    integrated_lufs_target: float
    true_peak_dbtp: float

    def validate(self) -> None:
        if not -16.0 <= self.integrated_lufs_target <= -12.0:
            raise ValueError("loudness target outside Shorts-safe range")
        if self.true_peak_dbtp > -1.0:
            raise ValueError("true peak too high")
        if len(self.cues) > max(5, int(self.duration * 1.25)):
            raise ValueError("sound cue density too high")
        ordered = sorted(self.cues, key=lambda cue: cue.at)
        if tuple(ordered) != self.cues:
            raise ValueError("audio cues must be sorted")
        if any(cue.at < 0 or cue.at + cue.duration > self.duration + 0.01 for cue in self.cues):
            raise ValueError("audio cue outside scene")


@dataclass(frozen=True)
class TransitionSpec:
    kind: str
    duration: float
    shared_object: str
    outgoing_action: str
    incoming_action: str
    sound: str
    continuity_score: float

    def validate(self) -> None:
        if self.kind not in {"object_match", "number_match", "data_morph", "impact_cut", "callback_return", "whip_pan"}:
            raise ValueError("unsupported transition")
        if not 0.08 <= self.duration <= 0.45:
            raise ValueError("transition duration outside range")
        if not 0 <= self.continuity_score <= 100:
            raise ValueError("continuity score outside range")


@dataclass(frozen=True)
class TensionBeat:
    scene_id: str
    role: str
    intensity: float
    uncertainty: float
    consequence: float
    release: float

    @property
    def net(self) -> float:
        return round(self.intensity * 0.45 + self.uncertainty * 0.20 + self.consequence * 0.35 - self.release * 0.25, 2)


@dataclass(frozen=True)
class TensionPlan:
    beats: tuple[TensionBeat, ...]
    peak_scene: str
    payoff_drop: float
    plateau_count: int

    def validate(self) -> None:
        if len(self.beats) < 3:
            raise ValueError("tension plan needs at least three beats")
        if self.beats[0].role != "hook" or self.beats[-1].role != "payoff":
            raise ValueError("tension plan must start with hook and end with payoff")
        if self.plateau_count > 1:
            raise ValueError("too many tension plateaus")
        if self.payoff_drop < 10:
            raise ValueError("payoff does not release enough tension")


@dataclass(frozen=True)
class StoryArchetype:
    name: str
    unit: str
    data_shape: str
    hook_mechanics: tuple[str, ...]
    body_mechanics: tuple[str, ...]
    payoff_mechanic: str


@dataclass(frozen=True)
class ScenePolish:
    scene_id: str
    role: str
    visual_event: str
    caption: CaptionLayout
    audio: AudioPlan
    tension: TensionBeat
    hero_box: Box
    platform_safe: bool


@dataclass(frozen=True)
class StoryPolishBundle:
    slug: str
    archetype: str
    scenes: tuple[ScenePolish, ...]
    transitions: tuple[TransitionSpec, ...]
    tension: TensionPlan
    callback_token: str
    score: float
    dimensions: Mapping[str, float]
    failures: tuple[str, ...] = ()

    def validate(self) -> None:
        if len(self.transitions) != max(0, len(self.scenes) - 1):
            raise ValueError("transition count mismatch")
        for scene in self.scenes:
            scene.caption.validate()
            scene.audio.validate()
            if not scene.platform_safe:
                raise ValueError("scene violates platform safe areas")
        for transition in self.transitions:
            transition.validate()
        self.tension.validate()
        if self.failures:
            raise ValueError("bundle contains hard failures")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SprintScorecard:
    scope: str
    dimensions: Mapping[str, float]
    overall_percent: float
    production_pipeline_modified: bool = False
    evidence: Mapping[str, object] = field(default_factory=dict)
