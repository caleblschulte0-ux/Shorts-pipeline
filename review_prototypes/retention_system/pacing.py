from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Sequence

from .models import Beat, RetentionReport


class PacingAnalyzer:
    """Evaluate temporal craft without relying on a vision model."""

    def analyze(self, beats: Sequence[Beat]) -> RetentionReport:
        hard: list[str] = []
        warnings: list[str] = []
        if len(beats) < 3:
            hard.append("fewer than three information beats")

        for beat in beats:
            beat.validate()
            if beat.duration > 4.5:
                hard.append(f"{beat.beat_id} lasts {beat.duration:.2f}s")
            elif beat.duration > 3.5:
                warnings.append(f"{beat.beat_id} is long at {beat.duration:.2f}s")
            if beat.static_hold_seconds > 0.4:
                hard.append(
                    f"{beat.beat_id} static hold {beat.static_hold_seconds:.2f}s exceeds 0.4s"
                )
            if beat.caption_density > 0.85:
                warnings.append(f"{beat.beat_id} captions may overload the frame")

        roles = Counter(beat.role for beat in beats)
        for role, count in roles.items():
            if count > max(2, len(beats) // 2):
                warnings.append(f"role {role!r} repeats {count} times")

        actions = Counter(beat.mascot_action for beat in beats if beat.mascot_action)
        for action, count in actions.items():
            if count > max(1, len(beats) // 2):
                hard.append(f"mascot action {action!r} dominates {count}/{len(beats)} beats")

        tensions = [beat.tension for beat in beats]
        if tensions:
            peak_index = max(range(len(tensions)), key=tensions.__getitem__)
            if peak_index == 0:
                hard.append("tension peaks immediately and has nowhere to build")
            if peak_index < len(tensions) - 2:
                warnings.append("tension peaks too early")
            if tensions[-1] > tensions[peak_index] - 0.05:
                warnings.append("ending does not visibly release tension")

        state_changes = sum(bool(beat.visual_change.strip()) for beat in beats)
        if state_changes < 3:
            hard.append("fewer than three visible state changes")

        duration_score = 100.0 - sum(max(0.0, beat.duration - 2.8) * 8 for beat in beats)
        static_score = 100.0 - sum(beat.static_hold_seconds * 120 for beat in beats)
        diversity_score = 100.0
        if actions:
            diversity_score -= max(actions.values()) / len(beats) * 60
        tension_score = 100.0
        if tensions:
            tension_score = 70.0 + max(tensions) * 20 + max(0.0, max(tensions) - tensions[-1]) * 20

        dimensions = {
            "beat_cadence": max(0.0, min(100.0, duration_score)),
            "motion_continuity": max(0.0, min(100.0, static_score)),
            "performance_diversity": max(0.0, min(100.0, diversity_score)),
            "tension_progression": max(0.0, min(100.0, tension_score)),
        }
        score = mean(dimensions.values()) - 20.0 * len(hard) - 3.0 * len(warnings)
        score = max(0.0, min(100.0, score))
        return RetentionReport(
            passed=not hard and score >= 70.0,
            score=round(score, 2),
            hard_failures=tuple(hard),
            warnings=tuple(warnings),
            dimensions={key: round(value, 2) for key, value in dimensions.items()},
        )
