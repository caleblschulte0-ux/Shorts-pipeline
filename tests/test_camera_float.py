"""NO CAMERA SHAKE. Anywhere. This file used to require it.

Operator ruling 2026-08-25, verbatim: *"that camera shake that keeps
plaguing our videos — rip it out all the way, it's a cancer, I want no
semblance of the camera shake to exist."*

This test file is inverted on purpose rather than deleted. It was written
to PIN the float in place — "the studio master must apply camera_float",
"the race must call crop_vf" — so deleting it would leave the reintroduction
of shake completely unguarded, and the next session chasing a temporal-gate
failure would rediscover the same bad idea. It now holds the opposite, for
the same reason it existed: this is a thing the repo has been wrong about
twice and must not be wrong about again.

The float existed because the temporal grade measures change between
consecutive frames, so a chart that finishes drawing and holds reads as
duplicate frames. Manufacturing whole-frame drift satisfied the meter
without making a single video better to watch — the operator spotted it
twice through two retunes. What replaces it is real motion the content now
has: struggle reps across the beat (`charts._perf_phase`), an anchor that
tours the ranking instead of parking (`charts._tour_index`), and a chart
race whose empty opening is refused before a slot is spent
(`engines.chart_race` OPEN_AREA_MIN / TRAVEL_MIN).

    python -m unittest tests.test_camera_float -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STUDIO = (ROOT / "data_learning" / "studio_render.py").read_text()
RACE = (ROOT / "engines" / "chart_race.py").read_text()
REPAIR = (ROOT / "scripts" / "scene_repair.py").read_text()

#: Every module that composites or measures a finished frame. If shake comes
#: back, it comes back in one of these.
RENDER_PATHS = [
    "data_learning/studio_render.py",
    "data_learning/longform_render.py",
    "engines/chart_race.py",
    "scripts/scene_repair.py",
    "make_reddit_story.py",
    "make_explainer_stacked.py",
    "make_graph_race.py",
]


class TestTheModuleIsRetired(unittest.TestCase):

    def test_it_announces_its_own_retirement(self):
        from shared import camera_float as cf
        self.assertTrue(cf.RETIRED)
        self.assertEqual(cf.RETIRED_ON, "2026-08-25")

    def test_every_old_entry_point_refuses_loudly(self):
        """A silent no-op would let a caller "work" while quietly meaning
        something else; a raise names the ruling at the call site."""
        from shared import camera_float as cf
        for fn in (cf.px_per_frame, cf.overlay_xy, cf.crop_vf):
            with self.assertRaises(RuntimeError) as ctx:
                fn(1080, 1920)
            self.assertIn("RETIRED", str(ctx.exception))


class TestNoRenderPathImportsIt(unittest.TestCase):

    def test_nothing_imports_camera_float(self):
        for rel in RENDER_PATHS:
            p = ROOT / rel
            if not p.exists():
                continue
            src = p.read_text()
            self.assertNotIn("import camera_float", src, rel)
            self.assertNotIn("camera_float.crop_vf", src, rel)

    def test_the_studio_master_composites_straight_to_captions(self):
        """The float sat between the composite and the subtitle burn-in."""
        self.assertIn("ass='{ass_esc}'[v]", STUDIO.replace('f"', '"'))
        self.assertNotIn("[flt]", STUDIO)

    def test_the_race_encodes_without_a_float_chain(self):
        seg = RACE.split("framerate", 1)[1][:600]
        self.assertNotIn("crop", seg)
        self.assertIn("format=yuv420p", seg)


class TestNobodyReimplementsTheShape(unittest.TestCase):
    """Removing the module is not enough — the shape is four lines of
    ffmpeg and the temptation returns the next time a beat measures short.
    An oscillator driven by TIME on a whole-frame overlay/crop is the
    signature, so look for it directly."""

    #: `sin(<freq>*t)` / `cos(<freq>*t)` inside an ffmpeg expression.
    OSC = re.compile(r"(sin|cos)\s*\(\s*[\d.]+\s*\*\s*t\s*\)")

    def test_no_time_driven_oscillator_in_the_render_paths(self):
        for rel in RENDER_PATHS:
            p = ROOT / rel
            if not p.exists():
                continue
            for i, line in enumerate(p.read_text().splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue          # the headstone comments may say it
                self.assertIsNone(
                    self.OSC.search(line),
                    f"{rel}:{i} looks like a time-driven wobble — the camera "
                    f"shake is retired (2026-08-25): {line.strip()[:90]}")

    def test_the_mascot_hover_is_gone_too(self):
        """The 12px/9px sprite bob was the last survivor of the family, and
        two oscillations in different phases is what read as shaking.

        Matched precisely: the AUDIO stingers a few hundred lines up are
        `0.12*sin(2*PI*294*t)` — a 294 Hz tone, not a wobble — and a loose
        substring flags them, which is how a guard like this gets deleted
        for crying wolf instead of fixed."""
        self.assertNotIn("+12*sin(1.1*t)", STUDIO)
        self.assertNotIn("+9*sin(0.9*t)", STUDIO)
        overlay = [l for l in STUDIO.splitlines()
                   if "overlay=x=" in l or "overlay=y=" in l]
        for line in overlay:
            self.assertIsNone(self.OSC.search(line), line.strip()[:90])


class TestTheProxiesMeasureWhatShips(unittest.TestCase):
    """The temporal proxies used to ADD the float so a short candidate clip
    predicted the long beat. With the float gone they must not add it — a
    proxy that measures motion the master does not have lets a genuinely
    static beat score as lively, which is the original 'fps 1.0 measured,
    1.0 shipped' bug with the sign flipped."""

    def test_the_studio_proxy_composites_at_rest(self):
        seg = STUDIO.split("MEASURE WHAT SHIPS", 1)[1][:1200]
        self.assertNotIn("crop_vf", seg)
        self.assertIn("overlay=0:0:shortest=1,format=yuv420p", seg)

    def test_the_repair_proxy_composites_at_rest(self):
        seg = REPAIR.split("fps_score = 0.5", 1)[1][:1200]
        self.assertNotIn("crop_vf", seg)
        self.assertIn("overlay=0:0:shortest=1,format=yuv420p", seg)


class TestTheReplacementIsRealMotion(unittest.TestCase):
    """The ruling only holds if the content genuinely moves — otherwise the
    next temporal failure re-opens the argument."""

    def test_the_beat_carries_performance_reps(self):
        charts = (ROOT / "data_learning" / "charts.py").read_text()
        self.assertIn("def _perf_phase(", charts)
        body = charts.split("def _bake_host(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_perf_phase(phase)", body)

    def test_the_anchor_tours_instead_of_parking(self):
        charts = (ROOT / "data_learning" / "charts.py").read_text()
        self.assertIn("def _tour_index(", charts)
        build = charts.split("def render_story_build(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_TOUR = f / max(1, frames)", build)

    def test_an_empty_race_opening_is_refused_not_shaken(self):
        self.assertIn("OPEN_AREA_MIN", RACE)
        self.assertIn("TRAVEL_MIN", RACE)


if __name__ == "__main__":
    unittest.main()
