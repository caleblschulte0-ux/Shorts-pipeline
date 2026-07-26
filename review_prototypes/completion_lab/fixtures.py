from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from .models import SourceFact, StoryBeat, StorySpec


FIXED_TODAY = date(2026, 7, 25)


def golden_story() -> StorySpec:
    return StorySpec(
        slug="blue-whale-heart",
        title="A Blue Whale Heart Weighs 400 Pounds",
        hook="This heart weighs 400 pounds—and beats only 8 times a minute.",
        closing="The biggest heart on Earth survives by slowing everything down.",
        source=SourceFact(
            publisher="National Oceanic and Atmospheric Administration",
            url="https://www.noaa.gov/example-blue-whale",
            accessed=date(2026, 7, 1),
            claim="Adult blue whale hearts can weigh roughly 400 pounds",
            value=400.0,
            unit="pounds",
        ),
        beats=(
            StoryBeat("hook", "This heart weighs 400 pounds.", 1.2, "scale_compare", "brace", 0.55),
            StoryBeat("scale", "It is about the size of a compact car.", 3.0, "object_compare", "push", 0.78),
            StoryBeat("rate", "Yet it can slow to 8 beats per minute.", 3.2, "pulse_timeline", "listen", 0.92),
            StoryBeat("payoff", "The biggest heart survives by slowing down.", 2.5, "synthesis", "settle", 0.30),
        ),
    )


def alternate_story() -> StorySpec:
    story = golden_story()
    return StorySpec(
        slug="giant-sequoia-water",
        title="A Giant Sequoia Can Move 500 Gallons a Day",
        hook="One tree can move 500 gallons of water in a single day.",
        closing="The tallest trees are also enormous living pumps.",
        source=SourceFact(
            publisher="National Park Service",
            url="https://www.nps.gov/example-sequoia",
            accessed=date(2026, 6, 20),
            claim="A giant sequoia can move hundreds of gallons of water daily",
            value=500.0,
            unit="gallons per day",
        ),
        beats=(
            StoryBeat("hook", "One tree moves 500 gallons a day.", 1.1, "container_compare", "lift", 0.60),
            StoryBeat("roots", "Its roots spread wider than the tree is tall.", 3.1, "root_map", "trace", 0.80),
            StoryBeat("flow", "Water climbs the height of a skyscraper.", 3.4, "vertical_flow", "climb", 0.94),
            StoryBeat("payoff", "It is a living pump disguised as a tree.", 2.4, "synthesis", "rest", 0.28),
        ),
        renderer_version=story.renderer_version,
        judge_version=story.judge_version,
        suite_version=story.suite_version,
    )


def load_fixture(path: Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
