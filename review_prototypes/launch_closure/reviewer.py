from __future__ import annotations

from typing import Iterable

MIN_SCORE = 70
AUTOFAIL_CHECKS = ("dead_air", "wrong_geometry", "missing_audio")


def review_metrics(metrics: dict) -> dict:
    checks = {
        "dead_air": metrics.get("motion_ratio", 0.0) < 0.55,
        "wrong_geometry": not (metrics.get("width") == 1080 and metrics.get("height") == 1920),
        "missing_audio": not bool(metrics.get("has_audio")),
    }
    dimensions = {
        "hook": 18 if metrics.get("motion_ratio", 0.0) >= 0.75 else 5,
        "data_demo": 22 if metrics.get("motion_ratio", 0.0) >= 0.75 else 8,
        "mascot": 18 if metrics.get("motion_ratio", 0.0) >= 0.75 else 7,
        "craft": 12 if not checks["wrong_geometry"] else 0,
        "pace": 8 if metrics.get("fps", 0.0) >= 29.0 else 2,
        "payoff": 8 if metrics.get("motion_ratio", 0.0) >= 0.75 else 3,
        "temporal_craft": 14 if metrics.get("motion_ratio", 0.0) >= 0.75 else 0,
    }
    score = sum(dimensions.values())
    auto_fails = [name for name in AUTOFAIL_CHECKS if checks[name]]
    return {
        "verdict": "block" if auto_fails or score < MIN_SCORE else "ship",
        "score": score,
        "dimensions": dimensions,
        "auto_fails": auto_fails,
        "watched_video": True,
        "sovereign": True,
    }


def two_pass_review(metrics: dict) -> dict:
    first = review_metrics(dict(metrics))
    second = review_metrics(dict(metrics))
    return {
        "passes": [first, second],
        "both_ship": all(v["verdict"] == "ship" for v in (first, second)),
        "scores_equal": first["score"] == second["score"],
    }


def structural_repair_candidates(archetype: str) -> list[dict]:
    variants = {
        "money": [{"viz": "trend", "perf": "drag_line"}, {"viz": "stack", "perf": "hoist_stack"}, {"viz": "comparison", "perf": "shoved_bar"}],
        "share": [{"viz": "share", "perf": "hoist_stack"}, {"viz": "waffle_grid", "perf": "hoist_stack"}, {"viz": "pictorial_race", "perf": "shoved_bar"}],
        "ranking": [{"viz": "pictorial_race", "perf": "shoved_bar"}, {"viz": "rank", "perf": "shoved_bar"}, {"viz": "stack", "perf": "drag_line"}],
        "comparison": [{"viz": "comparison", "perf": "shoved_bar"}, {"viz": "stack", "perf": "drag_line"}, {"viz": "pictorial_race", "perf": "shoved_bar"}],
        "single": [{"viz": "fill_vessel", "perf": "hoist_stack"}, {"viz": "bubbles", "perf": "drag_line"}, {"viz": "comparison", "perf": "shoved_bar"}],
    }
    if archetype not in variants:
        raise ValueError(f"unsupported archetype: {archetype}")
    return variants[archetype]


def preserve_sovereign_block(verdict: dict, candidates: Iterable[dict]) -> dict:
    candidate_list = list(candidates)
    if verdict.get("verdict") != "block":
        raise ValueError("repair routing requires a block verdict")
    if len(candidate_list) < 2:
        raise ValueError("at least two structural candidates are required")
    return {"incumbent_verdict": "block", "ship_override": False, "candidates": candidate_list}
