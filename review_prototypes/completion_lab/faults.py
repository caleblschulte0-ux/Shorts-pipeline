from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from .models import Fault, StorySpec, Verdict


def apply_story_fault(story: StorySpec, fault: Fault) -> StorySpec:
    if fault is Fault.MISSING_SOURCE:
        return replace(story, source=replace(story.source, publisher=""))
    if fault is Fault.STALE_SOURCE:
        return replace(story, source=replace(story.source, accessed=story.source.accessed - timedelta(days=500)))
    return story


def apply_verdict_fault(verdict: Verdict, fault: Fault) -> Verdict | dict[str, object]:
    if fault is Fault.MALFORMED_VERDICT:
        return {"score": "excellent"}
    if fault is Fault.JUDGE_UNWATCHED:
        return replace(verdict, watched_video=False)
    if fault is Fault.LOW_SCORE:
        return replace(verdict, score=72.0, lowest_dimension=6.0)
    return verdict
