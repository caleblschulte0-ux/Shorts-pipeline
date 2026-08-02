from __future__ import annotations

import re


def _rgb(value: str) -> tuple[float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("color must be six-digit hex")
    return tuple(int(value[i:i+2], 16) / 255 for i in (0, 2, 4))


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def contrast_ratio(foreground: str, background: str) -> float:
    fr, fg, fb = _rgb(foreground)
    br, bg, bb = _rgb(background)
    l1 = 0.2126 * _linear(fr) + 0.7152 * _linear(fg) + 0.0722 * _linear(fb)
    l2 = 0.2126 * _linear(br) + 0.7152 * _linear(bg) + 0.0722 * _linear(bb)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def numeric_emphasis(text: str) -> tuple[str, ...]:
    tokens = re.findall(r"(?:\$|\+|-)?\d[\d,.]*(?:%|×|x)?", text)
    return tuple(dict.fromkeys(token.rstrip(".,;:!?") for token in tokens))[:3]


def chunk_text(text: str, max_words: int = 6) -> tuple[str, ...]:
    words = text.split()
    if not words:
        raise ValueError("caption text required")
    chunks: list[list[str]] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        terminal = word.rstrip().endswith((".", "!", "?", ",", ":"))
        if len(current) >= max_words or (terminal and len(current) >= 3):
            chunks.append(current)
            current = []
    if current:
        if len(current) == 1 and chunks and len(chunks[-1]) < max_words:
            chunks[-1].extend(current)
        else:
            chunks.append(current)
    return tuple(" ".join(chunk) for chunk in chunks)
