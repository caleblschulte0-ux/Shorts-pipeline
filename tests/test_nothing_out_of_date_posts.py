"""Nothing made to an older standard is uploaded, by any path.

Operator, 2026-10-09, after a twins video drawn on 10-07 and two retired-look
videos went out: "make sure that this never happens again, that we always
need to be running that new updated art style ... make sure that these new
updated script and wording things are all going out too ... double
checking, triple checking". And of the self-checkout opening: "perfect,
beautiful. It's like what I want everything to look like", with one note:
"Data maybe would have had a shopping cart and he would have been moving
down the line".
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import currency  # noqa: E402

GOOD = {"hook": "Self-checkout was sold as the future. It backfired.",
        "segments": [{"say": "Almost every big grocery chain has the machines now."}],
        "closing": "The machines did not save the stores."}


def _src(rel):
    return (ROOT / rel).read_text()


class ARenderSaysWhatItWasMadeTo(unittest.TestCase):
    def _mp4(self, d, side):
        mp4 = Path(d) / "v.mp4"
        mp4.write_bytes(b"")
        if side is not None:
            mp4.with_suffix(".style.json").write_text(json.dumps(side))
        return mp4

    def test_todays_render_of_a_good_story_passes(self):
        with tempfile.TemporaryDirectory() as d:
            mp4 = self._mp4(d, {"style_arm": "illustrated", "fallback_beats": [],
                                **currency.stamp()})
            self.assertEqual(currency.problems(mp4, GOOD), [])

    def test_a_render_with_no_record_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(currency.problems(self._mp4(d, None), GOOD))

    def test_an_older_standard_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            mp4 = self._mp4(d, {"style_arm": "illustrated", "standard": "2026-10-07"})
            self.assertTrue(any("standard" in p for p in currency.problems(mp4, GOOD)))

    def test_the_retired_look_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            mp4 = self._mp4(d, {"style_arm": "current", **currency.stamp()})
            self.assertTrue(any("retired" in p for p in currency.problems(mp4, GOOD)))

    def test_old_words_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            mp4 = self._mp4(d, {"style_arm": "illustrated", **currency.stamp()})
            readout = dict(GOOD, segments=[{"say": "9% recycles, 50% lands in dumps, 22% disappears."}])
            self.assertTrue(any("reads off" in p for p in currency.problems(mp4, readout)))
            lab = dict(GOOD, hook="Peanut allergies went from 0.4% to 1.4%.")
            self.assertTrue(any("hook" in p for p in currency.problems(mp4, lab)))


class EveryUploadPathChecksIt(unittest.TestCase):
    def test_the_renderer_stamps_the_sidecar(self):
        src = _src("data_learning/studio_render.py")
        self.assertLess(src.index("_style.update(_currency.stamp())"),
                        src.index("_style_arms.sidecar(out_path).write_text"))

    def test_the_posting_run_checks_before_the_review(self):
        src = _src("scripts/post_stories.py")
        render = src.index("studio_render.render(slug, out, config_path=args.config)")
        check = src.index("_currency.problems(out, _fresh)", render)
        self.assertLess(check, src.index("SHOWRUNNER gate", render))
        retell = src.index("_narration.retell(")
        self.assertLess(retell, src.index("_narration.problems(sc)", retell))
        self.assertLess(src.index("_narration.problems(sc)", retell), render)

    def test_the_mailbox_claim_checks_before_it_claims(self):
        src = _src("scripts/claim_reviews.py")
        fn = src[src.index("def _publish_explainer("):src.index("def _publish_trending(")]
        self.assertLess(fn.index("currency.problems(mp4, sc)"), fn.index("YouTubeUploader("))
        self.assertIn('".style.json"', src[src.index("def download_artifact("):])
        self.assertIn('".style.json"', _src("shared/review_mailbox.py"))

    def test_a_refusal_is_a_hold_not_a_fault(self):
        from scripts import post_stories as ps
        self.assertIn("not_current", ps.HELD_REASONS)


class ASavedSceneMeetsTodaysStandard(unittest.TestCase):
    def setUp(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        import inspect
        self.SA = SA
        code = inspect.getsource(SS.checkout_lanes).replace(
            "def checkout_lanes(", "def scene(")
        helpers = "\n\n".join(inspect.getsource(getattr(SS, n)) for n in
                              ("_co_cart", "_co_basket", "_co_till", "_co_kiosk", "_co_at"))
        self.code = helpers + "\n\n" + code
        self.seg = {"say": "Almost every big grocery chain has self-checkout now.",
                    "topic": "self-checkout lanes", "illustrated_scene": self.code}
        self.pts = [["2000", 6.0], ["2012", 33.0], ["2023", 92.0]]

    def test_stamping(self):
        st = self.SA.stamped(self.code)
        self.assertEqual(self.SA.standard_of(st), self.SA.STANDARD)
        self.assertEqual(self.SA.standard_of(self.SA.stamped(st)), self.SA.STANDARD)
        self.assertEqual(st.count("# scene standard:"), 1)
        self.SA.compile_scene(st)

    def _saved(self, glance_problems, viewer=True, look=None):
        def fake_glance(fn, pts, log=print, say="", seen_by=None):
            if viewer and seen_by is not None:
                seen_by.append("viewer")
            return list(glance_problems)
        with mock.patch.object(self.SA, "_seg_pts", return_value=self.pts), \
                mock.patch.object(self.SA, "glance", side_effect=fake_glance), \
                mock.patch.object(self.SA, "look_again", return_value=look) as la:
            fn = self.SA.saved_scene(self.seg, log=lambda m: None)
        return fn, la

    def test_an_old_scene_the_viewer_passes_is_kept_and_stamped(self):
        fn, la = self._saved([])
        self.assertIsNotNone(fn)
        self.assertTrue(la.called, "it gets the look again beside the bars")
        self.assertEqual(self.SA.standard_of(self.seg["illustrated_scene"]), self.SA.STANDARD)

    def test_an_old_scene_the_viewer_fails_is_redrawn(self):
        fn, _ = self._saved(["the picture is a generic stand-in"])
        self.assertIsNone(fn)
        self.assertIsNone(self.seg["illustrated_scene"])

    def test_with_no_viewer_it_is_used_but_not_stamped(self):
        fn, la = self._saved([], viewer=False)
        self.assertIsNotNone(fn)
        self.assertFalse(la.called)
        self.assertIsNone(self.SA.standard_of(self.seg["illustrated_scene"]))

    def test_a_current_scene_is_not_judged_again(self):
        self.seg["illustrated_scene"] = self.SA.stamped(self.code)
        with mock.patch.object(self.SA, "glance") as g:
            self.assertIsNotNone(self.SA.saved_scene(self.seg, log=lambda m: None))
        self.assertFalse(g.called)

    def test_every_new_scene_is_stamped(self):
        src = _src("data_learning/scene_author.py")
        fn = src[src.index("def author("):src.index("# ----------------------------------------------------------- look again")]
        self.assertIn("return fn, stamped(code)", fn)

    def test_the_renderer_and_predraw_save_a_restamped_scene(self):
        r = _src("data_learning/studio_render.py")
        self.assertIn('seg_cfg.get("illustrated_scene") != _was', r)
        self.assertIn('story_cfg.get("hook_scene") != _wash', r)
        self.assertIn('story_cfg.get("closing_scene") != _wasc', r)
        self.assertIn('seg_cfg.get("illustrated_scene") != _was', _src("scripts/predraw_scenes.py"))


class TheCheckoutIsTheBar(unittest.TestCase):
    def test_it_is_the_posted_scene_verbatim(self):
        from data_learning import subject_scenes as SS
        import inspect
        cfg = json.loads(_src("data_learning/niche.config.json"))
        story = next((s for s in cfg["stories"] if s["slug"] == "self-checkout-cashier-jobs"), None)
        if story is None:
            self.skipTest("the self-checkout story left the queue")
        posted = story["segments"][0]["illustrated_scene"]
        posted = re.sub(r"^# scene standard: \S+\n", "", posted, flags=re.M)
        for a, b in [("_cart", "_co_cart"), ("_basket", "_co_basket"), ("_till", "_co_till"),
                     ("_kiosk", "_co_kiosk"), ("_at", "_co_at")]:
            posted = re.sub(r"\b" + a + r"\b", b, posted)
        def body(code, name):
            fn = next(n for n in ast.parse(code).body
                      if isinstance(n, ast.FunctionDef) and n.name == name)
            return [ast.dump(x) for x in fn.body[1:]]      # all but the docstring
        self.assertEqual(body(posted, "scene"),
                         body(inspect.getsource(SS.checkout_lanes), "checkout_lanes"),
                         "the bar is the scene the owner saw, not a re-draw of it")

    def test_it_passes_every_check(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        self.assertEqual(SA.verify(SS.checkout_lanes, SA.CHECKOUT_ROWS), [])

    def test_the_brain_is_shown_it_and_the_note(self):
        from data_learning import scene_author as SA
        p = SA.build_prompt("t", "topic", "say", [["a", 1.0], ["b", 2.0]], "")
        self.assertIn("def checkout_lanes(", p)
        self.assertIn("shopping cart", p)
        self.assertIn("DATA IS A CHARACTER IN THE STORY'S WORLD", p)
        src = _src("data_learning/scene_author.py")
        la = src[src.index("def look_again("):]
        self.assertIn("SS.checkout_lanes", la[:la.index("return None")+2000])


if __name__ == "__main__":
    unittest.main()
