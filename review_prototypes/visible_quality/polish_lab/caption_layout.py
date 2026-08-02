from __future__ import annotations

from typing import Iterable

from .caption_text import chunk_text, contrast_ratio, numeric_emphasis
from .models import Box, CaptionLayout, CaptionStyle

CANVAS = (1080, 1920)
RESERVED = (
    Box(0, 0, 1080, 180),
    Box(0, 1650, 1080, 270),
    Box(885, 470, 195, 1080),
)


def font_size_for(text: str, role: str, width: float) -> int:
    words = len(text.split())
    chars = len(text)
    base = 88 if role == "hook" else (78 if role == "payoff" else 64)
    penalty = max(0, words - 4) * 5 + max(0, chars - 28) // 7 * 3
    width_bonus = 8 if width >= 850 else (0 if width >= 680 else -8)
    return max(36, min(112, base - penalty + width_bonus))


def _candidate_boxes(role: str, height: float) -> tuple[Box, ...]:
    h = max(180, min(420, height))
    top = Box(70 if role == "hook" else 80, 210, 800 if role == "hook" else 790, h)
    bottom = Box(70 if role == "hook" else 80, 1280, 800 if role == "hook" else 790, h)
    middle = Box(90, 1160, 780, h)
    return (top, bottom, middle) if role == "hook" else (bottom, top, middle)


def choose_caption_box(role: str, lines: int, hero_box: Box, other_boxes: Iterable[Box] = ()) -> Box:
    blocked = (hero_box, *other_boxes, *RESERVED)
    for candidate in _candidate_boxes(role, 70 * max(1, lines) + 44):
        if not any(candidate.overlaps(box, padding=20) for box in blocked):
            return candidate
    raise ValueError("no collision-free caption position")


def layout_caption(text: str, role: str, duration: float, hero_box: Box, *, other_boxes: Iterable[Box] = ()) -> CaptionLayout:
    chunks = chunk_text(text)
    box = choose_caption_box(role, len(chunks[:3]), hero_box, other_boxes)
    size = font_size_for(max(chunks, key=len), role, box.width)
    result = CaptionLayout(
        text="\n".join(chunks[:3]),
        box=box,
        style=CaptionStyle(
            font_size=size,
            line_height=int(size * 1.16),
            weight=900 if role in {"hook", "payoff"} else 800,
            align="left" if box.x < 100 else "center",
            enter="slam" if role == "hook" else ("resolve" if role == "payoff" else "rise"),
            exit="cut" if role == "hook" else "fade",
            background_opacity=0.72,
        ),
        emphasis=numeric_emphasis(text),
        contrast_ratio=contrast_ratio("#F8FAFC", "#07101E"),
        start=0.04 if role == "hook" else 0.18,
        end=max(0.7, duration - (0.12 if role == "payoff" else 0.25)),
    )
    result.validate()
    return result


def platform_safe(box: Box) -> bool:
    return box.inside(*CANVAS) and not any(box.overlaps(zone, padding=8) for zone in RESERVED)
