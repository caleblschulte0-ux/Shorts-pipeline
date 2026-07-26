from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import DataValue, ProductionScene, ProductionStory, ROLES


def _read(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _values_from_insight(insight: Any) -> tuple[DataValue, ...]:
    items = _read(insight, "items", ()) or ()
    out: list[DataValue] = []
    for item in items:
        label = str(_read(item, "label", "")).strip()
        raw_value = _read(item, "value")
        if not label or raw_value is None:
            continue
        period = _read(item, "period")
        out.append(DataValue(label, float(raw_value), None if period is None else float(period)))
    return tuple(out)


def _infer_role(index: int, total: int, explicit: str) -> str:
    role = explicit.strip().lower()
    if role in ROLES:
        return role
    if index == 0:
        return "setup"
    if index == total - 1:
        return "consequence"
    return "explanation"


def adapt_story(story: Any) -> ProductionStory:
    """Convert the live pipeline's Story/Segment objects into a stable bridge model.

    This is intentionally duck-typed: Claude can run it against the current runtime
    objects without importing or changing production modules. Mapping fixtures work too.
    """
    raw_segments = tuple(_read(story, "segments", ()) or ())
    scenes: list[ProductionScene] = []
    for index, segment in enumerate(raw_segments):
        insight = _read(segment, "insight")
        values = _values_from_insight(insight)
        if not values:
            anchors = _read(segment, "anchors", ()) or ()
            values = tuple(
                DataValue(str(_read(anchor, "label", f"item_{i}")), float(_read(anchor, "value", 0)))
                for i, anchor in enumerate(anchors)
                if _read(anchor, "value") is not None
            )
        unit = str(_read(insight, "unit", "") or "")
        highlight = str(_read(insight, "highlight_label", "") or "")
        scene = ProductionScene(
            index=index,
            role=_infer_role(index, len(raw_segments), str(_read(segment, "role", "") or "")),
            sentence=str(_read(segment, "sentence", "") or "").strip(),
            topic=str(_read(segment, "topic", _read(insight, "topic", "")) or "").strip(),
            unit=unit,
            current_kind=str(_read(segment, "kind", _read(insight, "kind", "bubbles")) or "bubbles"),
            values=values,
            punches=tuple(_read(segment, "punches", ()) or ()),
            source_footer=str(_read(segment, "source_footer", "") or ""),
            host_baked=bool(_read(segment, "host_baked", False)),
            highlight_label=highlight,
        )
        scene.validate()
        scenes.append(scene)

    result = ProductionStory(
        slug=str(_read(story, "slug", "") or "").strip(),
        title=str(_read(story, "title", "") or "").strip(),
        hook=str(_read(story, "hook", "") or "").strip(),
        closing=str(_read(story, "closing", "") or "").strip(),
        scenes=tuple(scenes),
        question=str(_read(story, "question", "") or "").strip(),
        sources=tuple(str(source) for source in (_read(story, "sources", ()) or ())),
    )
    result.validate()
    return result


def story_to_mapping(story: ProductionStory) -> dict[str, Any]:
    return {
        "slug": story.slug,
        "title": story.title,
        "hook": story.hook,
        "closing": story.closing,
        "question": story.question,
        "sources": list(story.sources),
        "scenes": [
            {
                "index": scene.index,
                "role": scene.role,
                "sentence": scene.sentence,
                "topic": scene.topic,
                "unit": scene.unit,
                "current_kind": scene.current_kind,
                "values": [
                    {"label": value.label, "value": value.value, "period": value.period}
                    for value in scene.values
                ],
                "punches": list(scene.punches),
                "source_footer": scene.source_footer,
                "host_baked": scene.host_baked,
                "highlight_label": scene.highlight_label,
            }
            for scene in story.scenes
        ],
    }
