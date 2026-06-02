"""Cabin Hours — the lo-fi channel's visual worlds.

The brand's visual anchor is a warm-lit log cabin by a frozen pond. Each "world"
is a detailed stylized SceneSpec (sky, stars, aurora, haze, moon glow, drifting
clouds, mist, the cabin homestead, a skating pond, near/far particles, grain)
rendered entirely by the shared scene generator — generated stylized scenes, not
stock footage and not photoreal (a human-made / no-stock-footage signal).

Each world also carries the packaging metadata Cabin Hours publishes with:
a context-first `title` ([scene] + [listener task] + [palette]), the primary
`task`, the sonic `palette`, and the context `playlists` it feeds. The calendar
maps months to a world (see theme_for_date); see BRAND.md for the full playbook.
Retune or add a world here without touching render code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from shared.visualgen import Building, RidgeLayer, SceneSpec


def _homestead(cabin_x: float, barn_x: float, win: str,
               base: float = 0.885, scale: float = 1.0) -> tuple:
    """A cabin plus a small barn, for a cozy little homestead. `scale`<1 and a higher
    `base` push it back to the far shore behind the lake."""
    def px(v):
        return max(8, int(v * scale))
    cabin = Building(
        x=cabin_x, base=base, w=px(264), bh=px(178), rh=px(120), win_color=win,
        wood="3a2418", roof="33333c",
    )
    barn = Building(
        x=barn_x, base=base + 0.01, w=px(210), bh=px(128), rh=px(82), win_color=win,
        wood="3a201a", roof="262026", eaves=0.16,
        windows=((0.0, 0.24, 0.26, 0.22, "cross"),),       # hayloft window
        door=(0.0, 0.74, 0.36, 0.48),                       # big barn door
        chimney=False, smoke=False, spill=True,
    )
    return (barn, cabin) if barn_x < cabin_x else (cabin, barn)


@dataclass(frozen=True)
class Theme:
    name: str                 # calendar key
    world: str                # the lo-fi "world" (visual identity)
    title: str                # context-first upload title: [scene] + [task] + [palette]
    task: str                 # primary listener task this world serves
    palette: str              # sonic palette tag
    playlists: tuple          # context playlists this world feeds
    scene: SceneSpec


THEMES: dict[str, Theme] = {
    # Snowfall Cabin — moonlit night: stars, aurora, mist, homestead, skating pond.
    "winter": Theme(
        "winter",
        world="Snowfall Cabin",
        title="Snowfall Study — lofi beats to focus & relax",
        task="study / focus",
        palette="warm lofi, no lyrics",
        playlists=("Focus", "Sleep", "Rainy Café"),
        scene=SceneSpec(
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
        fog=True, fog_y=0.66, fog_strength=70, fog_color="cfd8ea", fog_speed=0.4,
        snow_ground=True, snow_ground_y=0.78,
        pond=True, pond_x=0.54, pond_y=0.88, pond_w=660, pond_h=180, skaters=4,
        buildings=_homestead(cabin_x=0.24, barn_x=0.40, win="ffc664", base=0.78, scale=0.76),
        shooting_star=True,
        particles="snow", particle_color="ffffff", particle_density=10,
    )),
    # Dawn Blossom — pastel sunrise: warm low sun, cloud, dawn mist, blossom drift.
    "spring": Theme(
        "spring",
        world="Dawn Blossom",
        title="Spring Morning — lofi to ease into the day",
        task="morning focus / calm",
        palette="bright, mellow lofi",
        playlists=("Focus", "Work", "Morning"),
        scene=SceneSpec(
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
    # Sunset Coast — warm sun low, cloud, sea haze, dark headlands (no particles).
    "summer": Theme(
        "summer",
        world="Sunset Coast",
        title="Sunset Coast — chill lofi to unwind",
        task="relax / unwind",
        palette="warm chillhop",
        playlists=("Chill", "Work", "Golden Hour"),
        scene=SceneSpec(
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
    # Autumn Leaves — amber dusk: low sun, stars, mist, cabin, falling leaves.
    "autumn": Theme(
        "autumn",
        world="Autumn Leaves",
        title="Autumn Work Session — cozy jazzy lofi",
        task="work / study",
        palette="jazzy lofi",
        playlists=("Work", "Focus", "Rainy Café"),
        scene=SceneSpec(
        sky_top="3a2150", sky_bottom="e0883c",
        ridges=(
            RidgeLayer(0.62, "7a4a2a", ((80, 260, 0.4), (24, 80, 0.6))),
            RidgeLayer(0.72, "4a2812", ((100, 190, 0.7), (40, 66, 1.1))),
            RidgeLayer(0.82, "200e06", ((54, 150, 0.2),), jag_amp=48, jag_period=24),
        ),
        glow=True, glow_x=0.66, glow_y=0.40, glow_radius=140, glow_color="ffcaa0",
        haze=True, haze_strength=140, stars=True, star_density=3,
        clouds=True, cloud_color="ffc59a", cloud_y=0.22, cloud_strength=110, cloud_speed=1.0,
        fog=True, fog_y=0.66, fog_strength=80, fog_color="f0d2b0", fog_speed=0.3,
        buildings=_homestead(cabin_x=0.62, barn_x=0.36, win="ffd27f"),
        shooting_star=True,
        particles="leaves", particle_color="ffae5a", particle_density=8,
    )),
    # Cabin Holidays — festive night: gold glow, aurora, mist, cabin, dense snow.
    "holiday": Theme(
        "holiday",
        world="Cabin Holidays",
        title="Cabin Holidays — festive lofi to cozy up",
        task="relax / festive",
        palette="warm festive lofi",
        playlists=("Sleep", "Chill", "Holiday"),
        scene=SceneSpec(
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
        fog=True, fog_y=0.66, fog_strength=75, fog_color="cfe0d8", fog_speed=0.4,
        snow_ground=True, snow_ground_y=0.78,
        pond=True, pond_x=0.54, pond_y=0.88, pond_w=660, pond_h=180, skaters=4,
        buildings=_homestead(cabin_x=0.24, barn_x=0.40, win="ffce73", base=0.78, scale=0.76),
        shooting_star=True,
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
