"""THE NEW LOOK HAS TO ACTUALLY RENDER — two of A, two of B.

From 2026-10-05 18:34 to 2026-10-07 the explainer posted only current-look
(A) videos. Every illustrated (B) story fell back at render time because one
beat had no verified scene, and three things made that the rule rather than
the exception. Each is held here, without calling a brain:

  * the brain was shown the kit's SIGNATURES only, guessed `w, h = text(...)`
    (text returns a four-number box) and crashed on attempt 1 of most drafts;
    the kit list now states each helper's return, and a crash names the
    brain's own line so attempt 2 can fix it;
  * the renderer STOPPED at the first beat that failed, so the beats after it
    were never drawn and every render of that story started from beat 0
    again; it now tries every beat and keeps what passed;
  * nothing drew ahead: `scripts/predraw_scenes.py` runs in the story forge
    with its own clock, through the same author and verifier.

And one leak the light rule left: a flat scene `saved_scene` refused came
straight back through `scene_for_segment`, which only compiled it.
"""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
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


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheBrainIsToldWhatTheKitReturns(unittest.TestCase):
    def test_text_says_it_returns_a_box(self):
        from data_learning import scene_author as SA
        line = next(ln for ln in SA._sigs().splitlines()
                    if ln.strip().startswith("text("))
        self.assertIn("(x0, y0, x1, y1)", line)

    def test_every_documented_helper_carries_its_contract(self):
        from data_learning import scene_author as SA
        from data_learning import subject_scenes as SS
        sigs = SA._sigs()
        for n in SA.KIT_NAMES:
            obj = getattr(SS, n)
            if callable(obj) and inspect.getdoc(obj):
                line = next(ln for ln in sigs.splitlines()
                            if ln.strip().startswith(f"{n}("))
                self.assertIn("  # ", line, n)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class ACrashNamesTheLine(unittest.TestCase):
    CRASHER = '''
def scene(cr, t, u, pts, host):
    """HERO: a jar
    SUBSTANCE: water
    CAUSE: Data pours water in"""
    vgrad(cr, [(0, (20, 30, 60)), (1, (10, 10, 30))])
    w, h = text(cr, "x", 100, 600, 40)
    host("pour", 400, 1400, 200)
'''

    def test_the_unpack_crash_points_at_the_brains_line(self):
        from data_learning import scene_author as SA
        fn = SA.compile_scene(self.CRASHER)
        probs = SA.verify(fn, [["2019", 1.0], ["2025", 4.0]], "")
        crash = next(p for p in probs if p.startswith("crashed"))
        self.assertIn("too many values to unpack", crash)
        self.assertIn("line 7", crash)
        self.assertIn("w, h = text(", crash)

    def test_the_line_reaches_the_next_attempt(self):
        from data_learning import scene_author as SA
        prompts = []

        def brain(p, model=None, timeout=None):
            prompts.append(p)
            return self.CRASHER
        with mock.patch.object(SA, "ask_brain", side_effect=brain):
            fn, why = SA.author("t", "x", "y", [["2019", 1.0], ["2025", 4.0]],
                                attempts=2, log=lambda m: None)
        self.assertIsNone(fn)
        self.assertIn("w, h = text(", prompts[1].split("FAILED THESE CHECKS")[1])


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class AFlatSavedSceneIsRedrawnNotReused(unittest.TestCase):
    def test_scene_for_segment_runs_the_load_check(self):
        from data_learning import scene_author as SA
        src = inspect.getsource(SA.scene_for_segment)
        self.assertIn("saved_scene(seg", src)
        tree = ast.parse(textwrap.dedent(src))
        calls = [ast.unparse(n.func) for n in ast.walk(tree)
                 if isinstance(n, ast.Call)]
        self.assertNotIn("compile_scene", calls,
                         "a saved scene must go through saved_scene (compile "
                         "AND craft), never compile_scene alone")

    def test_a_refused_saved_scene_is_re_authored(self):
        from data_learning import scene_author as SA
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        ins = Insight(kind="trend", topic="t", main_insight="m",
                      items=[DataPoint(label="2019", value=1.05),
                             DataPoint(label="2025", value=4.41)],
                      source=Source(name="X", publisher="Y", url="u",
                                    access_date="d"), unit="dollars")
        story = {"title": "t", "segments": [{"topic": "x", "say": "y",
                                              "illustrated_scene": "OLD"}]}
        with mock.patch.object(SA, "saved_scene", return_value=None), \
                mock.patch.object(SA, "author", return_value=(lambda *a: None, "NEW")) as au:
            self.assertIsNotNone(SA.scene_for_segment(story, 0, ins, log=lambda m: None))
            au.assert_called_once()
        self.assertEqual(story["segments"][0]["illustrated_scene"], "NEW")


class TheRendererTriesEveryBeat(unittest.TestCase):
    def test_a_missing_beat_does_not_stop_the_rest_being_drawn(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        i = src.index("_got = _resolve_scene(slug, story_cfg, _i, _sg.insight)")
        loop = src[i:i + 300]
        self.assertNotIn("break", loop.split("if _missing:")[0])
        self.assertIn("_missing.append(_i)", loop)


class ThePredrawStepIsWired(unittest.TestCase):
    def test_the_forge_runs_it_with_the_brain(self):
        wf = (ROOT / ".github" / "workflows" / "story_forge.yml").read_text()
        self.assertIn("python3 scripts/predraw_scenes.py", wf)
        i = wf.index("- name: Draw the next new-look stories")
        step = wf[i:wf.index("- name:", i + 10)]
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", step)
        self.assertLess(wf.index("npm install -g @anthropic-ai/claude-code"),
                        wf.index("python3 scripts/predraw_scenes.py"))
        # its scenes are committed with the forge's stories
        commit = wf[wf.index("Commit the new stories"):]
        self.assertIn("data_learning/niche.config.json", commit)

    def test_it_draws_through_the_renderers_own_author(self):
        from scripts import predraw_scenes as P
        src = inspect.getsource(P.predraw)
        self.assertIn("SA.scene_for_segment(", src)
        self.assertIn("SA.saved_scene(", src)

    def test_it_picks_the_next_unposted_new_look_stories_in_order(self):
        from scripts import predraw_scenes as P
        from shared import style_arms
        cfg = {"stories": [{"slug": f"s{i}"} for i in range(40)]}
        ill = [s["slug"] for s in cfg["stories"]
               if style_arms.choose(s["slug"]) == "illustrated"]
        self.assertGreaterEqual(len(ill), 3)
        self.assertEqual(P.candidates(cfg, set(), 2), ill[:2])
        self.assertEqual(P.candidates(cfg, {ill[0]}, 2), ill[1:3])

    def test_a_scene_is_saved_onto_only_its_segment(self):
        import json
        import tempfile
        from scripts import predraw_scenes as P
        cfg = {"stories": [{"slug": "a", "segments": [{"say": "x"}, {"say": "y"}]},
                           {"slug": "b", "segments": [{"say": "z"}]}]}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.json"
            p.write_text(json.dumps(cfg))
            P._save_scene(p, "a", 1, "CODE")
            got = json.loads(p.read_text())
        self.assertEqual(got["stories"][0]["segments"][1]["illustrated_scene"], "CODE")
        self.assertNotIn("illustrated_scene", got["stories"][0]["segments"][0])
        self.assertNotIn("illustrated_scene", got["stories"][1]["segments"][0])


if __name__ == "__main__":
    unittest.main()
