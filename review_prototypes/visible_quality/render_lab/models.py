from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Mapping

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 150, 250


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    def validate(self) -> None:
        if self.w <= 0 or self.h <= 0:
            raise ValueError("box dimensions must be positive")
        if self.x < 0 or self.y < 0 or self.x + self.w > W or self.y + self.h > H:
            raise ValueError("box must stay inside the 1080x1920 canvas")

    def overlaps(self, other: "Box", padding: float = 0) -> bool:
        return not (
            self.x + self.w + padding <= other.x
            or other.x + other.w + padding <= self.x
            or self.y + self.h + padding <= other.y
            or other.y + other.h + padding <= self.y
        )


@dataclass(frozen=True)
class CameraKeyframe:
    at: float
    scale: float
    x: float
    y: float
    easing: str

    def validate(self, duration: float) -> None:
        if not 0 <= self.at <= duration:
            raise ValueError("camera keyframe outside scene")
        if not 0.82 <= self.scale <= 1.30:
            raise ValueError("camera scale outside tasteful range")
        if self.easing not in {"linear", "ease_out", "ease_in_out", "overshoot"}:
            raise ValueError("unsupported camera easing")


@dataclass(frozen=True)
class CaptionAnimation:
    text: str
    start: float
    end: float
    box: Box
    enter: str
    exit: str
    emphasis: tuple[str, ...] = ()
    impact_at: float | None = None

    def validate(self, duration: float) -> None:
        self.box.validate()
        if not 0 <= self.start < self.end <= duration:
            raise ValueError("caption timing outside scene")
        if not 1 <= len(self.text.split()) <= 7:
            raise ValueError("caption must contain 1-7 words")
        if self.enter not in {"slam", "rise", "wipe", "type", "snap", "counter"}:
            raise ValueError("unsupported caption entrance")
        if self.exit not in {"cut", "fade", "shrink", "wipe"}:
            raise ValueError("unsupported caption exit")


@dataclass(frozen=True)
class SoundCue:
    at: float
    sound: str
    intensity: float
    sync_target: str
    duck_voice_db: float = 0.0

    def validate(self, duration: float) -> None:
        if not 0 <= self.at <= duration:
            raise ValueError("sound cue outside scene")
        if not 0 <= self.intensity <= 1:
            raise ValueError("sound intensity outside [0,1]")
        if not -9 <= self.duck_voice_db <= 0:
            raise ValueError("invalid voice ducking")


@dataclass(frozen=True)
class EffectKeyframe:
    at: float
    progress: float
    svg: str
    label: str

    def validate(self, duration: float) -> None:
        if not 0 <= self.at <= duration or not 0 <= self.progress <= 1:
            raise ValueError("invalid effect keyframe")
        if "<svg" not in self.svg or "</svg>" not in self.svg:
            raise ValueError("keyframe is not SVG")


@dataclass(frozen=True)
class RuntimeScene:
    scene_id: str
    role: str
    duration: float
    visual_event: str
    camera_move: str
    mascot_action: str
    callback_token: str
    captions: tuple[CaptionAnimation, ...]
    camera: tuple[CameraKeyframe, ...]
    sounds: tuple[SoundCue, ...]
    keyframes: tuple[EffectKeyframe, ...]
    metrics: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if self.duration < 1.2:
            raise ValueError("scene too short")
        if not self.keyframes or self.keyframes[0].at > 0.40:
            raise ValueError("visible action must begin by 0.40s")
        for item in self.captions:
            item.validate(self.duration)
        for item in self.camera:
            item.validate(self.duration)
        for item in self.sounds:
            item.validate(self.duration)
        for item in self.keyframes:
            item.validate(self.duration)
        for a, b in zip(self.captions, self.captions[1:]):
            if a.box.overlaps(b.box) and a.end > b.start + 0.05:
                raise ValueError("simultaneous captions overlap")


@dataclass(frozen=True)
class PreviewBundle:
    slug: str
    scenes: tuple[RuntimeScene, ...]
    total_duration: float
    opening_callback: str
    ending_callback: str
    quality_score: float
    failures: tuple[str, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.scenes:
            raise ValueError("preview requires scenes")
        for scene in self.scenes:
            scene.validate()
        if self.opening_callback != self.ending_callback or not self.opening_callback:
            raise ValueError("ending must reuse opening callback")
        if abs(self.total_duration - sum(s.duration for s in self.scenes)) > 0.01:
            raise ValueError("duration mismatch")

    def to_dict(self) -> dict:
        return asdict(self)
