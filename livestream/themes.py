"""Seasonal scene config for the livestream loop.

One channel, themed by season. Each theme is a detailed stylized SceneSpec
(sky, stars, aurora, horizon haze, sun/moon glow, drifting clouds, layered
ridges for depth, a tree-line foreground, low mist, a cozy cabin with a lit
window, near/far particles, grain) handed to the shared scene generator —
generated, stylized scenes, not stock footage and not photoreal. Retune a
season or add one here without touching render code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from shared.visualgen import RidgeLayer, SceneSpec


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    scene: SceneSpec


THEMES: dict[str, Theme] = {
    # Cool moonlit night: stars, aurora, cloud, mist, cabin, snowfall, blue hills.
    "winter": Theme("winter", "Winter — moonlit snowfall", SceneSpec(
        sky_top="071028", sky_bottom="2b4d8c",
        ridges=(
            RidgeLayer(0.60, "1a2e57", ((70, 280, 0.0), (26, 90, 0.6))),
            RidgeLayer(0.70, "111f3f", ((110, 190, 0.7), (44, 70, 1.2))),
            RidgeLayer(0.80, "070d20", ((60, 150, 0.2),), jag_amp=50, jag_period=24),
        ),
        glow=True, glow_x=0.70, glow_y=0.16, glow_radius=120, glow_color="eaf2ff",
        haze=True, haze_strength=120, stars=True, star_density=5,
        aurora=True, aurora_color="5cffb0", aurora_y=0.17, aurora_amp=90, aurora_strength=70,
        clouds=True, cloud_color="aeb9d6", cloud_y=0.30, cloud_strength=80, cloud_speed=1.0,
        fog=True, fog_y=0.66, fog_strength=70, fog_color="cfd8ea",
        cabin=True, cabin_x=0.30, window_color="ffcf6b",
        particles="snow", particle_color="ffffff", particle_density=10,
    )),
    # Pastel dawn: warm low sun, cloud, dawn mist, blossom, green hills + trees.
    "spring": Theme("spring", "Spring — blossom at dawn", SceneSpec(
        sky_top="ffd9e6", sky_bottom="9ad7e8",
        ridges=(
            RidgeLayer(0.62, "5a7d4a", ((70, 300, 0.3), (24, 80, 0.0))),
            RidgeLayer(0.72, "31532a", ((100, 200, 0.6), (40, 64, 1.0))),
            RidgeLayer(0.82, "16300f", ((50, 150, 0.2),), jag_amp=44, jag_period=26),
        ),
        glow=True, glow_x=0.30, glow_y=0.30, glow_radius=150, glow_color="fff2c4",
        haze=True, haze_strength=130, stars=False,
        clouds=True, cloud_color="ffffff", cloud_y=0.20, cloud_strength=120, cloud_speed=1.0,
        fog=True, fog_y=0.62, fog_strength=80, fog_color="fbe8f0",
        particles="leaves", particle_color="ffc6e0", particle_density=5,
    )),
    # Sunset coast: warm sun low, cloud, sea haze, dark headlands (no particles).
    "summer": Theme("summer", "Summer — sunset coast", SceneSpec(
        sky_top="3a2a78", sky_bottom="ff8a5b",
        ridges=(
            RidgeLayer(0.66, "5a2f52", ((50, 340, 0.0), (18, 100, 1.2))),
            RidgeLayer(0.76, "2e1630", ((70, 220, 0.5),)),
            RidgeLayer(0.85, "120a14", ((40, 160, 0.2),), jag_amp=40, jag_period=30),
        ),
        glow=True, glow_x=0.50, glow_y=0.62, glow_radius=150, glow_color="ffd27f",
        haze=True, haze_strength=150, stars=False,
        clouds=True, cloud_color="ffb98a", cloud_y=0.24, cloud_strength=120, cloud_speed=1.0,
        fog=True, fog_y=0.72, fog_strength=70, fog_color="ffd0b0",
        particles="none",
    )),
    # Amber dusk: low sun, stars, cloud, mist, cabin, falling leaves, rust hills.
    "autumn": Theme("autumn", "Autumn — falling leaves", SceneSpec(
        sky_top="3a2150", sky_bottom="e0883c",
        ridges=(
            RidgeLayer(0.62, "7a4a2a", ((80, 260, 0.4), (24, 80, 0.6))),
            RidgeLayer(0.72, "4a2812", ((100, 190, 0.7), (40, 66, 1.1))),
            RidgeLayer(0.82, "200e06", ((54, 150, 0.2),), jag_amp=48, jag_period=24),
        ),
        glow=True, glow_x=0.66, glow_y=0.40, glow_radius=140, glow_color="ffcaa0",
        haze=True, haze_strength=140, stars=True, star_density=3,
        clouds=True, cloud_color="ffc59a", cloud_y=0.22, cloud_strength=110, cloud_speed=1.0,
        fog=True, fog_y=0.66, fog_strength=80, fog_color="f0d2b0",
        cabin=True, cabin_x=0.70, window_color="ffd27f",
        particles="leaves", particle_color="ffae5a", particle_density=8,
    )),
    # Festive night: gold glow, aurora, cloud, mist, cabin, dense snow, green hills.
    "holiday": Theme("holiday", "Holiday — festive snowfall", SceneSpec(
        sky_top="14071a", sky_bottom="123a26",
        ridges=(
            RidgeLayer(0.60, "13402a", ((70, 280, 0.1), (26, 88, 0.5))),
            RidgeLayer(0.70, "0c2a1b", ((104, 188, 0.6), (44, 68, 1.3))),
            RidgeLayer(0.80, "06160e", ((58, 150, 0.2),), jag_amp=52, jag_period=22),
        ),
        glow=True, glow_x=0.72, glow_y=0.18, glow_radius=110, glow_color="ffd700",
        haze=True, haze_strength=120, stars=True, star_density=5,
        aurora=True, aurora_color="8affc8", aurora_y=0.14, aurora_amp=80, aurora_strength=60,
        clouds=True, cloud_color="9fb8c8", cloud_y=0.30, cloud_strength=70, cloud_speed=1.0,
        fog=True, fog_y=0.66, fog_strength=75, fog_color="cfe0d8",
        cabin=True, cabin_x=0.30, window_color="ffd27f",
        particles="snow", particle_color="ffffff", particle_density=13,
    )),
}

_SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


def theme_for_date(d: date) -> Theme:
    """Pick a theme from the calendar. December rotates to the holiday scene;
    other months map to their meteorological season."""
    if d.month == 12:
        return THEMES["holiday"]
    return THEMES[_SEASON_BY_MONTH[d.month]]
