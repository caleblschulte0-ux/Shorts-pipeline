"""THE BRAIN DRAWS THE SCENE — and nothing it draws is trusted.

`data_learning/scene_author.py` asks the headless brain for a subject scene
for any beat no one hand-drew. Held here, without calling any brain:

  * the SANDBOX refuses imports, dunders and escape builtins before anything
    runs, and runs the code with the kit as its only globals;
  * every hand-drawn teacher passes through that same sandbox and verifier
    (so the rules are ones good scenes actually meet);
  * the VERIFIER refuses a scene that invents a number, changes its numbers
    when the data's order changes, holds still at its end, leaves Data out,
    or leaves a transparent frame;
  * a failed attempt is sent back with its reasons, and after the attempts
    run out the renderer gets None (the current look, recorded);
  * the renderer asks the author only when no teacher exists, and a verified
    scene is saved onto the segment and persisted with the story.
"""
from __future__ import annotations

import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import cairo  # noqa: F401
    HAVE_CAIRO = True
except Exception:  # noqa: BLE001
    HAVE_CAIRO = False


def _teacher_as_brain(fn):
    return inspect.getsource(fn).replace(f"def {fn.__name__}(", "def scene(")


GOOD_MIN = '''
def scene(cr, t, u, pts, host):
    rows = by_time([(str(l), float(v)) for l, v in pts])
    vgrad(cr, [(0.0, (30, 30, 60)), (1.0, (10, 10, 20))], 0, H)
    motes(cr, t, P["dust"], speed=-40, a=0.4)
    heat_shimmer(cr, t, 600, 1500, a=0.3)
    lab, val = rows[-1]
    fit_readout(cr, f"{val:.1f}", lab, 80, 520)
    host("point" if u < 0.5 else "cheer", 300 + 400 * u, 1500, 220)
'''


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheSandbox(unittest.TestCase):
    def test_it_refuses_escapes_before_running(self):
        from data_learning import scene_author as SA
        for bad in ("import os\ndef scene(cr,t,u,pts,host): pass",
                    "def scene(cr,t,u,pts,host):\n    open('/etc/passwd')",
                    "def scene(cr,t,u,pts,host):\n    x = cr.__class__",
                    "def scene(cr,t,u,pts,host):\n    eval('1')",
                    "def not_scene(): pass"):
            with self.assertRaises(SA.Refused, msg=bad):
                SA.compile_scene(bad)

    def test_it_runs_with_only_the_kit(self):
        from data_learning import scene_author as SA
        fn = SA.compile_scene(GOOD_MIN)
        self.assertNotIn("os", fn.__globals__)
        self.assertNotIn("open", fn.__globals__["__builtins__"])


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheTeachersPassTheSameChecks(unittest.TestCase):
    def test_every_sandboxable_teacher_verifies(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        import tests.test_subject_scenes as T
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        for slug, fns in SS.TEACHERS.items():
            st = next(x for x in cfg["stories"] if x["slug"] == slug)
            for i, (fn0, pts) in enumerate(zip(fns, T._beats(slug))):
                with self.subTest(scene=fn0.__name__):
                    fn = SA.compile_scene(_teacher_as_brain(fn0))
                    self.assertEqual(SA.verify(fn, pts, st["segments"][i].get("say", "")), [])


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheVerifierRefusesBadScenes(unittest.TestCase):
    PTS = [["2019", 1.05], ["2025", 4.41]]

    def _problems(self, code):
        from data_learning import scene_author as SA
        return SA.verify(SA.compile_scene(code), self.PTS)

    def test_a_good_minimal_scene_passes(self):
        self.assertEqual(self._problems(GOOD_MIN), [])

    def test_an_invented_number_is_refused(self):
        code = GOOD_MIN.replace('fit_readout(cr, f"{val:.1f}", lab, 80, 520)',
                                'fit_readout(cr, "7.3 million", lab, 80, 520)')
        self.assertTrue(any("does not have" in p for p in self._problems(code)))

    def test_trusting_list_order_is_refused(self):
        code = GOOD_MIN.replace("rows = by_time(", "rows = list(")
        self.assertTrue(any("order" in p for p in self._problems(code)))

    def test_a_still_scene_is_refused(self):
        code = GOOD_MIN.replace('    motes(cr, t, P["dust"], speed=-40, a=0.4)\n', "") \
                       .replace('    heat_shimmer(cr, t, 600, 1500, a=0.3)\n', "") \
                       .replace('300 + 400 * u, 1500, 220)',
                                '540, 1500, 220, pace=False)')
        self.assertTrue(any("holds still" in p for p in self._problems(code)))

    def test_a_count_up_wearing_the_next_label_is_refused(self):
        """ "$3.24 · February 2025" — a glide between two data points,
        printed with the second one's label."""
        code = GOOD_MIN.replace('lab, val = rows[-1]',
                                'lab, val = rows[-1][0], rows[0][1] + (rows[-1][1] - rows[0][1]) * u')
        self.assertTrue(any("does not have" in p for p in self._problems(code)))

    def test_text_in_the_caption_band_is_refused(self):
        code = GOOD_MIN.replace('fit_readout(cr, f"{val:.1f}", lab, 80, 520)',
                                'fit_readout(cr, f"{val:.1f}", lab, 80, 1780)')
        self.assertTrue(any("caption band" in p for p in self._problems(code)))

    def test_two_texts_on_top_of_each_other_are_refused(self):
        """ "wiped oleft, within two years" — two captions in one spot."""
        code = GOOD_MIN.replace('fit_readout(cr, f"{val:.1f}", lab, 80, 520)',
                                'fit_readout(cr, f"{val:.1f}", lab, 80, 520)\n'
                                '    text(cr, "one left", 90, 510, 90)')
        self.assertTrue(any("overlap" in p for p in self._problems(code)))

    def test_a_derived_number_that_contradicts_the_narration_is_refused(self):
        from data_learning import scene_author as SA
        self.assertEqual(SA._contradicts("10,100", {10000.0}, [5.0, 510.0]), 10000.0)
        self.assertIsNone(SA._contradicts("10,000", {10000.0}, []))
        self.assertIsNone(SA._contradicts("8.7", {9.1}, [8.7, 9.1]))   # a raw value
        self.assertIsNone(SA._contradicts("2020", {2019.0}, []))       # a year

    def test_units_decide_what_can_contradict(self):
        """ "4.2x" is the ratio 4.41/1.05, not a misprint of "$4.41"."""
        from data_learning import scene_author as SA
        said = {(float(t.replace(",", "")), u) for t, u in
                SA._units("$4.41 a pound, up from $1.05. Prices rose 10,000%.")}
        x = SA._Tok("4.2"); x.unit = "x"
        self.assertIsNone(SA._contradicts(x, said, [], 5))
        y = SA._Tok("10,100"); y.unit = "%"
        self.assertEqual(SA._contradicts(y, said, [], 5), 10000.0)

    def test_a_number_that_flickers_is_refused(self):
        """ "a hook number that flickers too fast to register" """
        code = GOOD_MIN.replace('lab, val = rows[-1]',
                                'lab, val = rows[int(u * 40) % len(rows)]')
        from data_learning import scene_author as SA
        probs = SA.verify(SA.compile_scene(code), self.PTS, secs=3.0)
        self.assertTrue(any("long enough to read" in p for p in probs))

    def test_a_number_under_another_rows_label_is_refused(self):
        """ "$1.05" headline over a "2025 · $4.41" label."""
        code = GOOD_MIN.replace('fit_readout(cr, f"{val:.1f}", lab, 80, 520)',
                                'fit_readout(cr, f"{rows[0][1]:.2f}", lab, 80, 520)')
        self.assertTrue(any("not 2025's" in p for p in self._problems(code)))

    def test_a_sticker_mascot_is_refused(self):
        """The rubric: a bit (setup -> action -> payoff) and he MOVES."""
        code = GOOD_MIN.replace('host("point" if u < 0.5 else "cheer", 300 + 400 * u, 1500, 220)',
                                'host("point", 540, 1500, 220)')
        probs = self._problems(code)
        self.assertTrue(any("one act" in p for p in probs))
        self.assertTrue(any("one spot" in p for p in probs))

    def test_no_data_and_no_background_are_refused(self):
        code = GOOD_MIN.replace('    host("point" if u < 0.5 else "cheer", 300 + 400 * u, 1500, 220)\n', "") \
                       .replace("0, H)", "0, 600)")
        probs = self._problems(code)
        self.assertTrue(any("Data is missing" in p for p in probs))
        self.assertTrue(any("full-bleed" in p for p in probs))


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheAuthorLoop(unittest.TestCase):
    def test_a_refusal_is_sent_back_and_a_fix_is_accepted(self):
        from data_learning import scene_author as SA
        bad = GOOD_MIN.replace('fit_readout(cr, f"{val:.1f}", lab, 80, 520)',
                               'fit_readout(cr, "7.3 million", lab, 80, 520)')
        asks = []

        def brain(prompt, model=None, timeout=None):
            asks.append(prompt)
            return bad if len(asks) == 1 else GOOD_MIN
        with mock.patch.object(SA, "ask_brain", brain):
            fn, code = SA.author("t", "topic", "say", [["2019", 1.05], ["2025", 4.41]],
                                 log=lambda m: None)
        self.assertIsNotNone(fn)
        self.assertEqual(code, GOOD_MIN)
        self.assertIn("FAILED THESE CHECKS", asks[1])
        self.assertIn("does not have", asks[1])

    def test_a_spent_drawing_budget_stops_asking(self):
        from data_learning import scene_author as SA
        SA.set_budget(0)
        try:
            with mock.patch.object(SA, "ask_brain") as asked:
                fn, why = SA.author("t", "x", "y", [["a", 1.0]], log=lambda m: None)
            asked.assert_not_called()
            self.assertIsNone(fn)
            self.assertIn("budget", why)
        finally:
            SA._DEADLINE = None

    def test_no_brain_means_none(self):
        from data_learning import scene_author as SA
        with mock.patch.object(SA, "ask_brain", return_value=None):
            fn, why = SA.author("t", "x", "y", [["a", 1.0]], log=lambda m: None)
        self.assertIsNone(fn)

    def test_a_verified_scene_is_saved_on_the_segment(self):
        from data_learning import scene_author as SA
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        ins = Insight(kind="trend", topic="t", main_insight="m",
                      items=[DataPoint(label="2019", value=1.05),
                             DataPoint(label="2025", value=4.41)],
                      source=Source(name="X", publisher="Y", url="u",
                                    access_date="d"), unit="dollars")
        story = {"title": "t", "segments": [{"topic": "x", "say": "y"}]}
        with mock.patch.object(SA, "ask_brain", return_value=GOOD_MIN):
            fn = SA.scene_for_segment(story, 0, ins, log=lambda m: None)
        self.assertIsNotNone(fn)
        self.assertEqual(story["segments"][0]["illustrated_scene"], GOOD_MIN)
        with mock.patch.object(SA, "ask_brain") as asked:   # reused, not re-asked
            self.assertIsNotNone(SA.scene_for_segment(story, 0, ins, log=lambda m: None))
            asked.assert_not_called()


class TheBrainKnowsTheRestOfTheVideo(unittest.TestCase):
    def test_the_other_scenes_are_in_the_prompt(self):
        from data_learning import scene_author as SA
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        st = next(x for x in cfg["stories"] if x["slug"] == "coffee-price-record")
        sib = SA.siblings(st, 2)
        self.assertIn("beat 0: The price of a pound of coffee", sib)
        self.assertIn("beat 1:", sib)
        self.assertNotIn("beat 2:", sib)
        asked = {}
        with mock.patch.object(SA, "ask_brain",
                               side_effect=lambda p, model=None, timeout=None: asked.setdefault("p", p) and None):
            from data_learning.insights import Insight
            from data_learning.sources.base import DataPoint, Source
            ins = Insight(kind="trend", topic="t", main_insight="m",
                          items=[DataPoint(label="2024", value=2.0),
                                 DataPoint(label="2025", value=4.41)],
                          source=Source(name="X", publisher="Y", url="u",
                                        access_date="d"), unit="dollars")
            SA.scene_for_segment(st, 2, ins, log=lambda m: None)
        self.assertIn("OTHER SCENES IN THIS VIDEO", asked["p"])

    def test_a_sequence_holds_its_first_item_where_the_judge_first_looks(self):
        from data_learning import subject_scenes as SS
        self.assertEqual(SS.step_through(0.25, 7)[0], 0)     # the judge's first look
        self.assertEqual(SS.step_through(0.85, 7), (6, 1.0))  # ...and its last
        ks = [SS.step_through(u / 100, 7)[0] for u in range(101)]
        self.assertEqual(ks, sorted(ks))
        self.assertEqual(set(ks), set(range(7)))
        rows = [("2024", 2.0), ("2025", 4.41)]
        self.assertEqual(SS.landed(rows, 1, 0.3), ("2024", 2.0))
        self.assertEqual(SS.landed(rows, 1, 0.9), ("2025", 4.41))


class TheRendererAsksOnlyWhenNoTeacherExists(unittest.TestCase):
    def test_wiring(self):
        from data_learning import studio_render as R
        res = inspect.getsource(R._resolve_scene)
        self.assertLess(res.index("_ss.scene_for(slug, i)"),
                        res.index("_sa.scene_for_segment("))
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn('a["illustrated_scene"] = b["illustrated_scene"]', src)


if __name__ == "__main__":
    unittest.main()
