"""Long-form publishes a real watch-page video, and only through the gate.

Operator ruling 2026-08-25, reversing 2026-08-05: *"I want long form videos
to start posting"* — purpose-built 16:9, fail-closed gate.

Two things had to be true before a weekly cron could publish again, and
these tests are what keep them true:

  1. THE VIDEO IS A WATCH-PAGE VIDEO. The old builder concatenated six
     already-rendered VERTICAL 1080x1920 Shorts with `ffmpeg -c copy` and
     uploaded that; all nine it published (2026-06-07 .. 2026-08-02) landed
     as `/shorts/` URLs. `data_learning/longform_render.py` — a 1920x1080
     watch-page renderer with title card, chapters and a custom thumbnail —
     had existed the whole time, imported by nothing on this path.

  2. NOTHING REACHES THE CHANNEL UNJUDGED. Long-form had no showrunner, no
     QA, no judge at all. Publishing ungated is the exact move
     docs/SYSTEM_AUDIT.md §B measured the cost of (trending 6/day ungated,
     best video 45 views; explainer 1/day gated, best video 1,063).

    python -m unittest tests.test_longform_gated -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import build_longform as BL          # noqa: E402
from scripts import showrunner_review as SR   # noqa: E402

CFG = {"stories": [{"slug": "a", "title": "A", "hook": "hook a"},
                   {"slug": "b", "title": "B", "hook": "hook b"},
                   {"slug": "c", "title": "C", "hook": "hook c"}]}


class TestItPicksAStoryWorthCompiling(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-"))
        self._saved = (BL.EXPLAINER_LOG, BL.LONGFORM_LOG)
        BL.EXPLAINER_LOG = self.tmp / "explainer_posted_log.json"
        BL.LONGFORM_LOG = self.tmp / "longform_log.json"
        BL.EXPLAINER_LOG.write_text(json.dumps({"posted": {
            "a": {"url": "u", "at": "2026-08-01T00:00:00+00:00"},
            "b": {"url": "u", "at": "2026-08-20T00:00:00+00:00"},
            "c": {"url": "u", "at": "2026-08-10T00:00:00+00:00"},
        }}))

    def tearDown(self):
        BL.EXPLAINER_LOG, BL.LONGFORM_LOG = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_takes_the_newest_published_story(self):
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": []}))
        self.assertEqual(BL.pick_slug(CFG), "b")

    def test_it_never_builds_the_same_story_twice(self):
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": [
            {"slug": "b", "slugs": ["b"], "url": "x"}]}))
        self.assertEqual(BL.pick_slug(CFG), "c")

    def test_the_old_six_slug_entries_still_count_as_used(self):
        """The nine already-published compilations list six slugs each —
        those stories must not come back as 'never long-formed'."""
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": [
            {"slugs": ["a", "b", "c"], "url": "x"}]}))
        self.assertIsNone(BL.pick_slug(CFG))

    def test_an_explicit_slug_wins(self):
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": []}))
        self.assertEqual(BL.pick_slug(CFG, "a"), "a")

    def test_an_unknown_explicit_slug_is_refused_not_guessed(self):
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": []}))
        self.assertIsNone(BL.pick_slug(CFG, "nope"))

    def test_nothing_eligible_is_a_no_op_not_a_crash(self):
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": [
            {"slugs": ["a", "b", "c"]}]}))
        self.assertIsNone(BL.pick_slug(CFG))


class TestTheDescriptionIsAWatchPageDescription(unittest.TestCase):

    def test_chapters_are_rendered_from_the_meta_sidecar(self):
        d = BL._description(
            {"title": "T", "hook": "the hook"},
            {"chapters": [{"t": 0.0, "label": "Intro"},
                          {"t": 65.0, "label": "The gap"},
                          {"t": 190.5, "label": "Takeaway"}],
             "sources": ["World Bank WDI"]})
        self.assertIn("the hook", d)
        self.assertIn("0:00 Intro", d)
        self.assertIn("1:05 The gap", d)
        self.assertIn("3:10 Takeaway", d)
        self.assertIn("World Bank WDI", d)

    def test_it_survives_a_missing_sidecar(self):
        d = BL._description({"title": "T"}, {})
        self.assertIsInstance(d, str)


class TestTheJudgeActuallyWatchesALongVideo(unittest.TestCase):
    """Six stills is a Shorts number. On a 5-8 minute 16:9 video that is one
    glance per minute, and a judge that never sees minute 4 cannot honestly
    say the video holds up — it would rubber-stamp the dead middle a
    watch-page video dies of."""

    def test_a_short_still_gets_the_classic_sweep(self):
        plan = SR._frame_plan(40.0, None)
        mids = [l for _, l in plan if l.startswith("mid")]
        self.assertEqual(len(mids), 6, "existing Shorts verdicts must not move")

    def test_a_long_video_is_sampled_far_more_densely(self):
        plan = SR._frame_plan(360.0, None)
        mids = [l for _, l in plan if l.startswith("mid")]
        self.assertGreaterEqual(len(mids), 20)
        self.assertLessEqual(len(mids), 28, "bounded — vision calls cost")

    def test_the_sweep_reaches_the_end_of_a_long_video(self):
        plan = SR._frame_plan(360.0, None)
        self.assertGreater(max(t for t, _ in plan), 350.0)

    def test_chapters_become_segment_windows(self):
        """longform_render writes chapters, not segment_windows — the same
        information in the shape that video actually has."""
        plan = SR._frame_plan(300.0, {"chapters": [
            {"t": 0.0, "label": "Intro"}, {"t": 60.0, "label": "One"},
            {"t": 150.0, "label": "Two"}, {"t": 240.0, "label": "Takeaway"}]})
        labels = [l for _, l in plan]
        self.assertTrue(any(l.startswith("seg0:") for l in labels), labels)
        self.assertTrue(any(l.startswith("seg3:") for l in labels), labels)
        self.assertTrue(any(l.endswith(":mid") for l in labels))

    def test_a_real_manifest_still_wins_over_chapters(self):
        plan = SR._frame_plan(300.0, {
            "segment_windows": [[0.0, 150.0], [150.0, 300.0]],
            "chapters": [{"t": 0.0, "label": "x"}]})
        segs = {l.split(":")[0] for _, l in plan if l.startswith("seg")}
        self.assertEqual(segs, {"seg0", "seg1"})


class TestTheGateIsNotOptional(unittest.TestCase):

    SRC = (ROOT / "scripts" / "build_longform.py").read_text()

    def test_it_renders_the_16x9_watch_page_renderer(self):
        self.assertIn("longform_render.render(", self.SRC)

    def test_it_does_not_concatenate_shorts_any_more(self):
        for gone in ('"-f", "concat"', "lf_concat", "_intro_card"):
            self.assertNotIn(gone, self.SRC, gone)

    def test_the_gate_runs_before_any_upload(self):
        self.assertLess(self.SRC.index("showrunner_gate.run("),
                        self.SRC.index("up.upload("))

    def test_a_block_returns_without_uploading(self):
        after = self.SRC[self.SRC.index("if gate.get(\"blocked\")"):]
        head = after[:400]
        self.assertIn("NOT POSTING", head)
        self.assertIn("return", head)
        self.assertLess(self.SRC.index("if gate.get(\"blocked\")"),
                        self.SRC.index("up.upload("))

    def test_the_gate_is_told_this_is_a_publish_run(self):
        """`will_upload` is what makes `decide()` fail CLOSED — hardcoding
        False would turn every infra error into a silent ship."""
        self.assertIn("will_upload=will_upload", self.SRC)
        self.assertIn("will_upload = not args.dry_run", self.SRC)

    def test_the_thumbnail_and_chapters_reach_youtube(self):
        self.assertIn("thumbnail=thumb", self.SRC)
        self.assertIn("_description(story_cfg, meta)", self.SRC)


if __name__ == "__main__":
    unittest.main()
