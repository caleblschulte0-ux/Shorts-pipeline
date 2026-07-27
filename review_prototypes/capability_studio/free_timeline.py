from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Mapping

from .contracts import CommandPlan, stable_id


@dataclass(frozen=True)
class TimelineClip:
    name: str
    source: str
    timeline_start: float
    source_start: float
    duration: float
    track: str = "video"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeline_start < 0 or self.source_start < 0 or self.duration <= 0:
            raise ValueError("timeline_start/source_start must be nonnegative and duration must be positive")


@dataclass(frozen=True)
class TimelineDocument:
    name: str
    fps: int
    clips: tuple[TimelineClip, ...]
    width: int = 1080
    height: int = 1920

    @property
    def timeline_id(self) -> str:
        return stable_id("timeline", asdict(self))

    def to_otio_dict(self) -> dict[str, object]:
        tracks: dict[str, list[TimelineClip]] = {}
        for clip in self.clips:
            tracks.setdefault(clip.track, []).append(clip)
        children = []
        for track_name, clips in sorted(tracks.items()):
            ordered = sorted(clips, key=lambda item: item.timeline_start)
            track_children: list[dict[str, object]] = []
            cursor = 0.0
            for clip in ordered:
                if clip.timeline_start > cursor:
                    gap_duration = clip.timeline_start - cursor
                    track_children.append({"OTIO_SCHEMA": "Gap.1", "source_range": _time_range(0, gap_duration, self.fps)})
                track_children.append({
                    "OTIO_SCHEMA": "Clip.2",
                    "name": clip.name,
                    "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": clip.source},
                    "source_range": _time_range(clip.source_start, clip.duration, self.fps),
                    "metadata": dict(clip.metadata),
                })
                cursor = clip.timeline_start + clip.duration
            children.append({"OTIO_SCHEMA": "Track.1", "name": track_name, "kind": "Audio" if track_name.startswith("audio") else "Video", "children": track_children})
        return {
            "OTIO_SCHEMA": "Timeline.1", "name": self.name,
            "metadata": {"timeline_id": self.timeline_id, "width": self.width, "height": self.height, "fps": self.fps},
            "tracks": {"OTIO_SCHEMA": "Stack.1", "children": children},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_otio_dict(), indent=2, sort_keys=True)


def _time_range(start_seconds: float, duration_seconds: float, fps: int) -> dict[str, object]:
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "start_time": {"OTIO_SCHEMA": "RationalTime.1", "value": round(start_seconds * fps), "rate": fps},
        "duration": {"OTIO_SCHEMA": "RationalTime.1", "value": round(duration_seconds * fps), "rate": fps},
    }


class TimelineCommandPlanner:
    def validate_otio(self, timeline_json: str) -> CommandPlan:
        output = str(Path(timeline_json).with_suffix(".validated.otio"))
        return CommandPlan("opentimelineio", ("otioconvert", "-i", timeline_json, "-o", output), inputs=(timeline_json,), outputs=(output,))

    def moviepy_render(self, timeline_json: str, output: str) -> CommandPlan:
        return CommandPlan("moviepy", ("python", "-m", "review_prototypes.capability_studio.free_workers", "moviepy-render", "--timeline", timeline_json, "--output", output), inputs=(timeline_json,), outputs=(output,), notes=("MoviePy is an optional convenience renderer; FFmpeg remains the deterministic default.",))

    def ffmpeg_concat(self, concat_file: str, output: str) -> CommandPlan:
        return CommandPlan("ffmpeg", ("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", output), inputs=(concat_file,), outputs=(output,))
