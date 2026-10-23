"""A SAVED SCENE THE RUN REFUSED IS WRITTEN DOWN AS REFUSED.

2026-10-22/23, after the scene standard moved: the explainer posted nothing
for a day. Every saved scene stamped under the old standard was re-judged,
and the ones that failed were cleared in memory ("judged once: redraw it").
But the flush only copied a scene that was THERE, so the stale code stayed
in `niche.config.json`, and every run re-judged and refused it again. Red
hair, cryonics and body renewal spent the drawing budget on the same
refusals in 4 of 4 runs, and never got the fresh drawing they needed.

The flush now writes the refusal, but only over the exact code that was
refused, so a scene another run drew in the meantime is never overwritten.
No check moved: a refused scene is still refused, it just stays refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import scene_author as SA                 # noqa: E402
from data_learning import studio_render as SR                # noqa: E402
from data_learning import subject_scenes as SS               # noqa: E402

OLD = "# scene standard: 2026-10-09\ndef scene(cr, t): pass\n"


def _refuse(seg_cfg, log=print):
    seg_cfg["illustrated_scene"] = None       # what recertify does on a fail
    return None


class ARefusedSceneStaysRefused(unittest.TestCase):

    def setUp(self):
        SR._PERSISTED[:] = []
        SR._REFUSED.clear()

    def _write(self, td, seg_scene=OLD, hook=OLD):
        path = Path(td) / "niche.config.json"
        path.write_text(json.dumps({"stories": [
            {"slug": "red-hair", "hook_scene": hook,
             "segments": [{"say": "a"}, {"say": "b", "illustrated_scene": seg_scene}]},
            {"slug": "other", "segments": [{"illustrated_scene": OLD}]}]}))
        return path

    def _resolve(self, story_cfg):
        with mock.patch.object(SA, "saved_scene", _refuse), \
             mock.patch.object(SS, "scene_for", lambda slug, i: None), \
             mock.patch.object(SA, "scene_for_segment",
                               lambda *a, **k: None):
            return SR._resolve_scene("red-hair", story_cfg, 1, None)

    def test_the_refusal_reaches_the_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td)
            story_cfg = json.loads(path.read_text())["stories"][0]
            self.assertIsNone(self._resolve(story_cfg))
            self.assertIn("red-hair", SR._PERSISTED)
            SR._save_persisted_mechanics(path, story_cfg, "red-hair")
            got = json.loads(path.read_text())
            self.assertIsNone(got["stories"][0]["segments"][1]["illustrated_scene"],
                              "the refused scene is still saved, so the next "
                              "run re-judges and refuses it again")
            self.assertEqual(got["stories"][1]["segments"][0]["illustrated_scene"],
                             OLD, "another story was touched")

    def test_a_scene_drawn_since_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td)
            story_cfg = json.loads(path.read_text())["stories"][0]
            self._resolve(story_cfg)
            cfg = json.loads(path.read_text())
            fresh = "# scene standard: today\ndef scene(cr, t): pass\n"
            cfg["stories"][0]["segments"][1]["illustrated_scene"] = fresh
            path.write_text(json.dumps(cfg))
            SR._save_persisted_mechanics(path, story_cfg, "red-hair")
            got = json.loads(path.read_text())
            self.assertEqual(got["stories"][0]["segments"][1]["illustrated_scene"],
                             fresh)

    def test_a_refused_bookend_reaches_the_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td)
            story_cfg = json.loads(path.read_text())["stories"][0]
            story_cfg["hook_scene"] = None
            SR._note_refused("red-hair", "hook_scene", OLD)
            SR._save_persisted_mechanics(path, story_cfg, "red-hair")
            got = json.loads(path.read_text())
            self.assertIsNone(got["stories"][0]["hook_scene"])

    def test_a_scene_that_was_never_there_records_nothing(self):
        story_cfg = {"slug": "red-hair", "segments": [{}, {"say": "b"}]}
        self._resolve(story_cfg)
        self.assertEqual(SR._REFUSED, {})

    def test_the_render_loop_notes_refused_bookends(self):
        import inspect
        src = inspect.getsource(SR)
        self.assertIn('_note_refused(slug, "hook_scene", _wash)', src)
        self.assertIn('_note_refused(slug, "closing_scene", _wasc)', src)


if __name__ == "__main__":
    unittest.main()
