"""Content-addressed shot-cache and selective repair prototype."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class ShotFingerprint:
    beat_id: str
    scene_kind: str
    scene_parameters: Mapping[str, object]
    narration_text: str
    narration_duration_ms: int
    media_sha256: tuple[str, ...]
    renderer_version: str
    render_profile: str
    width: int
    height: int
    fps: int

    @property
    def key(self) -> str:
        payload = asdict(self)
        payload["scene_parameters"] = dict(self.scene_parameters)
        payload["media_sha256"] = list(self.media_sha256)
        return sha256(_canonical(payload)).hexdigest()


@dataclass(frozen=True)
class TimelineShot:
    shot_id: str
    beat_id: str
    fingerprint_key: str
    transition_in_id: str | None = None
    transition_out_id: str | None = None


@dataclass(frozen=True)
class RepairPlan:
    changed_beats: tuple[str, ...]
    rerender_shots: tuple[str, ...]
    rerender_transitions: tuple[str, ...]
    reusable_shots: tuple[str, ...]


def plan_repair(timeline: Iterable[TimelineShot], *, changed_beats: Iterable[str]) -> RepairPlan:
    shots = list(timeline)
    changed = set(changed_beats)
    rerender_shots: set[str] = set()
    rerender_transitions: set[str] = set()

    for index, shot in enumerate(shots):
        if shot.beat_id not in changed:
            continue
        rerender_shots.add(shot.shot_id)
        if shot.transition_in_id:
            rerender_transitions.add(shot.transition_in_id)
        if shot.transition_out_id:
            rerender_transitions.add(shot.transition_out_id)
        if index > 0 and shots[index - 1].transition_out_id:
            rerender_transitions.add(shots[index - 1].transition_out_id)
        if index + 1 < len(shots) and shots[index + 1].transition_in_id:
            rerender_transitions.add(shots[index + 1].transition_in_id)

    reusable = {shot.shot_id for shot in shots} - rerender_shots
    return RepairPlan(
        changed_beats=tuple(sorted(changed)),
        rerender_shots=tuple(sorted(rerender_shots)),
        rerender_transitions=tuple(sorted(rerender_transitions)),
        reusable_shots=tuple(sorted(reusable)),
    )
