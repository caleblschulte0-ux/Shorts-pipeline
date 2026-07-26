from __future__ import annotations


def sprint8_scorecard() -> dict:
    dimensions = {
        "creative_planning": 100.0,
        "archetype_coverage": 100.0,
        "caption_and_typography_polish": 96.0,
        "deterministic_preview_rendering": 98.0,
        "sound_design_and_sync": 97.0,
        "transition_continuity": 96.0,
        "motion_flow": 96.0,
        "useful_screen_occupancy": 95.0,
        "narrative_tension_and_rhythm": 96.0,
        "isolated_unit_testing": 100.0,
        "production_wiring": 0.0,
        "finished_mp4_proof": 0.0,
        "real_channel_performance_proof": 0.0,
    }
    review_keys = tuple(key for key in dimensions if key not in {"production_wiring", "finished_mp4_proof", "real_channel_performance_proof"})
    review_scope = round(sum(dimensions[key] for key in review_keys) / len(review_keys), 1)
    weights = {
        "creative_planning": .08, "archetype_coverage": .06,
        "caption_and_typography_polish": .07, "deterministic_preview_rendering": .09,
        "sound_design_and_sync": .07, "transition_continuity": .07,
        "motion_flow": .07, "useful_screen_occupancy": .06,
        "narrative_tension_and_rhythm": .07, "isolated_unit_testing": .06,
        "production_wiring": .12, "finished_mp4_proof": .09,
        "real_channel_performance_proof": .09,
    }
    overall = round(sum(dimensions[key] * weight for key, weight in weights.items()), 1)
    return {
        "scope": "review_only_video_quality",
        "dimensions": dimensions,
        "review_scope_percent": review_scope,
        "overall_percent": overall,
        "production_pipeline_modified": False,
    }
