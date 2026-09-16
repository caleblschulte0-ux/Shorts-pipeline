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
import re
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

    def test_a_missing_thumbnail_stops_a_publish_run_before_upload(self):
        """Doctor finding f87f60f38feb: make_thumbnail()'s failure is caught
        broadly inside the renderer (a dry run must still preview the rest
        of the video), so the ONLY place left to refuse a publish without
        the promised custom thumbnail is here, before the uploader ever
        sees the video."""
        self.assertIn("thumbnail_ok", self.SRC)
        check = self.SRC[self.SRC.index("if will_upload and not thumbnail_ok"):]
        self.assertIn("NOT POSTING", check[:400])
        self.assertIn("return", check[:400])
        self.assertLess(
            self.SRC.index("if will_upload and not thumbnail_ok"),
            self.SRC.index("up.upload("))
        self.assertLess(
            self.SRC.index("if will_upload and not thumbnail_ok"),
            self.SRC.index("gate = showrunner_gate.run("),
            "no reason to spend a review call on a cut that cannot publish")


class TestTheThumbnailFloorActuallyRuns(unittest.TestCase):
    """Behavioral proof, not just source position: inject a renderer that
    reports a bad thumbnail and prove `main()` never reaches the uploader,
    then inject one that reports a good thumbnail and prove it does."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-thumb-"))
        self._saved = (BL.EXPLAINER_LOG, BL.LONGFORM_LOG, BL.CONFIG, BL.OUT)
        BL.EXPLAINER_LOG = self.tmp / "explainer_posted_log.json"
        BL.LONGFORM_LOG = self.tmp / "longform_log.json"
        BL.CONFIG = self.tmp / "niche.config.json"
        BL.OUT = self.tmp / "output"
        BL.EXPLAINER_LOG.write_text(json.dumps({"posted": {
            "z": {"url": "u", "at": "2026-08-01T00:00:00+00:00"}}}))
        BL.LONGFORM_LOG.write_text(json.dumps({"posted": []}))
        BL.CONFIG.write_text(json.dumps(
            {"stories": [{"slug": "z", "title": "Z", "hook": "hook z"}]}))

        import data_learning
        self._real_module = sys.modules.get("data_learning.longform_render")
        self._real_attr = getattr(data_learning, "longform_render", None)
        self._data_learning = data_learning

    def tearDown(self):
        (BL.EXPLAINER_LOG, BL.LONGFORM_LOG,
         BL.CONFIG, BL.OUT) = self._saved
        if self._real_module is not None:
            sys.modules["data_learning.longform_render"] = self._real_module
        else:
            sys.modules.pop("data_learning.longform_render", None)
        if self._real_attr is not None:
            self._data_learning.longform_render = self._real_attr
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _install_fake_renderer(self, thumbnail_ok: bool):
        """A stand-in for data_learning.longform_render — the real module
        transitively imports PIL/matplotlib, which this test does not need
        and may not have installed."""
        import types
        fake = types.ModuleType("data_learning.longform_render")

        def render(slug, out_path, voice=None, config_path=None):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"not a real mp4")
            if thumbnail_ok:
                out_path.with_suffix(".jpg").write_bytes(b"not a real jpg")
            out_path.with_suffix(".meta.json").write_text(json.dumps({
                "slug": slug, "duration": 300.0,
                "chapters": [{"t": 0.0, "label": "Intro"}],
                "sources": [], "thumbnail_ok": thumbnail_ok}))
            return out_path

        fake.render = render
        sys.modules["data_learning.longform_render"] = fake
        self._data_learning.longform_render = fake

    def test_a_bad_thumbnail_never_reaches_the_gate_or_the_uploader(self):
        self._install_fake_renderer(thumbnail_ok=False)
        from unittest import mock
        from shared import showrunner_gate
        from shared import uploaders
        with mock.patch.object(showrunner_gate, "run") as gate_run, \
             mock.patch.object(uploaders, "YouTubeUploader") as uploader_cls, \
             mock.patch.object(sys, "argv", ["build_longform.py"]):
            rc = BL.main()
        self.assertEqual(rc, 4)
        gate_run.assert_not_called()
        uploader_cls.assert_not_called()

    def test_a_good_thumbnail_reaches_the_uploader(self):
        self._install_fake_renderer(thumbnail_ok=True)
        from unittest import mock
        from shared import showrunner_gate
        from shared import uploaders

        class _FakeResult:
            url = "https://youtu.be/fake"

        with mock.patch.object(showrunner_gate, "run",
                                return_value={"blocked": False,
                                              "verdict": {"score": 9}}), \
             mock.patch.object(uploaders, "YouTubeUploader") as uploader_cls, \
             mock.patch.object(sys, "argv", ["build_longform.py"]):
            uploader_cls.return_value.upload.return_value = _FakeResult()
            rc = BL.main()
        self.assertEqual(rc, 0)
        uploader_cls.return_value.upload.assert_called_once()
        _, kwargs = uploader_cls.return_value.upload.call_args
        self.assertIsNotNone(kwargs.get("thumbnail"))


if __name__ == "__main__":
    unittest.main()


class TestTheDoctorCanSeeLongForm(unittest.TestCase):
    """The operator asked for the doctor to work on long-form. It reads the
    evidence pack and its brief — a mandate that reaches neither is a
    sentence nobody acts on."""

    def setUp(self):
        import doctor
        self.doctor = doctor
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-doc-"))
        self._root = doctor.ROOT
        doctor.ROOT = self.tmp
        (self.tmp / "state").mkdir()
        for n in ("posted_log.json", "explainer_posted_log.json",
                  "third_posted_log.json"):
            (self.tmp / "state" / n).write_text(json.dumps({"posted": []}))
        (self.tmp / "state" / "longform_log.json").write_text(json.dumps(
            {"posted": [
                {"at": "2026-08-02T00:00:00+00:00", "title": "old concat",
                 "url": "u1", "slugs": ["a", "b"]},
                {"at": "2026-08-30T00:00:00+00:00", "title": "real 16:9",
                 "url": "u2", "slug": "c", "format": "long_form_16x9",
                 "duration_s": 372.0, "showrunner_score": 78}]}))

    def tearDown(self):
        self.doctor.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_pack_carries_long_form(self):
        lf = self.doctor.evidence_pack()["channel_performance"]["longform"]
        self.assertEqual(lf["total_posted"], 2)
        self.assertEqual(lf["recent"][-1]["showrunner_score"], 78)
        self.assertEqual(lf["recent"][-1]["duration_s"], 372.0)

    def test_it_points_at_the_code_not_just_the_numbers(self):
        lf = self.doctor.evidence_pack()["channel_performance"]["longform"]
        for key in ("renderer", "builder", "workflow", "gate", "verdicts"):
            self.assertTrue(lf.get(key), key)

    def test_the_retired_format_is_labelled_not_averaged_in(self):
        """The pre-08-25 entries measure a different product; a reviewer
        reasoning from their numbers would draw the wrong conclusion."""
        lf = self.doctor.evidence_pack()["channel_performance"]["longform"]
        self.assertEqual(lf["recent"][0]["format"], "legacy_vertical_concat")
        self.assertIn("NOT comparable", lf["note"])

    def test_a_missing_log_does_not_crash_the_pack(self):
        (self.tmp / "state" / "longform_log.json").unlink()
        lf = self.doctor.evidence_pack()["channel_performance"]["longform"]
        self.assertEqual(lf["total_posted"], 0)

    def test_the_brief_gives_the_reviewer_the_assignment(self):
        p = (ROOT / "doctor" / "PROMPTS.md").read_text()
        self.assertIn("LONG-FORM IS A STANDING ASSIGNMENT", p)
        self.assertIn("channel_performance.longform", p)
        self.assertIn("longform:<slug>", p)

    def test_the_brief_refuses_the_obvious_shortcut(self):
        """'Post more long-form by loosening its gate' is the one proposal
        this whole change exists to make unavailable."""
        p = (ROOT / "doctor" / "PROMPTS.md").read_text()
        seg = p.split("LONG-FORM IS A STANDING ASSIGNMENT", 1)[1][:2200]
        self.assertIn("loosening the long-form gate", seg)
        self.assertIn("unjudged", seg)


class TestTheStillFallbackHasRealMotion(unittest.TestCase):
    """Doctor finding f08a10274ea9: the Sept 6 production run degraded all
    three beats to the still fallback and the 47s master measured 8.4
    effective fps against the phase-1 floor of 11.0. The gate was right to
    block it — the fix belongs in the renderer, not the gate.

    `data_learning/story.py`'s `Segment.insight` is kept ON PURPOSE so a
    renderer can re-render the chart at frames = beat_seconds * 30 once the
    real beat length is known (its own docstring says so) — exactly the
    technique `data_learning/studio_render.py` uses for the primary
    channel. `longform_render.py` carried that field on every Segment and
    never spent it: `_still_beat` only ever grabbed the LAST frame of
    `story.build()`'s cheap 6-frame preview and froze it, then (until this
    change) papered over the freeze with a Ken Burns push — the exact
    "camera movement" `data_learning/tests/test_no_camera_shake.py` retires
    on every other render path.

    These are source checks, not a rendered measurement: this sandbox has
    neither Pillow, matplotlib nor ffmpeg (`import data_learning.
    longform_render` itself fails here on a missing PIL, transitively,
    through story -> viz_director -> viz_scene), so a real frame-diffing
    test can only run where the full render stack is installed — the
    auto-merge gate's CI, which does. What IS checkable everywhere is that
    the capability is actually wired: the real re-render call is present,
    scaled to the beat's own duration, and the old camera-push path is
    gone.
    """

    SRC = (ROOT / "data_learning" / "longform_render.py").read_text()

    def test_the_fallback_rerenders_the_segments_own_insight(self):
        """Not a silent default: `seg.insight` (or `ins`, its local alias)
        must actually reach `charts.render_story_build`, or the capability
        is carried on every Segment and spent by nobody — the exact shape
        CLAUDE.md calls out ("a capability nothing calls is not a
        capability")."""
        self.assertIn("seg.insight", self.SRC)
        call = self.SRC[self.SRC.index("charts.render_story_build("):][:400]
        self.assertIn("ins", call)

    def test_the_frame_count_scales_with_the_real_beat_duration(self):
        """The old story.build() preview is a fixed `frames=6` — that
        constant must never be what reaches the renderer's own build call,
        or every beat still only ever gets 6 frames no matter how long it
        plays."""
        call = self.SRC[self.SRC.index("charts.render_story_build("):][:400]
        self.assertIn("frames=nfr", call)
        self.assertNotIn("frames=6", call)
        self.assertIn("dur * FPS", self.SRC)

    def test_the_finished_chart_tail_is_bounded(self):
        """Reuses studio_render's own `_full_by` rather than re-deriving
        it — that function exists specifically because an unbounded tail on
        a long span is what tripped the cadence ceiling there first."""
        self.assertIn("_full_by(dur)", self.SRC)

    def test_frames_are_read_back_in_numeric_not_lexicographic_order(self):
        """A 3+ digit build (frame 100+) sorts wrong as text
        ('build100.png' < 'build2.png') — a plain glob+sort would play the
        animation out of order without ever raising."""
        self.assertIn("_BUILD_NUM", self.SRC)
        self.assertIn("int(_BUILD_NUM.search(fp.name).group(1))", self.SRC)

    def test_the_camera_push_helper_is_actually_gone(self):
        for gone in ("_kenburns_clip", "_title_card(", "zoompan"):
            self.assertNotIn(gone, self.SRC, gone)

    def test_a_beat_with_no_insight_degrades_to_a_static_hold_not_a_crash(self):
        self.assertIn("segment carries no insight to re-render", self.SRC)
        still = self.SRC[self.SRC.index("def _still_beat("):]
        self.assertIn("_static_hold_clip", still[:900])

    def test_title_and_closing_cards_reveal_instead_of_holding_static(self):
        """The intro/outro cards used to sit under the same camera push —
        their replacement must still guarantee a fresh visible change often
        enough to clear the cadence gate's frozen-run ceiling regardless of
        how short the card's own text is relative to its narrated window."""
        self.assertIn("_reveal_card_clip(", self.SRC)
        self.assertIn("SAFE_GAP_S", self.SRC)
        self.assertLess(float(re.search(r"SAFE_GAP_S = ([\d.]+)",
                                        self.SRC).group(1)), 1.875,
                        "must stay under the phase-1 max_dup_run ceiling "
                        "(45 frames @ 24fps)")


if __name__ == "__main__":
    unittest.main()
