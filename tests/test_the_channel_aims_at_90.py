"""THE CHANNEL AIMS AT 90, NOT AT THE PASS BAR.

Operator, 2026-09-23, on a 74 that shipped: "We need to be building a system
that consistently puts out 90s ... Don't ask if you can post a 74. Make a
system that makes better videos."

What that took, each held here:

  * a TARGET, in the registry (the only place channel policy lives), that a
    shipping cut is still repaired toward — while the gate's own pass bar
    and its sovereignty do not move;
  * a repair for the ILLUSTRATED arm: the brain redraws the scene the judge
    named from the judge's own words, verified like a first draft, and a
    losing redraw is undone;
  * the judge's scene ids read as the WINDOWS they are (see
    test_repair_targets_the_failure);
  * a CLOSING that is its own picture of the story's last line — full
    bleed, no bordered card — which is where the payoff points went;
  * a cut ranked by (ships, score), so polishing can never trade a SHIP for
    a higher-scoring BLOCK.
"""
from __future__ import annotations

import ast
import inspect
import json
import shutil
import sys
import tempfile
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


def _code(src: str) -> str:
    """Source round-tripped through the AST: comments gone, so a sentence
    explaining the rule can never satisfy a test for the rule."""
    return ast.unparse(ast.parse(src))


class TheTargetLivesInTheRegistry(unittest.TestCase):
    def test_the_explainer_aims_at_90(self):
        from shared import channel_registry as cr
        q = cr.quality("explainer", "data_story")
        self.assertEqual(q["target"], 90)
        self.assertGreaterEqual(q["polish_rounds"], 1)
        self.assertGreater(q["polish_budget_min"], 0)

    def test_an_invalid_block_means_no_polishing(self):
        from shared import channel_registry as cr
        self.assertTrue(cr.quality_problems({"target": 900}))
        self.assertTrue(cr.quality_problems({"target": 90, "polish_rounds": -1}))
        self.assertEqual(cr.quality_problems(
            {"target": 90, "polish_rounds": 2, "polish_budget_min": 170}), [])
        reg = json.loads((ROOT / "config" / "channel_registry.json").read_text())
        chs = reg["channels"]
        ex = chs["explainer"] if isinstance(chs, dict) else \
            next(c for c in chs if c["id"] == "explainer")
        ex["formats"]["data_story"]["quality"] = {"target": "ninety"}
        self.assertEqual(cr.quality("explainer", "data_story", reg)["polish_rounds"], 0)

    def test_the_pass_bar_did_not_move(self):
        from scripts import showrunner_review as sr
        self.assertLessEqual(sr.MIN_SCORE, 90)
        src = _code((ROOT / "scripts" / "post_stories.py").read_text())
        self.assertNotIn("MIN_SCORE", src)


class ThePolishLoop(unittest.TestCase):
    SRC = (ROOT / "scripts" / "post_stories.py").read_text()

    def test_a_shipping_cut_under_target_is_still_repaired(self):
        code = _code(self.SRC)
        self.assertIn("_under = _q['target'] is not None and _score < _q['target']", code)
        self.assertIn("if not (blocked or _under) or repairs >= _cap:", code)

    def test_a_higher_scoring_block_never_replaces_a_ship(self):
        self.assertIn("(not new_gate['blocked'], _new_score) > (not blocked, _prev_score)",
                      _code(self.SRC))

    def test_the_illustrated_arm_redraws_and_a_loser_is_undone(self):
        code = _code(self.SRC)
        self.assertIn("_rd.propose(slug, verdict, args.config)", code)
        self.assertIn("_undo()", code)

    def test_polishing_respects_the_runs_clock(self):
        self.assertIn("_minutes_since(_RUN_T0) > _q['polish_budget_min']", _code(self.SRC))

    def test_the_polish_loop_never_mentions_bypassing_the_gate(self):
        code = _code(self.SRC)
        self.assertNotIn("SHOWRUNNER", code.split("_q = _quality(")[1].split(
            "grade_mechanics")[0])


class TheRedraw(unittest.TestCase):
    VERDICT = {
        "score": 74,
        "weakest_scene": {"id": "seg4", "index": 4,
                          "failure_class": "static_reprise_outro",
                          "visible_evidence": "seg4 repeats seg3 under a card",
                          "root_cause": "the closing is a caption card",
                          "repair_goal": "give the closing its own beat"},
        "depictions": [{"id": "seg4", "bespoke": 1, "proves_claim": 0,
                        "note": "shows nothing about the bill growing"},
                       {"id": "seg1", "bespoke": 3, "proves_claim": 2, "note": "fine"}],
        "problems": ["seg4 is a near-duplicate", "seg1 has a ghost"],
    }

    def test_the_critique_is_the_judges_words_for_that_scene(self):
        from scripts import scene_redraw as rd
        c = rd.critique_for(self.VERDICT, 4)
        self.assertIn("give the closing its own beat", c)
        self.assertIn("shows nothing about the bill growing", c)
        self.assertIn("seg4 is a near-duplicate", c)
        self.assertNotIn("seg1 has a ghost", c)
        self.assertNotIn("fine", c)

    def _config(self):
        td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, td, True)
        p = td / "niche.config.json"
        shutil.copy(ROOT / "data_learning" / "niche.config.json", p)
        return p

    def _story(self, p):
        return next(s for s in json.loads(p.read_text())["stories"]
                    if s["slug"] == "amazon-still-shrinking")

    def test_a_weak_closing_is_redrawn_as_the_closing_and_undone(self):
        from scripts import scene_redraw as rd
        from data_learning import scene_author as SA
        p = self._config()
        before = self._story(p)
        seen = {}

        def fake(story_cfg, index, insight, prior, critique, log=print):
            seen.update(index=index, prior=prior, critique=critique)
            return (lambda *a: None), "def scene(cr, t, u, pts, host):\n    pass\n"
        with mock.patch.object(SA, "redraw", fake):
            plan = rd.propose("amazon-still-shrinking", self.VERDICT, p, log=lambda m: None)
        self.assertEqual((plan["role"], seen["index"]), ("closing", "closing"))
        self.assertIn("def scene(", seen["prior"])            # the teacher's code
        self.assertIn("give the closing its own beat", seen["critique"])
        self.assertIn("def scene", self._story(p)["closing_scene"])
        plan["undo"]()
        self.assertEqual(self._story(p), before)

    def test_a_weak_first_beat_is_beat_zero(self):
        from scripts import scene_redraw as rd
        from data_learning import scene_author as SA
        p = self._config()
        v = dict(self.VERDICT, weakest_scene={"id": "seg1", "repair_goal": "x"})
        with mock.patch.object(SA, "redraw",
                               return_value=((lambda *a: None), "def scene(): pass")):
            plan = rd.propose("amazon-still-shrinking", v, p, log=lambda m: None)
        self.assertEqual((plan["role"], plan["beat"]), ("beat", 0))
        self.assertEqual(self._story(p)["segments"][0]["illustrated_scene"],
                         "def scene(): pass")

    def test_a_weak_hook_redraws_the_hook_scene_when_there_is_one(self):
        from scripts import scene_redraw as rd
        from data_learning import scene_author as SA
        p = self._config()
        c = json.loads(p.read_text())
        st = next(x for x in c["stories"] if x["slug"] == "amazon-still-shrinking")
        st["hook_scene"], st["hook_data"] = "def scene(cr, t, u, pts, host): pass", 0
        p.write_text(json.dumps(c))
        v = dict(self.VERDICT, weakest_scene={"id": "hook", "repair_goal": "x"})
        seen = {}

        def fake(story_cfg, index, insight, prior, critique, log=print):
            seen.update(index=index, prior=prior)
            return (lambda *a: None), "def scene(cr, t, u, pts, host):\n    pass  # v2\n"
        with mock.patch.object(SA, "redraw", fake):
            plan = rd.propose("amazon-still-shrinking", v, p, log=lambda m: None)
        self.assertEqual((plan["role"], seen["index"]), ("hook", "hook"))
        self.assertIn("pass", seen["prior"])
        self.assertIn("# v2", self._story(p)["hook_scene"])

    def test_nothing_verified_changes_nothing(self):
        from scripts import scene_redraw as rd
        from data_learning import scene_author as SA
        p = self._config()
        before = p.read_text()
        with mock.patch.object(SA, "redraw", return_value=(None, "crashed")):
            with self.assertRaises(RuntimeError):
                rd.propose("amazon-still-shrinking", self.VERDICT, p, log=lambda m: None)
        self.assertEqual(p.read_text(), before)


class SavedCodeBeatsTheTeacher(unittest.TestCase):
    """A redraw that out-scored a hand-drawn teacher must be what renders
    next time — so saved code is looked up first."""

    def test_order(self):
        from data_learning import studio_render as R
        res = inspect.getsource(R._resolve_scene)
        a = res.index("scene = _sa.saved_scene(")
        b = res.index("scene = _ss.scene_for(slug, i)")
        c = res.index("scene = _sa.scene_for_segment(")
        self.assertLess(a, b)
        self.assertLess(b, c)
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertLess(src.index("_sa.saved_closing(story_cfg"),
                        src.index("_ss.closing_for(slug)"))
        self.assertLess(src.index('_sa.saved_bookend(story_cfg, "hook"'),
                        src.index("_ss.hook_for(slug)"))
        self.assertLess(src.index("_ss.hook_for(slug)"),
                        src.index('_sa.scene_for_bookend(\n                            story_cfg, "hook"'))


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheClosingIsItsOwnPicture(unittest.TestCase):
    def test_every_closing_teacher_passes_the_brains_checks_and_keeps_the_sky_clear(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        import tests.test_subject_scenes as T
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        for slug, (fn, idx) in SS.CLOSINGS.items():
            with self.subTest(slug=slug):
                st = next(x for x in cfg["stories"] if x["slug"] == slug)
                pts = T._beats(slug)[idx]
                src = inspect.getsource(fn).replace(f"def {fn.__name__}(", "def scene(")
                sfn = SA.compile_scene(src)
                self.assertEqual(SA.verify(sfn, pts, SA._story_say(st)), [])
                self.assertLessEqual(SA.held_ratio(sfn, pts), SA.MAX_HELD)
                ys = []
                real = SS.text

                def spy(cr, s, x, y, size, *a, **k):
                    ys.append(y - size)       # the glyphs' top, not the baseline
                    return real(cr, s, x, y, size, *a, **k)
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
                SS.text = spy
                try:
                    for u in (0.1, 0.5, 0.95):
                        fn(cairo.Context(surf), 3 + u, u, pts, lambda *a, **k: None)
                finally:
                    SS.text = real
                self.assertTrue(ys)
                self.assertFalse([y for y in ys if y < 480],
                                 "text reaches into y 140..480, where the closing "
                                 "line is drawn")

    def test_the_renderer_gives_the_closing_its_own_span_and_no_card(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn('_style["closing_scene"] = True', src)
        self.assertIn('closing_scene=bool(_style.get("closing_scene"))', src)
        fn = inspect.getsource(__import__(
            "data_learning.studio_render", fromlist=["x"]).build_story_ass)
        self.assertIn("if closing_scene:", fn)
        # the bubble is only drawn on the else branch
        tail = fn.split("if closing_scene:")[1]
        self.assertLess(tail.index("else:"), tail.index("{bubble}"))

    def test_a_brain_hook_is_asked_for_the_hook_line_and_saved(self):
        from data_learning import scene_author as SA
        from tests.test_the_brain_draws_the_scene import GOOD_MIN
        asked = {}

        def brain(prompt, model=None, timeout=None):
            asked["p"] = prompt
            return GOOD_MIN
        story = {"title": "t", "hook": "The clearing is dropping. The damage isn't.",
                 "segments": [{"say": "1.05 4.41 2019 2025"}]}
        ins = mock.Mock(items=[mock.Mock(label="2019", value=1.05),
                               mock.Mock(label="2025", value=4.41)], unit="")
        with mock.patch.object(SA, "ask_brain", brain):
            got = SA.scene_for_bookend(story, "hook", [ins], log=lambda m: None)
        self.assertIsNotNone(got)
        self.assertIn("THIS IS THE HOOK", asked["p"])
        self.assertIn("The damage isn't.", asked["p"])
        self.assertEqual((story["hook_scene"], story["hook_data"]), (GOOD_MIN, 0))

    def test_a_brain_closing_is_asked_for_the_closing_line(self):
        from data_learning import scene_author as SA
        asked = {}

        def brain(prompt, model=None, timeout=None):
            asked["p"] = prompt
            return None
        story = {"title": "t", "closing": "The bill still grows.",
                 "segments": [{"say": "x"}]}
        ins = mock.Mock(items=[mock.Mock(label="2019", value=1.0)], unit="")
        with mock.patch.object(SA, "ask_brain", brain):
            self.assertIsNone(SA.scene_for_closing(story, [ins], log=lambda m: None))
        self.assertIn("THIS IS THE CLOSING", asked["p"])
        self.assertIn("The bill still grows.", asked["p"])


class DataDoesNotRepeatAGesture(unittest.TestCase):
    """The same role in two scenes of one video resolved to the same
    animator — the hands-on-head pose three times in one video."""

    def test_each_scene_takes_the_least_used_act(self):
        from data_learning import subject_scenes as SS
        from data_learning import viz_scene as vs
        SS.reset_acts()
        n = len(vs.SCENE_ROLES["shock"])
        acts = [SS.act_for(f"scene{k}", "shock") for k in range(n)]
        self.assertEqual(len(set(acts)), n)
        self.assertEqual(SS.act_for("scene0", "shock"), acts[0])   # stable per scene
        SS.reset_acts()
        self.assertEqual(SS.act_for("x", "shock"), acts[0])
        self.assertEqual(SS.act_for(None, "shock"), "shock")        # outside a render

    def test_the_renderer_starts_each_video_fresh_and_names_each_scene(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_ss0.reset_acts()", src)
        from data_learning import subject_scenes as SS
        self.assertIn("act_for(_SCENE_KEY, role)", inspect.getsource(SS.place_host))
        self.assertIn("_SCENE_KEY = _SCENE_KEY, name", inspect.getsource(SS.render_build))


class OneVideoOneLook(unittest.TestCase):
    def test_a_beat_with_no_scene_turns_the_whole_video_current(self):
        src = _code((ROOT / "data_learning" / "studio_render.py").read_text())
        i = src.index("_got = _resolve_scene(slug, story_cfg, _i, _sg.insight)")
        tail = src[i:i + 600]
        self.assertIn("_style['style_arm'] = 'current'", tail)
        self.assertIn("_prepared = {}", tail)
        self.assertIn("_scene = _prepared.get(i)", src)


class ScenesCutTheyDoNotCrossfade(unittest.TestCase):
    def test_a_subject_scene_has_no_alpha_fade(self):
        src = _code((ROOT / "data_learning" / "studio_render.py").read_text())
        self.assertIn("_fades = '' if sp.get('kind') == 'subject_scene' else", src)


class NothingOnScreenSaysItTwice(unittest.TestCase):
    def test_a_scene_beat_gets_no_punch(self):
        from data_learning import studio_render as R
        src = inspect.getsource(R.build_story_ass)
        skip = src.index('if e.get("seg") in scene_beats:')
        self.assertLess(skip, src.index("Punch,,0,0,0,,"))
        self.assertIn('_style.setdefault("scene_beats", []).append(i)',
                      (ROOT / "data_learning" / "studio_render.py").read_text())

    def test_a_typed_double_hyphen_is_a_dash(self):
        from data_learning import studio_render as R
        self.assertEqual(R._dash("to 6,288 -- the lowest"), "to 6,288 \u2014 the lowest")
        self.assertNotIn("--", R._dash("a--b -- c"))
        src = inspect.getsource(R.build_story_ass)
        self.assertIn("_chunks(_dash(sent), 3)", src)
        self.assertIn("_chunks(_dash(st.hook), 2)", src)


if __name__ == "__main__":
    unittest.main()
