from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping

W, H = 1080, 1920


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

    @property
    def area(self) -> float:
        return self.width * self.height

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("box dimensions must be positive")
        if self.x < 0 or self.y < 0 or self.right > W or self.bottom > H:
            raise ValueError("box must stay inside 1080x1920")

    def overlaps(self, other: "Box", padding: float = 0) -> bool:
        return not (
            self.right + padding <= other.x
            or other.right + padding <= self.x
            or self.bottom + padding <= other.y
            or other.bottom + padding <= self.y
        )


@dataclass(frozen=True)
class StoryScene:
    scene_id: str
    role: str
    narration: str
    visual_event: str
    focus: str
    duration: float
    callback_token: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object], index: int) -> "StoryScene":
        scene = cls(
            scene_id=str(raw.get("scene_id", f"scene_{index:02d}")),
            role=str(raw.get("role", "explanation")),
            narration=str(raw.get("narration", "")).strip(),
            visual_event=str(raw.get("visual_event", "physical_demonstration")).strip(),
            focus=str(raw.get("focus", raw.get("focal_label", "datum"))).strip(),
            duration=float(raw.get("duration", 3.6)),
            callback_token=str(raw.get("callback_token", "")).strip(),
        )
        scene.validate()
        return scene

    def validate(self) -> None:
        if self.role not in {"hook", "setup", "explanation", "consequence", "payoff"}:
            raise ValueError(f"unsupported role: {self.role}")
        if not self.narration or not self.visual_event or not self.focus:
            raise ValueError("scene requires narration, visual_event, and focus")
        if not 1.2 <= self.duration <= 8.0:
            raise ValueError("scene duration out of range")


@dataclass(frozen=True)
class LayoutSpec:
    hero: Box
    caption: Box
    secondary: Box | None
    hero_anchor: str
    occupancy: float

    def validate(self) -> None:
        self.hero.validate()
        self.caption.validate()
        if self.secondary:
            self.secondary.validate()
        if self.hero.overlaps(self.caption, padding=18):
            raise ValueError("caption overlaps hero")
        if self.secondary and self.caption.overlaps(self.secondary, padding=12):
            raise ValueError("caption overlaps secondary visual")
        if not 0.0 < self.occupancy <= 1.0:
            raise ValueError("invalid occupancy")


@dataclass(frozen=True)
class AudioCue:
    at: float
    kind: str
    target: str
    gain_db: float
    duration: float
    duck_db: float

    def validate(self, scene_duration: float) -> None:
        if not 0 <= self.at <= scene_duration:
            raise ValueError("audio cue outside scene")
        if self.duration <= 0 or self.at + self.duration > scene_duration + 0.02:
            raise ValueError("audio cue duration outside scene")
        if not -30 <= self.gain_db <= 0 or not -12 <= self.duck_db <= 0:
            raise ValueError("audio gain outside bounds")


@dataclass(frozen=True)
class DuckPoint:
    at: float
    voice_gain_db: float


@dataclass(frozen=True)
class AudioPlan:
    cues: tuple[AudioCue, ...]
    ducking: tuple[DuckPoint, ...]
    emphasis_times: tuple[float, ...]
    payoff_silence: tuple[float, float] | None
    integrated_lufs_target: float = -14.0
    true_peak_dbtp: float = -1.2

    def validate(self, duration: float) -> None:
        for cue in self.cues:
            cue.validate(duration)
        if tuple(sorted(c.at for c in self.cues)) != tuple(c.at for c in self.cues):
            raise ValueError("audio cues must be sorted")
        if self.payoff_silence:
            start, end = self.payoff_silence
            if not 0 <= start < end <= duration:
                raise ValueError("invalid payoff silence")
        if not -16 <= self.integrated_lufs_target <= -12:
            raise ValueError("loudness target out of range")
        if self.true_peak_dbtp > -1.0:
            raise ValueError("true peak too high")


@dataclass(frozen=True)
class MotionKeyframe:
    at: float
    x: float
    y: float
    scale: float
    rotation: float
    ease: str


@dataclass(frozen=True)
class MotionPlan:
    object_id: str
    entry_edge: str
    exit_edge: str
    keyframes: tuple[MotionKeyframe, ...]
    first_motion_at: float
    carries_focus: bool

    def validate(self, duration: float) -> None:
        if self.entry_edge not in {"left", "right", "top", "bottom", "center"}:
            raise ValueError("invalid entry edge")
        if self.exit_edge not in {"left", "right", "top", "bottom", "center", "camera"}:
            raise ValueError("invalid exit edge")
        if not self.keyframes or self.keyframes[0].at != 0.0:
            raise ValueError("motion must begin at t=0")
        if self.first_motion_at > 0.25:
            raise ValueError("visible motion starts too late")
        if any(not 0 <= frame.at <= duration for frame in self.keyframes):
            raise ValueError("motion frame outside scene")


@dataclass(frozen=True)
class TransitionBridge:
    kind: str
    duration: float
    shared_object: str
    outgoing_edge: str
    incoming_edge: str
    sound: str
    continuity_score: float

    def validate(self) -> None:
        if self.kind not in {
            "object_match", "number_match", "data_morph", "momentum_match",
            "impact_cut", "callback_return", "focus_pull",
        }:
            raise ValueError("unsupported transition")
        if not 0.08 <= self.duration <= 0.45:
            raise ValueError("transition duration out of range")
        if not 0 <= self.continuity_score <= 100:
            raise ValueError("invalid continuity score")


@dataclass(frozen=True)
class RhythmBeat:
    at: float
    kind: str
    intensity: float


@dataclass(frozen=True)
class SceneContinuity:
    scene: StoryScene
    layout: LayoutSpec
    audio: AudioPlan
    motion: MotionPlan
    rhythm: tuple[RhythmBeat, ...]
    svg: str

    def validate(self) -> None:
        self.scene.validate()
        self.layout.validate()
        self.audio.validate(self.scene.duration)
        self.motion.validate(self.scene.duration)
        if not self.svg.startswith("<svg") or "1080" not in self.svg or "1920" not in self.svg:
            raise ValueError("scene requires deterministic 1080x1920 svg")
        if not self.rhythm or self.rhythm[0].at > 0.15:
            raise ValueError("scene rhythm starts too late")


@dataclass(frozen=True)
class ContinuityBundle:
    slug: str
    archetype: str
    scenes: tuple[SceneContinuity, ...]
    transitions: tuple[TransitionBridge, ...]
    callback_token: str
    quality_score: float
    dimensions: Mapping[str, float] = field(default_factory=dict)
    failures: tuple[str, ...] = ()

    def validate(self) -> None:
        if len(self.scenes) < 3 or len(self.transitions) != len(self.scenes) - 1:
            raise ValueError("bundle requires complete scene/transition chain")
        for scene in self.scenes:
            scene.validate()
        for transition in self.transitions:
            transition.validate()
        if self.scenes[0].scene.role != "hook" or self.scenes[-1].scene.role != "payoff":
            raise ValueError("bundle must start with hook and end with payoff")
        if not self.callback_token:
            raise ValueError("bundle requires callback token")
        if self.failures and self.quality_score > 69:
            raise ValueError("failed bundle cannot score above hold threshold")

    def to_dict(self) -> dict:
        return asdict(self)
