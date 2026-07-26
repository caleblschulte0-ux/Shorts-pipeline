from __future__ import annotations

import unittest

from .compiler import RetentionCompiler
from .ending_lab import EndingLab
from .hook_lab import HookLab
from .models import Beat
from .pacing import PacingAnalyzer


def healthy_beats():
    return (
        Beat("setup", 1.5, 3.6, "setup", "establish baseline", "chart appears", "brace", 0.25, 0.1, 0.4),
        Beat("growth", 3.6, 6.0, "escalation", "show acceleration", "line steepens", "pull", 0.55, 0.1, 0.5),
        Beat("reversal", 6.0, 8.3, "reversal", "expectation breaks", "bar overtakes", "race", 0.82, 0.1, 0.55),
        Beat("payoff", 8.3, 10.2, "payoff", "show consequence", "scene transforms", "recover", 0.35, 0.1, 0.4),
    )


class RetentionSystemTests(unittest.TestCase):
    def test_hook_lab_avoids_recent_pattern(self):
        lab = HookLab()
        plans = lab.generate(
            claim="The value doubled.",
            consequential_number="200%",
            expectation="slow growth",
            consequence="the limit breaks",
            mascot_goal="hold the line",
        )
        selected = lab.select(plans, recent_pattern_keys=("failed-attempt:reversal",))
        self.assertNotEqual(selected.hook.pattern_key, "failed-attempt:reversal")

    def test_pacing_rejects_repeated_action(self):
        beats = tuple(
            Beat(f"b{i}", i * 2.0, i * 2.0 + 1.8, "rank", f"fact {i}", "bar moves", "drag", 0.2 + i * 0.2)
            for i in range(4)
        )
        report = PacingAnalyzer().analyze(beats)
        self.assertFalse(report.passed)
        self.assertTrue(any("dominates" in item for item in report.hard_failures))

    def test_ending_lab_rejects_generic_cta(self):
        lab = EndingLab()
        endings = lab.generate(
            claim="The number changes the outcome.",
            consequence="the system fails",
            mascot_goal="balance the load",
            final_number="72%",
        )
        scored = {item.ending.ending_id: item for item in map(lab.score, endings)}
        self.assertTrue(scored["ending-question"].failures)

    def test_compiler_produces_valid_package(self):
        package = RetentionCompiler().compile(
            story_slug="demo",
            claim="The trend accelerates.",
            consequential_number="72%",
            expectation="steady growth",
            consequence="the old limit stops working",
            mascot_goal="hold the line",
            beats=healthy_beats(),
        )
        self.assertTrue(package.report.passed)
        package.validate()

    def test_static_hold_blocks_package(self):
        beats = list(healthy_beats())
        beats[2] = Beat("reversal", 6.0, 8.3, "reversal", "expectation breaks", "bar overtakes", "race", 0.82, 0.8, 0.55)
        package = RetentionCompiler().compile(
            story_slug="demo",
            claim="The trend accelerates.",
            consequential_number="72%",
            expectation="steady growth",
            consequence="the old limit stops working",
            mascot_goal="hold the line",
            beats=beats,
        )
        self.assertFalse(package.report.passed)


if __name__ == "__main__":
    unittest.main()
