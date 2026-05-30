"""Seasonal theme config for the livestream loop.

A theme is just a palette + motion speed + label, passed to the shared
visual-gen. Themes rotate by date (override with --theme). Add or retune
themes here without touching any render code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Theme:
    name: str
    colors: list[str]   # 2-8 hex stops, e.g. "0a1a3a"
    speed: float = 0.012
    label: str = ""


THEMES: dict[str, Theme] = {
    "winter": Theme("winter", ["0a1a3a", "1e3a6e", "a8c8ff"], 0.010, "Winter — cool blues"),
    "spring": Theme("spring", ["10331a", "3aa75a", "ffd1e8"], 0.014, "Spring — greens & blossom"),
    "summer": Theme("summer", ["07343a", "13a7a0", "ffd27f"], 0.016, "Summer — teal & gold"),
    "autumn": Theme("autumn", ["2a1206", "b5651d", "ff9f40"], 0.012, "Autumn — amber & rust"),
    # December special-cases to a holiday palette regardless of season mapping.
    "holiday": Theme("holiday", ["3a0a0a", "1e6e3a", "ffd700"], 0.012, "Holiday — red, green & gold"),
}

_SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


def theme_for_date(d: date) -> Theme:
    """Pick a theme from the calendar. December rotates to the holiday palette;
    other months map to their meteorological season."""
    if d.month == 12:
        return THEMES["holiday"]
    return THEMES[_SEASON_BY_MONTH[d.month]]
