from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PointFixture:
    label: str
    value: float
    period: float | None = None


@dataclass
class InsightFixture:
    topic: str
    unit: str
    kind: str
    items: list[PointFixture]
    highlight_label: str = ""
    main_insight: str = ""
    perf_override: str | None = None
    plan_locked: bool = False
    host_baked: bool = False


@dataclass
class SegmentFixture:
    sentence: str
    topic: str
    role: str
    kind: str
    insight: InsightFixture
    punches: list[dict[str, Any]] = field(default_factory=list)
    source_footer: str = "Source: fixture"
    host_baked: bool = False
    anchors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StoryFixture:
    slug: str
    title: str
    hook: str
    closing: str
    segments: list[SegmentFixture]
    question: str = "Which number surprised you most?"
    sources: list[str] = field(default_factory=lambda: ["Source: fixture"])


def _segment(topic: str, unit: str, kind: str, role: str, sentence: str, values: list[tuple], highlight: str = "") -> SegmentFixture:
    points = [PointFixture(*value) for value in values]
    insight = InsightFixture(topic, unit, kind, points, highlight or points[0].label, sentence)
    punches = []
    for point in points[:2]:
        token = f"{point.value:g}"
        if token in sentence:
            punches.append({"phrase": token, "text": token, "duration": 1.8})
    anchors = [{"label": point.label, "value": point.value, "cx": 400 + i * 100, "cy": 500 + i * 40, "w": 80, "h": 50} for i, point in enumerate(points)]
    return SegmentFixture(sentence, topic, role, kind, insight, punches=punches, anchors=anchors)


def archetype_story(name: str) -> StoryFixture:
    if name == "money":
        values = [("2019", 680, 2019), ("2022", 860, 2022), ("2026", 1030, 2026)]
        segments = [
            _segment("Grocery prices", "dollars", "trend", "hook", "2019 was 680 dollars. 2026 is 1030 dollars.", values, "2026"),
            _segment("Grocery prices", "dollars", "trend", "setup", "The same basket started at 680 dollars.", values, "2019"),
            _segment("Grocery prices", "dollars", "trend", "explanation", "By 2022 it had reached 860 dollars.", values, "2022"),
            _segment("Grocery prices", "dollars", "trend", "consequence", "Families now need 350 extra dollars for the same basket.", values, "2026"),
            _segment("Grocery prices", "dollars", "trend", "payoff", "The path from 680 to 1030 dollars is the story.", values, "2026"),
        ]
        return StoryFixture("grocery-bill-jump", "The grocery bill jump", "The same basket costs far more now.", "The gap is what families feel.", segments)
    if name == "share":
        values = [("Housing", 42, None), ("Food", 28, None), ("Other", 30, None)]
        segments = [
            _segment("Household spending", "percent", "share", "hook", "Housing takes 42 percent of this budget.", values, "Housing"),
            _segment("Household spending", "percent", "share", "setup", "Food takes another 28 percent.", values, "Food"),
            _segment("Household spending", "percent", "share", "explanation", "Only 30 percent remains for everything else.", values, "Other"),
            _segment("Household spending", "percent", "share", "consequence", "The 42 percent housing slice squeezes every other choice.", values, "Housing"),
            _segment("Household spending", "percent", "share", "payoff", "The opening 42 percent slice explains the pressure.", values, "Housing"),
        ]
        return StoryFixture("budget-squeeze", "The household budget squeeze", "One category is swallowing the budget.", "That first slice explains the rest.", segments)
    if name == "ranking":
        values = [("A", 91, None), ("B", 73, None), ("C", 51, None), ("D", 35, None)]
        segments = [
            _segment("City growth", "percent", "rank", "hook", "City A leads at 91 percent.", values, "A"),
            _segment("City growth", "percent", "rank", "setup", "City B follows at 73 percent.", values, "B"),
            _segment("City growth", "percent", "rank", "explanation", "City C is back at 51 percent.", values, "C"),
            _segment("City growth", "percent", "rank", "consequence", "The gap between 91 and 35 percent is enormous.", values, "A"),
            _segment("City growth", "percent", "rank", "payoff", "The winner matters, but the spread is the story.", values, "A"),
        ]
        return StoryFixture("city-growth-race", "The city growth race", "One city left the rest behind.", "The spread explains the race.", segments)
    if name == "comparison":
        values = [("Option A", 78, None), ("Option B", 44, None)]
        segments = [
            _segment("Adoption", "percent", "comparison", "hook", "Option A is at 78 percent versus 44 percent.", values, "Option A"),
            _segment("Adoption", "percent", "comparison", "setup", "Option B still reaches 44 percent.", values, "Option B"),
            _segment("Adoption", "percent", "comparison", "explanation", "The difference is 34 points.", values, "Option A"),
            _segment("Adoption", "percent", "comparison", "consequence", "That 34 point gap changes the whole market.", values, "Option A"),
            _segment("Adoption", "percent", "comparison", "payoff", "Return to 78 versus 44 and the outcome is obvious.", values, "Option A"),
        ]
        return StoryFixture("adoption-gap", "The adoption gap", "These two options are not close.", "The opening gap predicts the ending.", segments)
    if name == "single":
        values = [("Average", 63, None)]
        segments = [
            _segment("Daily screen time", "percent", "bubbles", "hook", "The average is 63 percent.", values, "Average"),
            _segment("Daily screen time", "percent", "bubbles", "setup", "That means most of the day is already claimed.", values, "Average"),
            _segment("Daily screen time", "percent", "bubbles", "explanation", "The 63 percent fills more than half the gauge.", values, "Average"),
            _segment("Daily screen time", "percent", "bubbles", "consequence", "That 63 percent leaves less room for everything else.", values, "Average"),
            _segment("Daily screen time", "percent", "bubbles", "payoff", "The same 63 percent now feels much larger.", values, "Average"),
        ]
        return StoryFixture("screen-time-stat", "The screen time stat", "One number fills most of the day.", "The number did not change; its meaning did.", segments)
    raise ValueError(f"unknown fixture archetype: {name}")
