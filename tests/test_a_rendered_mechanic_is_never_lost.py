"""THE BEST ANIMATION ON THE CHANNEL WAS LOST FROM EVERY PLACE THE BRAIN LEARNS.

`fusion-net-energy-gain`, 2026-09-16. The showrunner called its
bolt-per-0.2-megajoule grid "a genuinely good demonstration" twice and
blocked it twice on craft alone — two mascots on screen, three text layers
in one band, a legend covered. The run that finally shipped had re-invented
the story from scratch without it. Today its code is in neither the config,
nor the 60-slot library, nor the ledger, nor git. Asked what makes a video
work, the operator said "that laser one".

Three mechanisms, each held here:

  1. NOTHING IN CODE PERSISTED A MECHANIC THAT RENDERED. The only caller of
     `_record_mechanic` was the render-time invention pass, which is OFF in
     CI; the brain was asked to save its work by step 5 of a prompt. Now the
     renderer records it at the commit point and writes it back to the
     config segment it came from — by POINTER, because `story.build`
     reorders and drops segments, so an index would hit the wrong one.
  2. THE WORKFLOW'S HANDS-OFF CHECK COUNTED ONLY KIT SCENES, so a story
     already carrying a brain mechanic read as undirected and the next brain
     step overwrote it.
  3. THE LIBRARY CAP (60) EVICTED IT while forty static mechanics stayed.
     Starred entries are never evicted now; the cap is 120.
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

from data_learning import studio_render as SR                # noqa: E402
from data_learning import viz_director as VD                 # noqa: E402


class _Ins:
    def __init__(self, scene=None, seg_cfg=None, topic="t"):
        self.scene = scene
        self.seg_cfg = seg_cfg
        self.topic = topic


MECH = {"mechanic": "bolt-grid", "concept": "one bolt per 0.2 MJ",
        "code": "img = subject_image('laser')\npaste(img, 0, 0)"}


class TheRendererRecordsWhatItCommits(unittest.TestCase):

    def setUp(self):
        SR._PERSISTED[:] = []

    def test_a_rendered_mechanic_lands_in_its_config_segment_and_the_library(self):
        seg_cfg = {"key": "k", "topic": "the energy gain"}
        ins = _Ins(scene=dict(MECH, extra="ignored"), seg_cfg=seg_cfg)
        recorded = []
        with mock.patch.object(VD, "_record_mechanic",
                               lambda i, sc: recorded.append(sc)):
            SR._persist_rendered_mechanic(ins, "fusion")
        self.assertEqual(seg_cfg["scene"], MECH,
                         "the config segment did not get exactly "
                         "{mechanic, concept, code}")
        self.assertEqual(len(recorded), 1, "the library was not told")
        self.assertIn("fusion", SR._PERSISTED)

    def test_a_kit_scene_is_not_a_mechanic_and_is_left_alone(self):
        seg_cfg = {"scene": {"elements": [{"type": "object"}]}}
        ins = _Ins(scene={"elements": [{"type": "object"}]}, seg_cfg=seg_cfg)
        with mock.patch.object(VD, "_record_mechanic") as rec:
            SR._persist_rendered_mechanic(ins, "s")
            rec.assert_not_called()
        self.assertEqual(seg_cfg["scene"], {"elements": [{"type": "object"}]})
        self.assertEqual(SR._PERSISTED, [])

    def test_an_unchanged_scene_does_not_dirty_the_config(self):
        seg_cfg = {"scene": dict(MECH)}
        ins = _Ins(scene=dict(MECH), seg_cfg=seg_cfg)
        with mock.patch.object(VD, "_record_mechanic"):
            SR._persist_rendered_mechanic(ins, "s")
        self.assertEqual(SR._PERSISTED, [], "a no-op write was scheduled")

    def test_it_never_raises_into_the_render(self):
        """Losing a record is bad; losing the render over it is worse."""
        ins = _Ins(scene=dict(MECH), seg_cfg={})
        with mock.patch.object(VD, "_record_mechanic",
                               side_effect=RuntimeError("disk on fire")):
            SR._persist_rendered_mechanic(ins, "s")      # must not raise
        self.assertEqual(ins.seg_cfg.get("scene"), MECH,
                         "a library failure must not cost the config write")


class TheSaveTouchesOnlyThisStory(unittest.TestCase):

    def setUp(self):
        SR._PERSISTED[:] = []

    def _cfg(self):
        return {"stories": [
            {"slug": "fusion", "segments": [{"key": "a"}, {"key": "b"}, {"key": "c"}]},
            {"slug": "other", "segments": [{"key": "z", "scene": {"elements": [1]}}]},
        ]}

    def test_the_scene_is_written_to_the_matching_segment_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "niche.config.json"
            path.write_text(json.dumps(self._cfg()))
            story_cfg = json.loads(json.dumps(self._cfg()["stories"][0]))
            story_cfg["segments"][1]["scene"] = dict(MECH)
            SR._PERSISTED.append("fusion")
            SR._save_persisted_mechanics(path, story_cfg, "fusion")
            got = json.loads(path.read_text())
            segs = got["stories"][0]["segments"]
            self.assertEqual(segs[1]["scene"], MECH)
            self.assertNotIn("scene", segs[0])
            self.assertNotIn("scene", segs[2])
            self.assertEqual(got["stories"][1], self._cfg()["stories"][1],
                             "another story was touched")
            self.assertEqual(SR._PERSISTED, [], "the flag was not cleared")

    def test_nothing_is_written_when_nothing_was_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "niche.config.json"
            path.write_text("{\"stories\": []}")
            before = path.stat().st_mtime_ns
            SR._save_persisted_mechanics(path, {"segments": []}, "fusion")
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_another_processs_edits_to_other_stories_survive(self):
        """The file is re-read at save time, so a concurrent author's changes
        elsewhere in it are not clobbered by this render's stale copy."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "niche.config.json"
            cfg = self._cfg()
            path.write_text(json.dumps(cfg))
            story_cfg = json.loads(json.dumps(cfg["stories"][0]))
            story_cfg["segments"][0]["scene"] = dict(MECH)
            # someone else edits 'other' after we loaded
            cfg["stories"][1]["hook"] = "edited elsewhere"
            path.write_text(json.dumps(cfg))
            SR._PERSISTED.append("fusion")
            SR._save_persisted_mechanics(path, story_cfg, "fusion")
            got = json.loads(path.read_text())
            self.assertEqual(got["stories"][1]["hook"], "edited elsewhere")
            self.assertEqual(got["stories"][0]["segments"][0]["scene"], MECH)


class TheInsightKnowsItsOwnConfigSegment(unittest.TestCase):
    """`story.build` reorders (trend beats to the end) and can drop
    segments, so an index is the wrong key. The pointer is set before the
    shuffle, on the object that survives it."""

    def test_every_built_segment_points_at_a_real_config_dict(self):
        from data_learning import story
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        st_cfg = next((s for s in cfg["stories"]
                       if s["slug"] == "cash-payments-decade-decline"), None)
        if not st_cfg:
            self.skipTest("story not in config")
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(story.charts, "render_story_chart",
                                  return_value=(None, [])):
            st = story.build(st_cfg, cfg, Path(td), ROOT)
        ids = {id(c) for c in st_cfg["segments"]}
        for seg in st.segments:
            self.assertIn(id(seg.insight.seg_cfg), ids,
                          "an insight's seg_cfg is not one of the story's "
                          "own segment dicts")
            self.assertEqual(seg.insight.topic, seg.insight.seg_cfg.get("topic"),
                             "the pointer names a DIFFERENT segment — the "
                             "reorder broke it")


class TheLibraryKeepsWhatWasStarred(unittest.TestCase):

    def test_starred_entries_survive_the_cap(self):
        lib = [{"sig": f"s{i}", "mechanic": f"m{i}", "code": "c",
                "starred": i < 10} for i in range(130)]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lib.json"
            path.write_text(json.dumps(lib))
            with mock.patch.object(VD, "_MECH_LIB", str(path)):
                VD._record_mechanic(_Ins(topic="t"),
                                    {"mechanic": "new", "concept": "c",
                                     "code": "brand new code"})
            got = json.loads(path.read_text())
        self.assertLessEqual(len(got), 120)
        self.assertEqual(sum(1 for m in got if m.get("starred")), 10,
                         "a starred mechanic was evicted")
        self.assertTrue(any(m["mechanic"] == "new" for m in got))
        self.assertTrue(next(m for m in got if m["mechanic"] == "new")["moves"])


class TheWorkflowKeepsItsHandsOffAMechanic(unittest.TestCase):

    def test_the_hands_off_check_counts_a_mechanic_scene(self):
        src = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        i = src.index("kit = sum(1 for sg in st.get('segments', [])")
        block = src[i:i + 400]
        self.assertIn("sg['scene'].get('code')", block,
                      "a story with a brain mechanic still reads as "
                      "undirected and gets re-directed over")


if __name__ == "__main__":
    unittest.main()
