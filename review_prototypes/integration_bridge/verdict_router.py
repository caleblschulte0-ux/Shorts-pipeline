from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .contracts import QualityBridgeBundle, SceneOverride

AUTOFAIL_PRIORITY = (
    "junk_imagery", "decorative_mascot", "bare_number_card", "dead_air", "empty_void"
)
DIMENSION_TO_REASON = {
    "hook": "opening action is not immediate or specific enough",
    "data_demo": "the data is not physically demonstrated clearly enough",
    "mascot": "the mascot lacks contact, cause, or consequence",
    "craft": "composition or visual execution is weak",
    "pace": "the beat timing is too flat or slow",
    "payoff": "the ending does not resolve the opening visual",
    "temporal_craft": "effective motion cadence is too low",
}


@dataclass(frozen=True)
class RepairDirective:
    preserve_verdict: str
    target_segment: int
    target_reason: str
    incumbent: Mapping[str, Any]
    candidates: tuple[Mapping[str, Any], ...]
    acceptance_rule: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _segment_from_evidence(verdict: Mapping[str, Any], count: int) -> int:
    blobs: list[str] = []
    for item in verdict.get("auto_fails", ()) or ():
        blobs.append(str(item))
    checks = verdict.get("checks", {}) or {}
    for value in checks.values():
        if isinstance(value, Mapping):
            blobs.append(str(value.get("evidence", "")))
    hits = [int(value) for value in re.findall(r"seg(?:ment)?\s*(\d+)", " ".join(blobs), re.I)]
    return (max(set(hits), key=hits.count) % count) if hits else count - 1


def _weakest_dimension(verdict: Mapping[str, Any]) -> str:
    weights = {
        "hook": (18, 4), "data_demo": (22, 5), "mascot": (18, 4),
        "craft": (12, 3), "pace": (8, 2), "payoff": (8, 2),
        "temporal_craft": (14, 3),
    }
    dimensions = verdict.get("dimensions", {}) or {}
    return min(
        weights,
        key=lambda key: (
            max(0, min(weights[key][1], int(dimensions.get(key, 0)))) / weights[key][1],
            -weights[key][0],
        ),
    )


def _alternatives(incumbent: SceneOverride) -> tuple[dict[str, Any], ...]:
    by_kind = {
        "trend": (("trend", "pull_down_win"), ("timeline", "drag_line"), ("pictorial_race", "shoved_bar")),
        "timeline": (("trend", "drag_line"), ("timeline", "pull_down_win"), ("pictorial_race", "shoved_bar")),
        "comparison": (("comparison", "shoved_bar"), ("pictorial_race", "shoved_bar"), ("stack", "hoist_stack")),
        "waffle_grid": (("waffle_grid", "hoist_stack"), ("share", "hoist_stack"), ("stack", "drag_line")),
        "share": (("waffle_grid", "hoist_stack"), ("share", "drag_line"), ("stack", "hoist_stack")),
        "fill_vessel": (("fill_vessel", "hoist_stack"), ("bubbles", "shoved_bar"), ("stack", "drag_line")),
        "pictorial_race": (("pictorial_race", "shoved_bar"), ("rank", "shoved_bar"), ("stack", "drag_line")),
        "rank": (("pictorial_race", "shoved_bar"), ("rank", "drag_line"), ("bubbles", "hoist_stack")),
    }
    pairs = by_kind.get(incumbent.kind, ((incumbent.kind, incumbent.performance), ("bubbles", "shoved_bar"), ("stack", "hoist_stack")))
    result = []
    for kind, performance in pairs:
        result.append({
            "viz": kind,
            "perf": performance,
            "structurally_different": (kind, performance) != (incumbent.kind, incumbent.performance),
        })
    return tuple(result)


def route_verdict(verdict: Mapping[str, Any], bundle: QualityBridgeBundle) -> RepairDirective | None:
    """Create a repair directive without ever changing the showrunner's verdict."""
    bundle.validate()
    if str(verdict.get("verdict", "")).lower() == "ship":
        return None
    target_index = _segment_from_evidence(verdict, len(bundle.overrides))
    incumbent = bundle.overrides[target_index]
    failed = [str(item).split(":", 1)[0].strip() for item in verdict.get("auto_fails", ()) or ()]
    reason_key = next((name for name in AUTOFAIL_PRIORITY if name in failed), None)
    if reason_key:
        reason = f"showrunner auto-fail: {reason_key}"
    else:
        dimension = _weakest_dimension(verdict)
        reason = f"weakest dimension {dimension}: {DIMENSION_TO_REASON[dimension]}"
    return RepairDirective(
        preserve_verdict=str(verdict.get("verdict", "block")),
        target_segment=target_index,
        target_reason=reason,
        incumbent={"viz": incumbent.kind, "perf": incumbent.performance},
        candidates=_alternatives(incumbent),
        acceptance_rule="render all candidates blind; keep only a candidate that beats the incumbent by >0.08 and never flip a showrunner BLOCK",
    )
