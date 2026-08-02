from __future__ import annotations

from .models import StoryArchetype

ARCHETYPES = {
    "money_over_time": StoryArchetype(
        "money_over_time", "$", "time_series", ("receipt_roll", "before_after_collision", "cart_overflow"),
        ("trend_yank", "burden_stack", "number_match"), "callback_bridge",
    ),
    "share_of_whole": StoryArchetype(
        "share_of_whole", "%", "parts_sum_to_100", ("share_squeeze", "waffle_takeover"),
        ("cell_pressure", "remainder_escape"), "opening_grid_resolves",
    ),
    "ranking": StoryArchetype(
        "ranking", "", "ordered_categories", ("rank_race", "scale_collision"),
        ("finish_gap", "podium_reframe"), "winner_gap_callback",
    ),
    "comparison": StoryArchetype(
        "comparison", "%", "two_values", ("scale_collision", "column_shove"),
        ("gap_expansion", "brace_between_values"), "side_by_side_resolution",
    ),
    "single_stat": StoryArchetype(
        "single_stat", "%", "one_value", ("gauge_launch", "object_fill"),
        ("needle_ride", "remaining_space"), "gauge_freeze_takeaway",
    ),
}


def detect_archetype(story: dict) -> StoryArchetype:
    data = tuple(story.get("data", ()))
    unit = str(story.get("unit", ""))
    if len(data) == 1:
        return ARCHETYPES["single_stat"]
    if data and all(point.get("period") is not None for point in data):
        return ARCHETYPES["money_over_time"]
    total = sum(float(point.get("value", 0)) for point in data)
    if unit in {"%", "percent"} and 95 <= total <= 105:
        return ARCHETYPES["share_of_whole"]
    if len(data) == 2:
        return ARCHETYPES["comparison"]
    return ARCHETYPES["ranking"]


def select_mechanics(archetype: StoryArchetype, recent: tuple[str, ...] = ()) -> tuple[str, ...]:
    hooks = sorted(archetype.hook_mechanics, key=lambda name: (recent.count(name), archetype.hook_mechanics.index(name)))
    body = sorted(archetype.body_mechanics, key=lambda name: (recent.count(name), archetype.body_mechanics.index(name)))
    return (hooks[0], *body, archetype.payoff_mechanic)
