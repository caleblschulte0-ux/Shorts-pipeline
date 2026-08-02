from __future__ import annotations

from typing import Any, Mapping

from .contracts import ProductionStory, QualityBridgeBundle


def augment_manifest(base_manifest: Mapping[str, Any], bundle: QualityBridgeBundle) -> dict[str, Any]:
    """Return a richer manifest without removing or renaming production fields."""
    bundle.validate()
    out = dict(base_manifest)
    windows = out.get("segment_windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("production manifest must retain segment_windows")
    out["quality_bridge"] = {
        "version": bundle.version,
        "story_fingerprint": bundle.story_fingerprint,
        "callback_token": bundle.callback_token,
        "scene_plans": [
            {
                "segment_index": override.segment_index,
                "kind": override.kind,
                "performance": override.performance,
                "role": override.role,
                "target": override.target,
                "goal": override.goal,
                "callback_token": override.callback_token,
                "timeline": dict(override.scene_timeline),
                "audio_cues": [dict(cue) for cue in override.audio_cues],
                "transition_in": None if override.transition_in is None else dict(override.transition_in),
            }
            for override in bundle.overrides
        ],
    }
    return out


def showrunner_context(story: ProductionStory, bundle: QualityBridgeBundle) -> dict[str, Any]:
    story.validate()
    bundle.validate()
    return {
        "slug": story.slug,
        "title": story.title,
        "hook": story.hook,
        "closing": story.closing,
        "segments": [scene.sentence for scene in story.scenes][:8],
        "quality_bridge": {
            "version": bundle.version,
            "callback_token": bundle.callback_token,
            "scene_plans": [
                {
                    "seg": override.segment_index,
                    "role": override.role,
                    "kind": override.kind,
                    "performance": override.performance,
                    "goal": override.goal,
                    "target": override.target,
                    "timeline": dict(override.scene_timeline),
                    "transition_in": override.transition_in,
                }
                for override in bundle.overrides
            ],
        },
    }
