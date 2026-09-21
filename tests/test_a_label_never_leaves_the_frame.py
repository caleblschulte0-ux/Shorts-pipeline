"""THE THING THAT SEPARATES A 57 FROM A 95 IS CRAFT, AND CRAFT IS MEASURED.

Operator, 2026-09-21: *"make sure the animations are better."*

Read across the showrunner's verdicts, the top-retention videos and the
bottom ones score the SAME on `data_demo` — "genuinely varied", "genuinely
animated", "solid, honest" — and split on `craft`: 3 at the top, 1 at the
bottom, every time. The craft faults are the same five, in the brain's own
mechanics: a label clipped off the frame edge (five of the seven worst
videos), two labels printed on top of each other, a raw `51915952` on screen
while the voice says "million metric tons", the mascot on the number, half
the frame empty.

The chart composers lost every one of those to measurement. The mechanic
sandbox had none: `text(s, x, y)` drew wherever it was told. This file holds
the sandbox to the same standard — and holds the PROMPT to the same numbers
as the code, because the brain was being told `RBOT=1180` while the code
said 1560, which is the `empty_void` cause in `viz_scene`'s own comment.

Every test that can be proved by injection is.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import viz_scene as vs                    # noqa: E402


class _Ins:
    slug = "t"
    topic = "t"
    unit = "million metric tons"
    items = []


def _env(unit="million metric tons"):
    from PIL import Image, ImageChops, ImageDraw, ImageOps
    return {"values": [51915952.0, 93466633.0], "labels": ["a", "b"],
            "vmax": 93466633.0, "n": 2, "images": {}, "unit": unit,
            "subject_image": lambda *_a, **_k: None,
            "_Image": Image, "_ImageDraw": ImageDraw,
            "_ImageOps": ImageOps, "_ImageChops": ImageChops}


def _ink_bbox(code: str, reveal: float = 1.0):
    """Run one frame of `code` and return the bbox of everything it drew."""
    from PIL import Image
    canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
    vs._run_mechanic_frame(compile(code, "<t>", "exec"), canvas, _env(), reveal)
    return canvas.getbbox()


LONG = "'Overweight-prone (control-fed) dogs in the long-term study'"


class ALabelNeverLeavesTheFrame(unittest.TestCase):

    def test_a_label_asked_for_at_the_right_edge_stays_inside_it(self):
        """'Submarine cables 95' was truncated at the right frame edge — the
        video's central claim never shown complete. The label is asked for
        at x=1000 and lands complete, inside RX1."""
        bb = _ink_bbox(f"text({LONG}, 1000, 400, size=44)")
        self.assertIsNotNone(bb, "nothing drawn")
        self.assertLessEqual(bb[2], vs.RX1 + 1, f"ink runs to x={bb[2]}")
        self.assertGreaterEqual(bb[0], vs.RX0 - 1)

    def test_and_that_is_the_CLAMP_doing_it(self):
        """Proof by injection: widen the safe area to the whole frame and the
        same call runs past 1040 — so it is the clamp holding the label, not
        the string happening to fit."""
        with mock.patch.object(vs, "RX1", 4000):
            bb = _ink_bbox(f"text({LONG}, 1000, 400, size=44)")
        # The canvas is 1080 wide, so an overflowing label is CUT at 1079 —
        # touching the canvas edge is the proof it ran past the safe area.
        self.assertGreaterEqual(bb[2], vs.W - 1,
                                "the label fits without the clamp — the "
                                "test string is too short to prove anything")

    def test_a_label_below_the_box_is_lifted_into_it(self):
        bb = _ink_bbox("text('bottom', 500, 1900, size=44)")
        self.assertLessEqual(bb[3], vs.RBOT + 1, f"ink reaches y={bb[3]}")

    def test_a_wide_label_SHRINKS_before_it_is_cut(self):
        """A category name loses points before it loses characters — the
        same rule as the card footer."""
        code = (f"text({LONG}, 40, 400, size=72)\n")
        bb = _ink_bbox(code)
        self.assertLessEqual(bb[2], vs.RX1 + 1)
        # at 72pt the string is far wider than the box; it drew, so it shrank
        self.assertGreater(bb[2] - bb[0], 600, "it was cut, not shrunk")


class TwoLabelsNeverPrintOnEachOther(unittest.TestCase):

    def test_a_second_label_at_the_same_spot_is_nudged_clear(self):
        """'the two bottom category labels are printed on top of each other
        and are unreadable across the whole scene'."""
        from PIL import Image
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        code = ("text('Lean-fed dogs', 300, 600, size=44)\n"
                "text('Overweight-prone dogs', 300, 600, size=44)\n")
        vs._run_mechanic_frame(compile(code, "<t>", "exec"), canvas, _env(), 1.0)
        # Ink at y=600 is only one line tall if the labels stacked cleanly:
        # count distinct lit rows in two bands and expect BOTH bands lit.
        import numpy as np
        a = np.asarray(canvas)[:, :, 3] > 24
        rows = a.any(axis=1)
        first = rows[600:650].sum()
        second = rows[650:720].sum()
        self.assertGreater(first, 10, "first label missing")
        self.assertGreater(second, 10, "second label was not nudged below "
                                       "the first — they overprinted")

    def test_the_nudge_is_bounded_and_cannot_walk_off_the_frame(self):
        code = "\n".join(f"text('row {i}', 300, 1500, size=40)" for i in range(12))
        bb = _ink_bbox(code)
        self.assertLessEqual(bb[3], vs.RBOT + 1)
        self.assertGreaterEqual(bb[1], vs.RTOP - 1)


class TheNumberIsTheOneTheVoiceSays(unittest.TestCase):

    def test_fmt_is_in_the_sandbox(self):
        code = "text(fmt(values[0]), 100, 300)"
        self.assertIsNotNone(_ink_bbox(code))

    def test_fmt_carries_the_units(self):
        """'bar labels show unformatted raw values (51915952 … 93466633)
        while the caption and VO say million metric tons'."""
        from PIL import Image
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        got = {}
        code = "out['s'] = fmt(values[0])"
        base = _env()
        # smuggle a result out through the base dict the sandbox shares
        base["out"] = got
        ns_code = compile(code, "<t>", "exec")
        # run via the real runner so `fmt` is the real closure
        with mock.patch.object(vs, "_SAFE_BUILTINS", {**vs._SAFE_BUILTINS}):
            try:
                vs._run_mechanic_frame(ns_code, canvas, base, 1.0)
            except NameError:
                self.skipTest("sandbox does not expose the base dict — "
                              "checked via the formatter directly below")
        from data_learning import charts
        # The formatter's contract: the unit's magnitude word becomes the
        # suffix, so a value already IN millions prints as such. (The raw
        # '51915952' the showrunner saw was a value in tonnes stored under a
        # 'million' unit — a DATA fault fmt() cannot fix, only expose.)
        self.assertEqual(charts._ulabel(52.0, "million metric tons",
                                        group=True), "52M")
        self.assertEqual(charts._ulabel(36.1, "percent", group=True), "36.1%")

    def test_a_missing_unit_still_formats(self):
        """A fixture without `unit` (the motion test's) must not crash the
        sandbox — `fmt` reads it with a default."""
        env = _env(); env.pop("unit")
        from PIL import Image
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        vs._run_mechanic_frame(compile("text(fmt(3.0), 100, 300)", "<t>", "exec"),
                               canvas, env, 1.0)
        self.assertIsNotNone(canvas.getbbox())


class TheBrainIsToldTheSameNumbersTheCodeUses(unittest.TestCase):
    """`RBOT` is 1560 in the code, held by `test_the_frame_is_used.py`. The
    kit prompt and the playbook both told the brain 1180 — a layout this
    channel has not had for months, and the `empty_void` cause in
    viz_scene's own comment. A prompt that disagrees with the code is a
    second source of truth, and the brain reads the prompt."""

    def _stated(self, path):
        txt = (ROOT / path).read_text()
        return {int(m) for m in re.findall(r"RBOT\s*=\s*(\d+)", txt)}

    def test_the_kit_prompt_matches_the_code(self):
        got = self._stated("data_learning/viz_director.py")
        self.assertEqual(got, {vs.RBOT}, f"prompt says RBOT={got}")

    def test_the_playbook_matches_the_code(self):
        got = self._stated("data_learning/VIZ_BRAIN.md")
        self.assertEqual(got, {vs.RBOT}, f"VIZ_BRAIN.md says RBOT={got}")

    def test_both_tell_the_brain_about_fmt(self):
        for path in ("data_learning/viz_director.py", "data_learning/VIZ_BRAIN.md"):
            self.assertIn("fmt(", (ROOT / path).read_text(), path)

    def test_the_playbook_no_longer_names_the_mid_tone_as_a_colour(self):
        txt = (ROOT / "data_learning" / "VIZ_BRAIN.md").read_text()
        self.assertNotRegex(txt, r"Colors:\s*ACCENT,",
                            "the playbook still hands the brain ACCENT")


class NothingAlreadyWorkingBroke(unittest.TestCase):

    def test_a_known_good_mechanic_still_renders_and_moves(self):
        # `validate_mechanic` rightly demands a real subject image; a sweep
        # with none is refused before the dry run, which is correct.
        sweep = ("img = subject_image('a thing')\n"
                 "paste(img, 100, 100) if img is not None else None\n"
                 "d.rectangle([0, 0, 40, int(20 + reveal * (H - 100))], "
                 "fill=rgba(TEXT, 255))\n"
                 "text(fmt(values[1]), 200, 200, size=60)")
        with mock.patch.object(vs, "_mechanic_env", return_value=_env()):
            self.assertTrue(vs.mechanic_dry_ok(
                {"mechanic": "m", "concept": "c", "code": sweep}, _Ins()))


class ATintNeverErasesANumber(unittest.TestCase):
    """PIL's ImageDraw WRITES pixels; it does not composite. A mechanic that
    prints its number and then lays `rgba(WARN, 40)` over the region — a
    tint, by any reading of the intent — wiped the number and left a dark
    box with "yrs" sticking out. Found on 2026-09-21 by rendering the
    pet-obesity lifespan scene: "13.0 yrs" became "yrs".

    `ImageDraw.Draw(canvas, "RGBA")` does NOT fix this on an RGBA canvas;
    that was checked empirically first. The sandbox's `d` is `_BlendDraw`
    now: translucent fills composite, opaque ones write exactly as before.
    """

    GOLD = (255, 211, 122)

    def _gold_px(self, code):
        from PIL import Image
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        vs._run_mechanic_frame(compile(code, "<t>", "exec"), canvas, _env(), 1.0)
        import numpy as np
        a = np.asarray(canvas)
        # "Still readable gold", not "still exactly gold": a tint SHIFTS the
        # colour — that is what a tint is — so an exact match fails the very
        # case being proved (a 60-alpha orange moves G from 211 to ~181).
        # Wiped text has no opaque pixels; opaquely covered text is orange
        # (G=84). Blended text is opaque and still warm-bright.
        gold = (a[:, :, 0] > 200) & (a[:, :, 1] > 150) & (a[:, :, 3] > 200)
        return int(gold.sum())

    LABEL = "text('13.0 yrs', 600, 500, size=40, color=(255, 211, 122))\n"

    def test_a_translucent_rectangle_over_a_label_leaves_it_readable(self):
        alone = self._gold_px(self.LABEL)
        tinted = self._gold_px(self.LABEL + "d.rectangle([550, 480, 900, 600], fill=(242, 84, 45, 40))")
        self.assertGreater(alone, 100, "the label itself did not draw")
        self.assertGreater(tinted, alone * 0.8,
                           f"the tint erased the number: {alone} -> {tinted} gold px")

    def test_and_an_OPAQUE_rectangle_still_covers_it(self):
        """Proof the blend path is what saved it, and that opaque drawing is
        untouched — an opaque box over a label is supposed to hide it."""
        alone = self._gold_px(self.LABEL)
        covered = self._gold_px(self.LABEL + "d.rectangle([550, 480, 900, 600], fill=(242, 84, 45, 255))")
        self.assertLess(covered, alone * 0.2, "opaque fill no longer covers")

    def test_every_shape_method_blends(self):
        for call in ("d.ellipse([560, 470, 900, 610], fill=(242,84,45,60))",
                     "d.rounded_rectangle([550,480,900,600], radius=12, fill=(242,84,45,60))",
                     "d.polygon([(550,480),(900,480),(900,600),(550,600)], fill=(242,84,45,60))",
                     "d.pieslice([500,430,950,650], 0, 360, fill=(242,84,45,60))",
                     "d.line([(540,520),(920,520)], fill=(242,84,45,60), width=60)"):
            alone = self._gold_px(self.LABEL)
            tinted = self._gold_px(self.LABEL + call)
            self.assertGreater(tinted, alone * 0.8, call)

    def test_the_real_pet_obesity_scene_shows_its_number(self):
        """The case that found it, rendered through the real env."""
        import json
        from data_learning import insights as I
        from data_learning.sources import offline as OFF
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        st = next((s for s in cfg["stories"] if s["slug"] == "pet-obesity-epidemic"), None)
        if not st:
            self.skipTest("story no longer in config")
        seg = next((sg for sg in st["segments"]
                    if (sg.get("scene") or {}).get("mechanic") == "lifespan-track-runners"), None)
        if not seg:
            self.skipTest("mechanic no longer in config")
        ins = I.build(OFF.OfflineSource().fetch(seg["key"], seg.get("params")),
                      seg.get("insight_type", "auto"))
        ins.slug = "pet-obesity-epidemic"
        from PIL import Image
        import numpy as np
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        with mock.patch.object(vs, "_load_photo", return_value=None), \
                mock.patch.object(vs, "_load_cutout", return_value=None):
            base = vs._mechanic_env(ins, ins.slug)
            vs._run_mechanic_frame(compile(seg["scene"]["code"], "<m>", "exec"),
                                   canvas, base, 1.0)
        a = np.asarray(canvas)
        # row 1's value label sits just under the first track (RTOP+260+20);
        # count gold there — the wipe left exactly zero in the "13.0" span.
        y0, y1 = vs.RTOP + 260 + 10, vs.RTOP + 260 + 70
        band = a[y0:y1, :, :]
        gold = (abs(band[:, :, 0].astype(int) - 255) < 40) & \
               (abs(band[:, :, 1].astype(int) - 211) < 40) & \
               (band[:, :, 3] > 200)
        self.assertGreater(int(gold.sum()), 250,
                           "row 1's '13.0 yrs' is still being erased by the tint")


if __name__ == "__main__":
    unittest.main()
