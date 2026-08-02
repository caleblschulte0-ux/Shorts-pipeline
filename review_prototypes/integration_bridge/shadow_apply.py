from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .contracts import QualityBridgeBundle


def _read(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _write(obj: Any, name: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[name] = value
    else:
        setattr(obj, name, value)


def apply_to_copy(story: Any, bundle: QualityBridgeBundle) -> Any:
    """Apply bridge overrides to a deep copy of a live Story object.

    The original is never mutated. The copy uses extension points already consumed
    by production charts/studio_render: insight.kind, insight.perf_override,
    insight.plan_locked, segment.kind and a structured scene_plan sidecar.
    """
    bundle.validate()
    clone = copy.deepcopy(story)
    segments = list(_read(clone, "segments", ()) or ())
    if len(segments) != len(bundle.overrides):
        raise ValueError("story segment count does not match bridge bundle")
    for segment, override in zip(segments, bundle.overrides):
        insight = _read(segment, "insight")
        if insight is None:
            raise ValueError(f"segment {override.segment_index} has no insight")
        _write(insight, "kind", override.kind)
        _write(insight, "perf_override", override.performance)
        _write(insight, "plan_locked", True)
        _write(insight, "quality_scene_plan", dict(override.scene_timeline))
        _write(segment, "kind", override.kind)
        _write(segment, "quality_scene_plan", dict(override.scene_timeline))
        _write(segment, "quality_audio_cues", [dict(cue) for cue in override.audio_cues])
        _write(segment, "quality_transition_in", None if override.transition_in is None else dict(override.transition_in))
        _write(segment, "quality_callback_token", override.callback_token)
    _write(clone, "quality_bridge_version", bundle.version)
    _write(clone, "quality_story_fingerprint", bundle.story_fingerprint)
    return clone


def existing_scene_plan_schema(bundle: QualityBridgeBundle) -> dict[str, dict[str, str]]:
    """Backward-compatible payload for state/scene_plans/{slug}.json.

    Existing scene_repair.py only reads/writes `viz` + `perf`, so this deliberately
    emits that exact minimal schema. Rich metadata belongs in the manifest sidecar.
    """
    return {
        str(override.segment_index): {"viz": override.kind, "perf": override.performance}
        for override in bundle.overrides
    }
