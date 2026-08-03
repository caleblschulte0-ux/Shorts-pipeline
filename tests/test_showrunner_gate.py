"""The taste gate's policy, locked down — for EVERY channel that publishes.

The showrunner is the permanent, autonomous quality authority. Its decision
logic used to live inline in `scripts/post_stories.py`, which meant it
protected the 1-video-a-day channel and not the 6-video-a-day one. It is now
`shared/showrunner_gate.py` and both channels call it.

These tests exist so nobody can quietly weaken it. Read `decide()` as a
truth table: a publish run holds on ANY doubt, a preview run never blocks on
infrastructure, and there is no input at all that turns a brain BLOCK into a
ship.

    python -m unittest tests.test_showrunner_gate -v
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from shared import showrunner_gate as gate            # noqa: E402

SHIP = {"verdict": "ship", "score": 88, "one_line": "good"}
BLOCK = {"verdict": "block", "score": 41, "one_line": "muddy middle"}
NO_SCORE = {"verdict": "ship", "score": None, "one_line": ""}


class TestABlockIsSovereign(unittest.TestCase):
    """Code may only ever ADD blocks. Never the reverse."""

    def test_a_block_holds_on_a_publish_run(self):
        d = gate.decide(will_upload=True, gate_on=True, verdict=BLOCK)
        self.assertTrue(d["blocked"])

    def test_a_block_holds_on_a_preview_run_too(self):
        d = gate.decide(will_upload=False, gate_on=True, verdict=BLOCK)
        self.assertTrue(d["blocked"], "a preview may fail open on INFRA, but "
                                      "never on the brain's own verdict")

    def test_a_high_score_cannot_override_a_block(self):
        d = gate.decide(will_upload=True, gate_on=True,
                        verdict={"verdict": "block", "score": 99})
        self.assertTrue(d["blocked"])

    def test_no_combination_of_inputs_ships_a_block(self):
        for upload in (True, False):
            for score in (None, 0, 50, 100):
                d = gate.decide(will_upload=upload, gate_on=True,
                                verdict={"verdict": "block", "score": score})
                self.assertTrue(d["blocked"],
                                f"BLOCK shipped at upload={upload} "
                                f"score={score}")


class TestAPublishRunFailsClosed(unittest.TestCase):
    """No verdict is not evidence of quality."""

    def test_an_infra_error_holds_the_video(self):
        d = gate.decide(will_upload=True, gate_on=True, verdict=None,
                        error=RuntimeError("no API key"))
        self.assertTrue(d["blocked"])
        self.assertIn("fail-closed", d["reason"])

    def test_a_verdict_with_no_score_holds_the_video(self):
        d = gate.decide(will_upload=True, gate_on=True, verdict=NO_SCORE)
        self.assertTrue(d["blocked"])

    def test_an_empty_verdict_holds_the_video(self):
        self.assertTrue(gate.decide(will_upload=True, gate_on=True,
                                    verdict={})["blocked"])

    def test_SHOWRUNNER_off_is_REFUSED_on_a_publish_run(self):
        d = gate.decide(will_upload=True, gate_on=False, verdict=None)
        self.assertTrue(d["blocked"])
        self.assertIn("not allowed on a publish run", d["reason"])

    def test_a_clean_ship_actually_ships(self):
        d = gate.decide(will_upload=True, gate_on=True, verdict=SHIP)
        self.assertFalse(d["blocked"], "the gate must not block everything — "
                                       "a gate nothing passes gets removed")


class TestAPreviewRunFailsOpen(unittest.TestCase):
    """Iteration must not be blocked by infrastructure."""

    def test_an_infra_error_does_not_block_a_preview(self):
        d = gate.decide(will_upload=False, gate_on=True, verdict=None,
                        error=RuntimeError("ffmpeg missing"))
        self.assertFalse(d["blocked"])

    def test_no_score_does_not_block_a_preview(self):
        self.assertFalse(gate.decide(will_upload=False, gate_on=True,
                                     verdict=NO_SCORE)["blocked"])

    def test_SHOWRUNNER_off_is_fine_on_a_preview(self):
        d = gate.decide(will_upload=False, gate_on=False, verdict=None)
        self.assertFalse(d["blocked"])
        self.assertFalse(d["ran"])


class TestTheSwitch(unittest.TestCase):
    def test_off_values(self):
        for v in ("off", "OFF", "0", "false", "no"):
            self.assertFalse(gate.enabled({"SHOWRUNNER": v}), v)

    def test_anything_else_is_on(self):
        for v in ("on", "", "1", "yes", "please"):
            self.assertTrue(gate.enabled({"SHOWRUNNER": v}), repr(v))

    def test_absent_means_on(self):
        self.assertTrue(gate.enabled({}))


class TestRunNeverRaises(unittest.TestCase):
    """A gate that crashes the run is a gate that caused the outage it
    exists to prevent."""

    def setUp(self):
        self.real = sys.modules.get("scripts.showrunner_review")

    def tearDown(self):
        if self.real is not None:
            sys.modules["scripts.showrunner_review"] = self.real
        else:
            sys.modules.pop("scripts.showrunner_review", None)

    def _fake(self, fn):
        import types
        m = types.ModuleType("scripts.showrunner_review")
        m.review_video = fn
        m.append_ledger = lambda *a, **k: None
        m.should_block = lambda v: v.get("verdict") == "block"
        sys.modules["scripts.showrunner_review"] = m

    def test_a_reviewer_that_explodes_holds_a_publish_run(self):
        def boom(*a, **k):
            raise ValueError("model returned garbage")
        self._fake(boom)
        r = gate.run("/nonexistent.mp4", slug="s", will_upload=True,
                     sidecar=False)
        self.assertTrue(r["blocked"])

    def test_a_reviewer_that_calls_sys_exit_holds_a_publish_run(self):
        def bail(*a, **k):
            raise SystemExit(3)
        self._fake(bail)
        r = gate.run("/nonexistent.mp4", slug="s", will_upload=True,
                     sidecar=False)
        self.assertTrue(r["blocked"], "SystemExit must not read as approval")

    def test_ctrl_c_still_propagates(self):
        def stop(*a, **k):
            raise KeyboardInterrupt
        self._fake(stop)
        with self.assertRaises(KeyboardInterrupt):
            gate.run("/x.mp4", slug="s", will_upload=True, sidecar=False)

    def test_a_ship_verdict_passes_through(self):
        self._fake(lambda *a, **k: dict(SHIP))
        r = gate.run("/x.mp4", slug="s", will_upload=True, sidecar=False)
        self.assertFalse(r["blocked"])
        self.assertEqual(r["verdict"]["score"], 88)

    def test_off_still_refuses_a_publish_run_without_calling_the_brain(self):
        def boom(*a, **k):
            raise AssertionError("must not be called when the gate is off")
        self._fake(boom)
        r = gate.run("/x.mp4", slug="s", will_upload=True,
                     env={"SHOWRUNNER": "off"}, sidecar=False)
        self.assertTrue(r["blocked"])


class TestBothChannelsAreActuallyGated(unittest.TestCase):
    """The whole point. A gate wired into one channel is half a gate."""

    CHANNELS = {
        "scripts/post_stories.py": "explainer",
        "scripts/run_trending_daily.py": "trending",
    }

    def test_every_publishing_channel_calls_the_shared_gate(self):
        for rel, name in self.CHANNELS.items():
            src = (ROOT / rel).read_text()
            self.assertIn("showrunner_gate", src,
                          f"{name} ({rel}) does not run the taste gate")

    def test_trending_blocks_the_upload_on_a_gate_block(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        self.assertIn("showrunner_block", src,
                      "trending calls the gate but ignores its verdict")

    def test_nobody_reimplements_the_policy_inline(self):
        """A second copy is how the two channels drift apart again."""
        for rel in self.CHANNELS:
            src = (ROOT / rel).read_text()
            self.assertNotIn("_sr.should_block", src,
                             f"{rel} still has its own copy of the policy")

    def test_trendings_workflow_can_actually_reach_a_judge(self):
        """The gate fails CLOSED. A render step with no judge credential
        holds all six videos — a zero-post day caused by the gate itself."""
        wf = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets."
                      "CLAUDE_CODE_OAUTH_TOKEN }}", wf)
        # and the preflight must say so BEFORE spending 40 minutes rendering
        pre = wf.split("Verify required secrets are set", 1)[1].split(
            "- name:", 1)[0]
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", pre)
        self.assertIn("GEMINI_API_KEY", pre)

    def test_the_gate_has_no_bypass(self):
        """No branch may set blocked back to False after something set it."""
        src = (ROOT / "shared" / "showrunner_gate.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "decide")
        # Every `blocked` value in decide() is a literal at construction time
        # or bool(reasons); none is an assignment that could clear a hold.
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    self.assertNotEqual(getattr(t, "id", None), "blocked",
                                        "decide() reassigns `blocked` — that "
                                        "is exactly the bypass shape")


class TestZFormatAwareShowrunnerContract(unittest.TestCase):
    def test_reddit_is_not_required_to_invent_a_statistic(self):
        from scripts.showrunner_review import _format_directive
        text = _format_directive({"format": "reddit_story"})
        self.assertIn("narrative, not a statistics explainer", text)
        self.assertIn("do not demand numbers", text)

    def test_graph_forbids_explainer_mascot(self):
        from scripts.showrunner_review import _format_directive
        text = _format_directive({"format": "graph_race"})
        self.assertIn("separate Explainer channel mascot", text)
        self.assertIn("mark decorative_mascot present", text)

    def test_reddit_forbids_explainer_mascot(self):
        from scripts.showrunner_review import _format_directive
        text = _format_directive({"format": "reddit_story"})
        self.assertIn("separate Explainer channel mascot", text)
        self.assertIn("mark decorative_mascot present", text)


if __name__ == "__main__":
    unittest.main()
