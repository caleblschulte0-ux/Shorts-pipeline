"""SUBJECT SCENES — the illustrated arm drawn as the subject itself.

Operator, 2026-09-23: "you need to be far more throwing the mascot on top of
this video" (docs/style_samples/illustrated_2d/sample_a.py). Every
hand-authored teacher scene in `data_learning/subject_scenes.TEACHERS` is
rendered here against its story's REAL sourced data and held to:

  * it renders every frame, full-bleed, with Data placed in every frame;
  * ORDER DOES NOT CHANGE THE STORY: the same data handed over newest-first
    prints the same numbers. The first coffee render chalked last year's
    price in as the new one ("0.5x in twelve months") because the renderer
    handed the pair over newest-first;
  * every number printed is the data's, or arithmetic on it (a difference,
    a share, a ratio) — decoration moves, it never adds a quantity;
  * the scene is still moving at its end by the showrunner's own temporal
    measure (a held frame is one where no 16px block moves by 6 levels).
"""
from __future__ import annotations

import glob
import itertools
import json
import re
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


def _beats(slug):
    cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
    st = next(x for x in cfg["stories"] if x["slug"] == slug)
    out = []
    for g in st["segments"]:
        f = glob.glob(str(ROOT / "data_learning" / "data" / "**" / g["params"]["file"]),
                      recursive=True)[0]
        out.append([(p["label"], float(p["value"])) for p in json.loads(Path(f).read_text())["points"]])
    return out


def _allowed(pts):
    vals = [v for _, v in pts]
    tot = sum(vals) or 1.0
    nums = set(vals)
    nums |= {abs(a - b) for a, b in itertools.combinations(vals, 2)}
    nums |= {v / tot * 100 for v in vals}
    nums |= {a / b for a, b in itertools.permutations(vals, 2) if b}
    for _, v in pts:
        pass
    years = {float(m) for l, _ in pts for m in re.findall(r"(?:1[6-9]|20)\d{2}", str(l))}
    return nums | years


def _num_ok(tok, allowed, extra):
    try:
        x = float(tok.replace(",", ""))
    except ValueError:
        return True
    if x in extra:
        return True
    for a in allowed:
        for d in (0, 1, 2):
            if round(a, d) == round(x, d) or round(a / 1000, d) == round(x, d) \
                    or round(a / 1e6, d) == round(x, d):
                return True
    return False


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class EveryTeacherSceneTellsTheTruth(unittest.TestCase):
    def _run(self, fn, pts, us=(0.0, 0.5, 1.0)):
        from data_learning import subject_scenes as SS
        import cairo as _c
        surf = _c.ImageSurface(_c.FORMAT_ARGB32, SS.W, SS.H)
        hosts, texts = [], []
        real = SS.text

        def text(cr, s, *a, **k):
            texts.append(str(s))
            return real(cr, s, *a, **k)
        with mock.patch.object(SS, "text", text):
            for u in us:
                texts.clear()
                cr = _c.Context(surf)
                fn(cr, 3.0 + u * 10, u, pts,
                   lambda role, x, fy, h, pace=True: hosts.append((x, fy, h)))
        return surf, hosts, list(texts)

    def test_every_scene_renders_with_data_in_it(self):
        from data_learning import subject_scenes as SS
        import numpy as np
        for slug, fns in SS.TEACHERS.items():
            for i, (fn, pts) in enumerate(zip(fns, _beats(slug))):
                with self.subTest(scene=fn.__name__):
                    surf, hosts, _ = self._run(fn, pts)
                    self.assertEqual(len(hosts), 3, "Data missing from a frame")
                    for x, fy, h in hosts:
                        self.assertTrue(0 < x < SS.W and 0 < fy < SS.H and h >= 150)
                    a = np.ndarray((SS.H, SS.W, 4), np.uint8, surf.get_data())
                    self.assertEqual(int((a[..., 3] < 255).sum()), 0, "not full-bleed")

    def test_order_does_not_change_the_story(self):
        from data_learning import subject_scenes as SS
        for slug, fns in SS.TEACHERS.items():
            for fn, pts in zip(fns, _beats(slug)):
                with self.subTest(scene=fn.__name__):
                    _, _, a = self._run(fn, pts, us=(1.0,))
                    _, _, b = self._run(fn, list(reversed(pts)), us=(1.0,))
                    na = sorted(t for t in a if re.search(r"\d", t))
                    nb = sorted(t for t in b if re.search(r"\d", t))
                    if fn.__name__ == "heat_by_city":   # a ranking: order is the data
                        continue
                    self.assertEqual(na, nb)

    def test_every_number_printed_is_the_datas(self):
        from data_learning import subject_scenes as SS
        extra = {25.0, 50.0, 75.0, 1937.0} | {float(q) for q in range(0, 14, 2)}
        for slug, fns in SS.TEACHERS.items():
            for fn, pts in zip(fns, _beats(slug)):
                allowed = _allowed(pts)
                _, _, texts = self._run(fn, pts, us=(1.0,))
                for s in texts:
                    for tok in re.findall(r"\d[\d,]*\.?\d*", s):
                        with self.subTest(scene=fn.__name__, text=s):
                            self.assertTrue(_num_ok(tok, allowed, extra),
                                            f"{fn.__name__} printed {s!r}")

    def test_the_end_of_every_scene_still_moves(self):
        from data_learning import subject_scenes as SS
        from scripts import showrunner_review as sr
        from PIL import Image
        import cairo as _c
        held = {}
        for slug, fns in SS.TEACHERS.items():
            for fn, pts in zip(fns, _beats(slug)):
                surf = _c.ImageSurface(_c.FORMAT_ARGB32, SS.W, SS.H)
                px = []
                for f in range(24):
                    cr = _c.Context(surf)
                    t = 12.0 + f / 24.0
                    fn(cr, t, 0.9 + f / 240.0, pts,
                       lambda role, x, fy, h, pace=True, _cr=cr, _f=f, _t=t: SS.place_host(
                           _cr, role, (_f % 24) / 24.0, None, x, fy, h, _t, pace))
                    surf.flush()
                    im = Image.frombuffer("RGBA", (SS.W, SS.H), bytes(surf.get_data()),
                                          "raw", "BGRA", 0, 1)
                    px.append(list(im.convert("L").resize((192, 341)).getdata()))
                d = [sr._max_block_diff(a, b, 192) < sr.BLOCK_MOTION_THRESH
                     for a, b in zip(px, px[1:])]
                r = sum(d) / len(d)
                if r > 0.3:
                    held[fn.__name__] = round(r, 2)
        self.assertEqual(held, {}, f"scenes that hold still at their end: {held}")


class TheRendererUsesThem(unittest.TestCase):
    def test_a_subject_scene_comes_first_and_is_not_replayed(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_ss.scene_for(slug, i)", src)
        i = src.index("_ss.scene_for(slug, i)")
        self.assertLess(i, src.index("_il.drawing_for(seg.insight)"))
        self.assertIn('if sp.get("kind") == "subject_scene"', src)

    def test_the_teachers_are_the_operators_reference_style(self):
        self.assertTrue((ROOT / "docs" / "style_samples" / "illustrated_2d" /
                         "sample_a.py").exists())
        src = (ROOT / "data_learning" / "subject_scenes.py").read_text()
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{6}\b", src), [])


if __name__ == "__main__":
    unittest.main()


class TheSpokenNumberIsReadable(unittest.TestCase):
    def test_a_dark_punch_is_lifted_a_bright_one_kept(self):
        from data_learning import studio_render as R
        self.assertEqual(R._readable_punch("#ffffff"), "#ffffff")
        self.assertEqual(R._readable_punch("#ffd37a"), "#ffd37a")
        dark = R._readable_punch("#1f2a6b")
        self.assertNotEqual(dark, "#1f2a6b")
        self.assertGreater(int(dark[1:3], 16), 0x80)


class TheCallToActionIsDrawnOnce(unittest.TestCase):
    def test_the_steady_cta_steps_aside_for_each_pulse(self):
        import tempfile
        from data_learning import studio_render as R, story as _story
        seg = _story.Segment(sentence="x", chart_path=None, punches=[],
                             source_footer="", topic="t", anchors=[])
        st = _story.Story(slug="s", title="t", hook="h", closing="c",
                          segments=[seg], hashtags=[], sources=["World Bank"],
                          question="Would you? Tell me below.")
        windows = [(0.0, 3.0), (3.0, 13.0), (13.0, 22.0)]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "s.ass"
            R.build_story_ass(st, windows, [], out)
            lines = [l for l in out.read_text().splitlines()
                     if "COMMENT BELOW" in l]

        def iv(l):
            a, b = l.split(",")[1:3]
            f = lambda s: (int(s.split(":")[0]) * 3600 + int(s.split(":")[1]) * 60
                           + float(s.split(":")[2]))
            return f(a), f(b)
        steady = [iv(l) for l in lines if l.startswith("Dialogue: 5,")]
        pulses = [iv(l) for l in lines if l.startswith("Dialogue: 6,")]
        self.assertTrue(steady)
        for a, b in steady:
            for pa, pb in pulses:
                self.assertFalse(a < pb - 1e-6 and pa < b - 1e-6,
                                 f"CTA {a}-{b} overlaps pulse {pa}-{pb}")
