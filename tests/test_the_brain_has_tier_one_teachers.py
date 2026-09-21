"""THE BRAIN HAS TIER-1 TEACHERS ON THE SHELF, AND A METHOD FOR MAKING MORE.

Operator, 2026-09-21: *"it's not about a specific animation, it's building
a system that can make good per-video animations without me."*

The judge now grades every depiction and the library ranks by that grade
(`test_the_judge_grades_each_depiction.py`). But ranking can only sort what
exists, and on 2026-09-21 the library held zero mechanics the judge had
graded tier 1 — the brain learns by copying, and everything it could copy
was a track with a dog on it. So:

  1. `scripts/seed_exemplars.py` carries four HAND-AUTHORED tier-1
     mechanics, one per data shape the channel ships, each verified by
     RENDERING through the real sandbox and the reviewer's own motion
     detector before it may be seeded. Held here: they validate, they
     render and move on their shapes with no image at all, and the copy on
     the shelf is byte-for-byte the one in the source.
  2. They sit in the library starred, graded 3, `moves: true`, flagged
     `exemplar: true`, and `_mechanic_examples` hands them to the brain
     FIRST.
  3. The kit prompt and the playbook give the brain a METHOD for tier 1
     (name the subject's verb, draw the number as that verb, swap test,
     keep it arriving), not just a definition.
  4. The sandbox bug the exemplars found — `fill_image(color=...)` tinting
     the whole box instead of the subject — stays fixed.
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

from scripts import seed_exemplars as SE                     # noqa: E402
from scripts.score_mechanics import SHAPES, _insight         # noqa: E402
from data_learning import viz_scene as VS                    # noqa: E402
from data_learning import viz_director as VD                 # noqa: E402

LIB = ROOT / "data_learning" / "viz_mechanics.json"


class TheTeachersAreWellFormed(unittest.TestCase):
    def test_there_is_one_per_data_shape(self):
        names = {e["mechanic"] for e in SE.EXEMPLARS}
        self.assertEqual(names, {"subject-strike-grid", "subject-shore-recede",
                                 "subject-drain-share", "subject-true-scale"})

    def test_every_teacher_passes_the_structural_gate(self):
        for e in SE.EXEMPLARS:
            spec = {"mechanic": e["mechanic"], "concept": e["concept"], "code": e["code"]}
            self.assertTrue(VS.validate_mechanic(spec), e["mechanic"])
            self.assertLessEqual(len(e["code"]), 6000, e["mechanic"])

    def test_every_teacher_uses_the_measured_helpers(self):
        """A teacher that prints a raw float or draws a label with
        `d.text` teaches the craft faults the channel just paid for."""
        for e in SE.EXEMPLARS:
            self.assertIn("fmt(", e["code"], e["mechanic"])
            self.assertNotIn("d.text(", e["code"], e["mechanic"])
            self.assertIn("subject_image(", e["code"], e["mechanic"])
            self.assertIn("HIGHLIGHT", e["code"], e["mechanic"])
            self.assertIn("REST", e["code"], e["mechanic"])


class TheTeachersRenderAndMove(unittest.TestCase):
    """Through the REAL sandbox and the REAL motion probe, with no subject
    image at all — the offline worst case — on the shapes each is for."""

    def setUp(self):
        self._photo, self._cut = VS._load_photo, VS._load_cutout
        SE._no_images(VS)

    def tearDown(self):
        VS._load_photo, VS._load_cutout = self._photo, self._cut

    def test_each_teacher_moves_on_its_own_shapes_without_an_image(self):
        for e in SE.EXEMPLARS:
            spec = {"mechanic": e["mechanic"], "concept": e["concept"], "code": e["code"]}
            for shape in e["shapes"]:
                self.assertTrue(VS.mechanic_dry_ok(spec, _insight("t", SHAPES[shape])),
                                f"{e['mechanic']} on {shape}")

    def test_the_teacher_bar_is_above_the_gates_floor(self):
        self.assertGreaterEqual(SE._TEACHER_MOTION, 0.75)
        self.assertGreater(SE._TEACHER_MOTION * 20, VS._MOTION_MIN_POINTS)


class TheTeachersAreOnTheShelf(unittest.TestCase):
    def _lib(self):
        return json.loads(LIB.read_text())

    def test_every_teacher_is_in_the_library_exactly_as_written(self):
        """The shelf copy must be the source copy: editing the script
        without re-seeding would teach one thing and test another."""
        by_sig = {m.get("sig"): m for m in self._lib()}
        for e in SE.EXEMPLARS:
            spec = {"mechanic": e["mechanic"], "concept": e["concept"], "code": e["code"]}
            row = by_sig.get(SE.sig_of(spec))
            self.assertIsNotNone(row, f"{e['mechanic']} not seeded — run "
                                      f"scripts/seed_exemplars.py --write")
            self.assertEqual(row["code"], e["code"])
            self.assertTrue(row.get("exemplar"))
            self.assertTrue(row.get("starred"), "a teacher must never be evicted")
            self.assertIs(row.get("moves"), True)
            self.assertEqual((row.get("grade") or {}).get("bespoke"), 3)
            self.assertEqual((row.get("grade") or {}).get("proves_claim"), 3)

    def test_the_library_stays_a_small_file(self):
        self.assertLess(LIB.stat().st_size, 256 * 1024)

    def test_the_brain_is_shown_the_teachers_first(self):
        names = [m["mechanic"] for m in VD._mechanic_examples(len(SE.EXEMPLARS))]
        self.assertEqual(set(names), {e["mechanic"] for e in SE.EXEMPLARS},
                         f"the first examples handed to the brain are {names}")

    def test_a_judge_graded_3_still_outranks_a_teacher_that_stopped_moving(self):
        """Motion band first, always: a teacher measured static would sink."""
        lib = [{"sig": "t", "mechanic": "teacher", "code": "c", "exemplar": True,
                "starred": True, "moves": False, "grade": {"bespoke": 3}},
               {"sig": "b", "mechanic": "brain-3", "code": "c", "moves": True,
                "grade": {"bespoke": 3}}]
        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "lib.json"; lp.write_text(json.dumps(lib))
            with mock.patch.object(VD, "_MECH_LIB", str(lp)):
                self.assertEqual(VD._mechanic_examples(1)[0]["mechanic"], "brain-3")


class SeedingIsIdempotent(unittest.TestCase):
    def test_seeding_twice_adds_nothing_and_updates_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "lib.json"
            lp.write_text(json.dumps([{"sig": "x", "mechanic": "old", "code": "c"}]))
            SE.seed(SE.EXEMPLARS, lp)
            n1 = len(json.loads(lp.read_text()))
            SE.seed(SE.EXEMPLARS, lp)
            got = json.loads(lp.read_text())
            self.assertEqual(len(got), n1)
            self.assertEqual(n1, 1 + len(SE.EXEMPLARS))
            self.assertEqual(got[0], {"sig": "x", "mechanic": "old", "code": "c"},
                             "a non-exemplar row was touched")

    def test_a_failing_teacher_is_never_seeded(self):
        """`main` refuses to write when verify() reports anything."""
        with mock.patch.object(SE, "verify", return_value=[("m", "s", "i", "why")]), \
                mock.patch.object(SE, "seed") as seed, \
                mock.patch.object(sys, "argv", ["seed_exemplars", "--write"]):
            self.assertEqual(SE.main(), 1)
            seed.assert_not_called()


class TheBrainIsGivenAMethodNotJustADefinition(unittest.TestCase):
    def test_the_kit_prompt_has_the_method_and_the_swap_test(self):
        for s in ("THE METHOD", "swap test", "MOTION THE REVIEWER CAN SEE",
                  "copy their METHOD, not\n  their subject"):
            self.assertIn(s, VD._MECH_API, s)

    def test_the_playbook_has_the_same_method(self):
        txt = (ROOT / "data_learning" / "VIZ_BRAIN.md").read_text()
        for s in ("### The METHOD", "Name the subject's verb", "swap test",
                  "Keep it arriving", "exemplar: true", "Copy their METHOD"):
            self.assertIn(s, txt, s)


class FillImageTintsTheSubjectNotItsBox(unittest.TestCase):
    """Found by rendering `subject-cut-away` on 2026-09-21: a pizza slice
    sitting in a mustard rectangle. The wash covered the whole w x h box and
    the alpha was read AFTER it, so a transparent cut-out came back solid."""

    def test_a_transparent_corner_stays_transparent_under_a_tint(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse([40, 40, 160, 160], fill=(200, 50, 50, 255))
        code = compile("fill_image(images['x'], 1.0, 100, 100, 400, 400, "
                       "color=HIGHLIGHT)", "<m>", "exec")
        base = {"values": [1.0], "labels": ["x"], "vmax": 1.0, "n": 1,
                "images": {"x": img}, "subject_image": lambda n: img, "unit": "",
                "_Image": Image, "_ImageDraw": ImageDraw,
                "_ImageOps": __import__("PIL.ImageOps", fromlist=["x"]),
                "_ImageChops": __import__("PIL.ImageChops", fromlist=["x"])}
        canvas = Image.new("RGBA", (VS.W, VS.H), (0, 0, 0, 0))
        VS._run_mechanic_frame(code, canvas, base, 1.0)
        self.assertEqual(canvas.getpixel((105, 105))[3], 0,
                         "the box corner outside the subject was painted")
        self.assertGreater(canvas.getpixel((300, 300))[3], 200,
                           "the subject itself vanished")


if __name__ == "__main__":
    unittest.main()
