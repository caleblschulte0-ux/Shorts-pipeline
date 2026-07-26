from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .models import Box, CameraKeyframe, CaptionAnimation, SoundCue


def _tokens(text: str) -> list[str]:
    return re.findall(r"\$?[A-Za-z0-9,.%×+\-]+(?:'[A-Za-z]+)?|[!?]", text)


def _emphasis(words: Iterable[str]) -> tuple[str, ...]:
    ranked: list[tuple[int, str]] = []
    for word in words:
        clean = re.sub(r"[^A-Za-z0-9$%×+\-]", "", word)
        score = 0
        score += 5 if any(c.isdigit() for c in clean) else 0
        score += 3 if any(c in clean for c in "$%×+−-") else 0
        score += 2 if clean.lower() in {"more", "less", "double", "half", "only", "now"} else 0
        if score:
            ranked.append((score, clean))
    return tuple(word for _, word in sorted(ranked, reverse=True)[:2])


def compile_captions(text: str, duration: float, role: str) -> tuple[CaptionAnimation, ...]:
    words = _tokens(text)
    if not words:
        raise ValueError("caption source cannot be empty")
    chunks: list[list[str]] = []
    current: list[str] = []
    max_words = 4 if role == "hook" else 6
    for word in words:
        current.append(word)
        if len(current) >= max_words or word in {"!", "?"}:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    if len(chunks) > 1 and len(chunks[-1]) == 1 and not any(c.isdigit() for c in chunks[-1][0]):
        chunks[-2].extend(chunks.pop())

    usable = max(0.8, duration - 0.30)
    weights = [max(1.0, len(c) ** 0.85) for c in chunks]
    total = sum(weights)
    at = 0.12
    result: list[CaptionAnimation] = []
    for i, (chunk, weight) in enumerate(zip(chunks, weights)):
        span = usable * weight / total
        text_chunk = " ".join(chunk).replace(" !", "!").replace(" ?", "?")
        emph = _emphasis(chunk)
        numeric = any(any(c.isdigit() for c in token) for token in chunk)
        enter = "slam" if role == "hook" and i == 0 else ("counter" if numeric else ("wipe" if i % 2 else "rise"))
        exit_style = "cut" if role == "hook" else ("wipe" if i < len(chunks) - 1 else "fade")
        y = 1380 if role != "hook" else 1260
        if i % 2 and role not in {"hook", "payoff"}:
            y -= 72
        result.append(CaptionAnimation(
            text=text_chunk,
            start=round(at, 3),
            end=round(min(duration - 0.05, at + span), 3),
            box=Box(90, y, 900, 210),
            enter=enter,
            exit=exit_style,
            emphasis=emph,
            impact_at=round(at + 0.08, 3) if (numeric or role == "hook") else None,
        ))
        at += span
    return tuple(result)


CAMERA_RECIPES = {
    "snap_push_in": ((0.0, 1.00, 540, 960, "linear"), (0.18, 1.16, 540, 920, "overshoot"), (1.0, 1.08, 540, 960, "ease_out")),
    "follow_tip": ((0.0, 1.02, 500, 1050, "linear"), (0.55, 1.10, 590, 830, "ease_in_out"), (1.0, 1.06, 640, 720, "ease_out")),
    "counter_pan": ((0.0, 1.07, 650, 930, "linear"), (0.5, 1.10, 470, 900, "ease_in_out"), (1.0, 1.05, 560, 860, "ease_out")),
    "pressure_pull_back": ((0.0, 1.17, 540, 1020, "linear"), (0.65, 1.02, 540, 920, "ease_out"), (1.0, 0.96, 540, 900, "ease_out")),
    "gap_dolly": ((0.0, 1.04, 500, 960, "linear"), (0.60, 1.13, 590, 950, "ease_in_out"), (1.0, 1.08, 540, 930, "ease_out")),
    "row_track": ((0.0, 1.05, 470, 960, "linear"), (0.55, 1.08, 620, 960, "ease_in_out"), (1.0, 1.04, 540, 930, "ease_out")),
    "side_track": ((0.0, 1.06, 420, 960, "linear"), (0.55, 1.10, 650, 960, "ease_in_out"), (1.0, 1.04, 560, 930, "ease_out")),
    "slow_push": ((0.0, 1.00, 540, 960, "linear"), (1.0, 1.08, 540, 900, "ease_in_out")),
    "callback_pull_back": ((0.0, 1.12, 540, 900, "linear"), (0.58, 1.00, 540, 940, "ease_out"), (1.0, 0.94, 540, 960, "ease_out")),
}


def compile_camera(move: str, duration: float) -> tuple[CameraKeyframe, ...]:
    recipe = CAMERA_RECIPES.get(move, CAMERA_RECIPES["slow_push"])
    return tuple(CameraKeyframe(round(f * duration, 3), scale, x, y, easing) for f, scale, x, y, easing in recipe)


SOUND_MAP = {
    "slam": "low_thump",
    "gap": "elastic_stretch",
    "line": "riser_tension",
    "yank": "rope_snap",
    "stack": "weight_clack",
    "impact": "number_hit",
    "callback": "memory_chime",
    "squeeze": "rubber_squeak",
    "race": "short_whoosh",
    "gauge": "dial_sweep",
}


def compile_sounds(visual_event: str, captions: tuple[CaptionAnimation, ...], duration: float) -> tuple[SoundCue, ...]:
    low = visual_event.lower()
    cues: list[SoundCue] = []
    event_keys = [key for key in SOUND_MAP if key in low]
    if not event_keys:
        event_keys = ["impact"]
    for i, key in enumerate(event_keys[:2]):
        at = 0.08 if i == 0 else min(duration * 0.55, duration - 0.1)
        cues.append(SoundCue(round(at, 3), SOUND_MAP[key], 0.76 if i == 0 else 0.55, visual_event, -1.5))
    for caption in captions:
        if caption.impact_at is not None:
            cues.append(SoundCue(caption.impact_at, "caption_tick", 0.24, caption.text, 0.0))
    unique: dict[tuple[float, str], SoundCue] = {}
    for cue in cues:
        unique[(cue.at, cue.sound)] = cue
    return tuple(sorted(unique.values(), key=lambda c: c.at)[:5])


def varied_moves(moves: Iterable[str]) -> bool:
    seq = list(moves)
    return all(a != b or b != c for a, b, c in zip(seq, seq[1:], seq[2:]))


def action_repetition(actions: Iterable[str]) -> float:
    seq = list(actions)
    if not seq:
        return 0.0
    counts = Counter(seq)
    return max(counts.values()) / len(seq)
