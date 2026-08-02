from __future__ import annotations

from typing import Sequence

from .ending_lab import EndingLab
from .hook_lab import HookLab
from .models import Beat, RetentionPackage, RetentionReport
from .pacing import PacingAnalyzer


class RetentionCompiler:
    def __init__(
        self,
        *,
        hook_lab: HookLab | None = None,
        ending_lab: EndingLab | None = None,
        pacing: PacingAnalyzer | None = None,
    ) -> None:
        self.hook_lab = hook_lab or HookLab()
        self.ending_lab = ending_lab or EndingLab()
        self.pacing = pacing or PacingAnalyzer()

    def compile(
        self,
        *,
        story_slug: str,
        claim: str,
        consequential_number: str,
        expectation: str,
        consequence: str,
        mascot_goal: str,
        beats: Sequence[Beat],
        recent_hook_patterns: Sequence[str] = (),
    ) -> RetentionPackage:
        hook = self.hook_lab.select(
            self.hook_lab.generate(
                claim=claim,
                consequential_number=consequential_number,
                expectation=expectation,
                consequence=consequence,
                mascot_goal=mascot_goal,
            ),
            recent_pattern_keys=recent_hook_patterns,
        ).hook
        ending = self.ending_lab.select(
            self.ending_lab.generate(
                claim=claim,
                consequence=consequence,
                mascot_goal=mascot_goal,
                final_number=consequential_number,
            )
        ).ending
        pacing_report = self.pacing.analyze(tuple(beats))
        dimensions = dict(pacing_report.dimensions)
        dimensions["hook"] = 100.0
        dimensions["ending"] = 100.0
        combined_score = min(100.0, pacing_report.score * 0.75 + 25.0)
        report = RetentionReport(
            passed=pacing_report.passed and combined_score >= 75.0,
            score=round(combined_score, 2),
            hard_failures=pacing_report.hard_failures,
            warnings=pacing_report.warnings,
            dimensions=dimensions,
        )
        package = RetentionPackage(
            story_slug=story_slug,
            hook=hook,
            beats=tuple(beats),
            ending=ending,
            report=report,
        )
        if report.passed:
            package.validate()
        return package
