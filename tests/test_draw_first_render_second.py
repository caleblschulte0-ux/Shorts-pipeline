"""A posting run spends its hours on stories that can post.

2026-10-11: the morning explainer run spent four hours on seven stories,
each finished in the retired look because a beat had no verified scene,
each refused at the door (`currency`), and posted nothing. Meanwhile stories
with two of three beats already drawn waited further down the queue.

Three things now:
  * the queue is ordered so the stories with the fewest beats left to draw
    render first (recently blocked ones still go to the back);
  * a render that would fall back to a look with no slot stops before it
    encodes (`studio_render.RetiredLook`), after saving what DID draw;
  * the predraw step, where postable scenes are really made, gets a bigger
    default budget.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import post_stories as PS  # noqa: E402

SA = "illustrated_scene"


def _src(rel):
    return (ROOT / rel).read_text()


class TheDrawnStoriesGoFirst(unittest.TestCase):
    def test_beats_to_draw_counts_missing_scenes(self):
        self.assertEqual(PS._beats_to_draw({"segments": [{SA: "x"}, {}, {SA: "y"}]}), 1)
        self.assertEqual(PS._beats_to_draw({"segments": [{SA: "x"}, {SA: "y"}]}), 0)
        self.assertEqual(PS._beats_to_draw({}), 0)

    def test_the_order_is_fewest_left_then_blocked_last(self):
        stories = {"none": {"segments": [{}, {}, {}]},
                   "two": {"segments": [{SA: 1}, {SA: 1}, {}]},
                   "all": {"segments": [{SA: 1}, {SA: 1}, {SA: 1}]},
                   "all_blocked": {"segments": [{SA: 1}, {SA: 1}, {SA: 1}]}}
        slugs = ["none", "all_blocked", "two", "all"]
        blocked = {"all_blocked"}
        slugs.sort(key=lambda s: (s in blocked, PS._beats_to_draw(stories[s])))
        self.assertEqual(slugs, ["all", "two", "none", "all_blocked"])

    def test_main_orders_the_queue_by_it(self):
        tree = ast.parse(_src("scripts/post_stories.py"))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "main")
        sorts = [n for n in ast.walk(main) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "sort"
                 and any(isinstance(x, ast.Name) and x.id == "_beats_to_draw"
                         for x in ast.walk(n))]
        self.assertTrue(sorts, "main() must order the queue by _beats_to_draw")


class ARetiredLookIsNotEncoded(unittest.TestCase):
    def test_render_stops_after_saving_what_drew(self):
        from data_learning import studio_render as S
        self.assertTrue(issubclass(S.RetiredLook, Exception))
        src = _src("data_learning/studio_render.py")
        i = src.index("raise RetiredLook(")
        before = src[max(0, i - 600):i]
        self.assertIn("_save_persisted_mechanics(config_path, story_cfg, slug)", before)
        self.assertIn("stop_if_retired", before)
        self.assertIn('"current" not in', before)

    def test_the_posting_run_asks_for_it_and_moves_on(self):
        tree = ast.parse(_src("scripts/post_stories.py"))
        handlers = [h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)
                    and isinstance(h.type, ast.Attribute)
                    and h.type.attr == "RetiredLook"]
        self.assertTrue(handlers, "post_stories must catch RetiredLook")
        self.assertTrue(any(isinstance(n, ast.Continue)
                            for h in handlers for n in ast.walk(h)))
        calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Attribute) and c.func.attr == "render"
                 and any(k.arg == "stop_if_retired" for k in c.keywords)]
        self.assertTrue(calls, "the first render must pass stop_if_retired")


class ThePredrawHasTheBudget(unittest.TestCase):
    def test_default_budget(self):
        wf = _src(".github/workflows/story_forge.yml")
        m = re.search(r'--stories "\$\{\{ inputs\.predraw_stories \|\| (\d+) \}\}" '
                      r'--budget-min "\$\{\{ inputs\.predraw_minutes \|\| (\d+) \}\}"', wf)
        self.assertIsNotNone(m)
        self.assertGreaterEqual(int(m.group(1)), 6)
        self.assertGreaterEqual(int(m.group(2)), 90)
        t = re.search(r"Draw the next new-look stories.*?timeout-minutes: (\d+)", wf, re.S)
        self.assertGreater(int(t.group(1)), int(m.group(2)))


if __name__ == "__main__":
    unittest.main()
