"""The opening is its own shot, and the hook names what the video is about.

Operator, 2026-10-17, of the livestock-methane video: "the first fucking 10
seconds of it is that one clip, and it's just the guy feeding the cow ...
That can't be an opening clip. People are going to swipe away", and of its
hook, "Everyone blames cars for climate change. The farm down the road is
doing it too.": "terrible hook".

All three videos posted that day had no hook scene. The beats spent the
video's drawing clock first and the hook got "this video's drawing budget
is spent" after two tries, so each opened on its first beat's picture for
the hook and the beat together (7.7 to 10.6 seconds). The predraw drew the
closing before the hook, so its clock ran out on the hook too: of ten
queued stories fully drawn, four had a closing and two a hook.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import post_stories as PS  # noqa: E402
from scripts import predraw_scenes as PD  # noqa: E402
from shared import hook_doctrine as HD  # noqa: E402


def _src(rel):
    return (ROOT / rel).read_text()


class TheHookIsDrawnFirst(unittest.TestCase):
    def test_the_predraw_draws_the_hook_before_the_closing(self):
        self.assertEqual(PD.BOOKENDS[0], "hook")
        self.assertIn("closing", PD.BOOKENDS)

    def test_the_render_gives_the_hook_its_own_clock(self):
        try:
            from data_learning import scene_author as SA
        except Exception:  # noqa: BLE001
            self.skipTest("no scene kit")
        self.assertGreaterEqual(SA.HOOK_MIN_S, 300)
        saved = SA._DEADLINE
        try:
            SA.set_budget(5)
            SA.reserve(SA.HOOK_MIN_S)
            self.assertGreater(SA._remaining(), SA.HOOK_MIN_S - 5)
            SA.set_budget(10_000)
            SA.reserve(60)                     # never takes clock away
            self.assertGreater(SA._remaining(), 9_000)
        finally:
            SA._DEADLINE = saved
        # and the renderer reserves it right before it draws the hook
        src = _src("data_learning/studio_render.py")
        i = src.index("_sa.reserve(_sa.HOOK_MIN_S)")
        j = src.index('story_cfg, "hook", [sg.insight for sg in st.segments]')
        self.assertLess(i, j)
        self.assertLess(j - i, 400)


class AStoryWithItsOpeningDrawnPostsFirst(unittest.TestCase):
    def test_opening_to_draw(self):
        self.assertEqual(PS._opening_to_draw({"hook": "x"}), 1)
        self.assertEqual(PS._opening_to_draw({"hook": "x", "hook_scene": "def scene(): pass"}), 0)
        self.assertEqual(PS._opening_to_draw({"hook": ""}), 0)

    def test_it_breaks_the_tie_never_skips(self):
        S = "illustrated_scene"
        stories = {"bare": {"hook": "h", "segments": [{S: 1}, {S: 1}]},
                   "opened": {"hook": "h", "hook_scene": "c", "segments": [{S: 1}, {S: 1}]},
                   "undrawn": {"hook": "h", "hook_scene": "c", "segments": [{S: 1}, {}]}}
        slugs = ["bare", "undrawn", "opened"]
        slugs.sort(key=lambda s: (False, PS._beats_to_draw(stories[s]),
                                  PS._opening_to_draw(stories[s])))
        self.assertEqual(slugs, ["opened", "bare", "undrawn"])

    def test_main_orders_by_it(self):
        tree = ast.parse(_src("scripts/post_stories.py"))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "main")
        self.assertTrue(any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "sort"
            and any(isinstance(x, ast.Name) and x.id == "_opening_to_draw"
                    for x in ast.walk(n))
            for n in ast.walk(main)))


class TheHookNamesTheThing(unittest.TestCase):
    def test_the_writer_is_told(self):
        ask = HD._prompt({"title": "Livestock Methane Could Hit 9.1 Billion Tons",
                          "hook": "x", "segments": [{"say": "cows burp methane"}]}, 5)
        self.assertIn("NAME THE THING", ask)
        self.assertIn("the farm down the road", ask)

    def test_the_listener_ranks_a_riddle_below_the_name(self):
        self.assertIn("ranks below every line that names it", HD._LISTEN)
        HD._LISTEN.format(say="s", cands="c")


if __name__ == "__main__":
    unittest.main()
