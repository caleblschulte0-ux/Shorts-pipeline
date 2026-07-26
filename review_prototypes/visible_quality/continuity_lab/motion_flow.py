from __future__ import annotations

from collections import Counter

from .models import LayoutSpec, MotionKeyframe, MotionPlan, StoryScene

EDGES = ("left", "right", "top", "bottom")


def _edge_point(edge: str, layout: LayoutSpec) -> tuple[float, float]:
    hero = layout.hero
    points = {
        "left": (hero.x - 160, hero.y + hero.height * .55),
        "right": (hero.right + 160, hero.y + hero.height * .55),
        "top": (hero.x + hero.width * .5, hero.y - 180),
        "bottom": (hero.x + hero.width * .5, hero.bottom + 180),
        "center": (hero.x + hero.width * .5, hero.y + hero.height * .5),
        "camera": (540, 960),
    }
    return points[edge]


def compile_motion(scene: StoryScene, layout: LayoutSpec, index: int, previous_exit: str | None) -> MotionPlan:
    entry = previous_exit if previous_exit in EDGES else EDGES[index % len(EDGES)]
    if scene.role == "payoff":
        exit_edge = "camera"
    else:
        opposite = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
        exit_edge = opposite.get(entry, EDGES[(index + 1) % len(EDGES)])
    sx, sy = _edge_point(entry, layout)
    cx, cy = _edge_point("center", layout)
    ex, ey = _edge_point(exit_edge, layout)
    duration = scene.duration
    frames = (
        MotionKeyframe(0.0, sx, sy, .86, -4 if entry == "left" else 4, "out_cubic"),
        MotionKeyframe(round(min(.18, duration * .06), 3), cx, cy, 1.0, 0.0, "out_back"),
        MotionKeyframe(round(duration * .72, 3), cx + (25 if index % 2 else -25), cy - 18, 1.04, 1.5, "in_out_sine"),
        MotionKeyframe(round(duration, 3), ex, ey, 1.12 if exit_edge == "camera" else .92, 0.0, "in_cubic"),
    )
    plan = MotionPlan(
        object_id=scene.callback_token or scene.focus,
        entry_edge=entry,
        exit_edge=exit_edge,
        keyframes=frames,
        first_motion_at=0.0,
        carries_focus=True,
    )
    plan.validate(scene.duration)
    return plan


def motion_flow_score(plans: tuple[MotionPlan, ...]) -> float:
    if not plans:
        return 0.0
    continuity_hits = sum(a.exit_edge == b.entry_edge for a, b in zip(plans, plans[1:]))
    continuity = continuity_hits / max(1, len(plans) - 1)
    early = sum(plan.first_motion_at <= .10 for plan in plans) / len(plans)
    focus = sum(plan.carries_focus for plan in plans) / len(plans)
    exits = [plan.exit_edge for plan in plans[:-1]]
    repeat = max(Counter(exits).values(), default=1) - 1
    score = continuity * 50 + early * 25 + focus * 25 - repeat * 4
    return round(max(0.0, min(100.0, score)), 1)
