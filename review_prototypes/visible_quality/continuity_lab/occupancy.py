from __future__ import annotations

from .models import Box, LayoutSpec, W, H

RIGHT_RAIL = Box(930, 500, 150, 1050)
BOTTOM_UI = Box(0, 1660, 1080, 260)

_LAYOUTS = {
    "money": (
        (Box(70, 330, 840, 1030), Box(110, 90, 780, 180), Box(140, 1400, 720, 160), "center"),
        (Box(60, 300, 850, 1080), Box(90, 90, 800, 170), Box(170, 1410, 660, 150), "lower_center"),
    ),
    "share": (
        (Box(80, 300, 820, 1080), Box(90, 90, 800, 180), Box(150, 1410, 690, 150), "center"),
        (Box(100, 330, 790, 1030), Box(100, 90, 780, 170), Box(190, 1400, 610, 160), "center"),
    ),
    "ranking": (
        (Box(55, 315, 855, 1070), Box(95, 85, 790, 180), Box(145, 1415, 700, 145), "full_rows"),
        (Box(70, 350, 830, 1020), Box(100, 95, 780, 170), Box(170, 1410, 650, 150), "full_rows"),
    ),
    "comparison": (
        (Box(65, 320, 845, 1060), Box(100, 90, 780, 175), Box(165, 1410, 650, 150), "split"),
        (Box(80, 350, 820, 1010), Box(110, 100, 760, 165), Box(175, 1390, 630, 165), "split"),
    ),
    "single": (
        (Box(90, 330, 800, 1040), Box(100, 90, 780, 180), Box(190, 1400, 600, 160), "center"),
        (Box(70, 300, 840, 1080), Box(110, 90, 760, 170), Box(185, 1410, 610, 145), "center"),
    ),
}


def _useful_occupancy(hero: Box, caption: Box, secondary: Box | None) -> float:
    weighted = hero.area + caption.area * 0.72 + (secondary.area * 0.65 if secondary else 0)
    return min(1.0, weighted / (W * H))


def _safe(box: Box) -> bool:
    return not box.overlaps(RIGHT_RAIL, padding=8) and not box.overlaps(BOTTOM_UI, padding=8)


def solve_layout(archetype: str, role: str, event: str) -> LayoutSpec:
    candidates = _LAYOUTS.get(archetype, _LAYOUTS["single"])
    best: LayoutSpec | None = None
    best_score = -1.0
    for hero, caption, secondary, anchor in candidates:
        if role in {"hook", "payoff"}:
            hero = Box(hero.x, max(285, hero.y - 25), hero.width, min(1110, hero.height + 55))
        occupancy = _useful_occupancy(hero, caption, secondary)
        if not (_safe(caption) and (_safe(secondary) if secondary else True)):
            continue
        if hero.overlaps(caption, padding=18) or (secondary and caption.overlaps(secondary, padding=12)):
            continue
        event_bonus = 0.02 if any(token in event.lower() for token in ("collision", "squeeze", "race", "overflow")) else 0
        score = occupancy + event_bonus
        if score > best_score:
            best = LayoutSpec(hero, caption, secondary, anchor, occupancy)
            best_score = score
    if best is None:
        raise ValueError("no safe layout candidate")
    best.validate()
    return best


def occupancy_score(layout: LayoutSpec) -> float:
    return round(min(100.0, layout.occupancy / 0.43 * 100), 1)
