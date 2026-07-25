"""Quality milestones — the staged bar the pipeline is held to (ChatGPT review).

Do NOT jump straight to "90 is passing": with the gate that strict the pipeline
would block everything indefinitely. Instead climb through phases, each with a
higher *median* bar AND stricter build-time hard-fails, so the floor rises
without freezing shipping. The active phase is chosen by ``QUALITY_PHASE`` (env),
defaulting to phase 1 (the current reality: no hard failures, median >= 70).

    Phase 1  median >= 70, no hard failures                       (get here first)
    Phase 2  median >= 80, every dimension above its midpoint
    Phase 3  median >= 90 across two consecutive full benchmark runs
    prod     individual video >= 90 and no hard failure           (final floor)

Each phase also sets the BUILD-TIME temporal hard-fail thresholds (checked in
code, before the expensive vision review — see ``scripts/temporal_gate.py``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    name: str
    median_bar: int                 # required median score across the benchmark
    dim_midpoint_required: bool      # every dimension above its midpoint?
    consecutive_runs: int            # runs that must all pass
    # build-time temporal hard-fail thresholds (before vision review):
    min_effective_fps: float
    max_duplicate_ratio: float
    max_dup_run_frames: int


PHASES = {
    "1": Phase("phase-1", 70, False, 1, min_effective_fps=11.0,
               max_duplicate_ratio=0.45, max_dup_run_frames=45),
    "2": Phase("phase-2", 80, True, 1, min_effective_fps=17.0,
               max_duplicate_ratio=0.30, max_dup_run_frames=12),
    "3": Phase("phase-3", 90, True, 2, min_effective_fps=22.0,
               max_duplicate_ratio=0.18, max_dup_run_frames=6),
    "prod": Phase("prod", 90, True, 2, min_effective_fps=24.0,
                  max_duplicate_ratio=0.15, max_dup_run_frames=4),
}

DEFAULT_PHASE = "1"


def active_phase() -> Phase:
    key = os.environ.get("QUALITY_PHASE", DEFAULT_PHASE).strip() or DEFAULT_PHASE
    return PHASES.get(key, PHASES[DEFAULT_PHASE])


def dimension_midpoints() -> dict:
    """Per-dimension midpoint (dims are graded 0-3 unless noted); 'above midpoint'
    means strictly greater. Phase 2+ requires every dimension above these."""
    return {"hook": 1.5, "data_demo": 1.5, "mascot": 1.5, "craft": 1.5,
            "pace": 1.5, "payoff": 1.5, "temporal_craft": 1.5}
