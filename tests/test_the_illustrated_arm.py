"""THE ILLUSTRATED ARM — proven the way the machines are proven.

Operator, 2026-09-23: A/B test the illustrated 2D style on the mascot
channel, "and make sure that we can constantly make something that looks that
good in a wide variety of situations and a wide variety of data."

Held here, for EVERY world in `look.WORLDS` and every illustrated drawing:
  * it renders full-bleed (no transparent pixel: a world, not a chart on a
    ground) through the real `render_build` path;
  * Data is placed in every frame, standing on the drawing;
  * every number printed is one the data has (decoration moves, it never
    adds a quantity);
  * motion is MEASURED with the same still-frame detector the machines are
    held to — no world holds still long enough to be called frozen;
and for the A/B plumbing: the split lives in the registry, the choice is
deterministic, the arm is recorded with the render, the verdict and the
posted log, the judge is never told the arm, and the retro says when the
sample is noise.
"""
from __future__ import annotations

import json
import re
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

from shared import look, style_arms                      # noqa: E402
from data_learning.insights import Insight               # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-23")


def _ins(pairs, unit="count", topic="a story", periods=False):
    return Insight(kind="scene", topic=topic, main_insight="m",
                   items=[DataPoint(label=str(a), value=float(b),
                                    period=(int(a) if periods else None))
                          for a, b in pairs],
                   source=SRC, unit=unit, highlight_label=str(pairs[0][0]))


RANK = _ins([("Shanghai", 49.0), ("Singapore", 39.0), ("Ningbo-Zhoushan", 35.3),
             ("Shenzhen", 30.0), ("Qingdao", 28.8)], unit="million TEU")
TREND = _ins([("1996", 6600), ("2000", 8000), ("2006", 12500), ("2013", 18000),
              ("2019", 24000)], unit="TEU", periods=True)
SHARE = _ins([("By sea", 80.0), ("Everything else", 20.0)], unit="percent")
DUEL = _ins([("Damage & losses", 90.0), ("Prevention & management", 10.0)],
            unit="percent")


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class EveryWorldDrawsEveryShape(unittest.TestCase):
    def _render(self, ins, draw, world, frames=6):
        from data_learning import illustrated as I
        td = Path(tempfile.mkdtemp())
        hosts, texts = [], []
        real_host, real_text = I._host, I.text

        def host(cr, role, phase, insight, kind, cx, foot_y, height):
            hosts.append((cx, foot_y))
            return real_host(cr, role, phase, insight, kind, cx, foot_y, height)

        def text(cr, s, *a, **k):
            texts.append(s)
            return real_text(cr, s, *a, **k)
        with mock.patch.object(I, "_host", host), mock.patch.object(I, "text", text):
            pat, anc = I.render_build(ins, td, "t", frames=frames, full_by=0.8,
                                      draw=draw, world=world)
        return pat, hosts, texts

    def test_all_worlds_all_drawings(self):
        from PIL import Image
        import numpy as np
        from data_learning import illustrated as I
        for world in look.WORLDS:
            for ins, draw in ((RANK, I.draw_columns), (TREND, I.draw_ridge),
                              (SHARE, I.draw_tank), (DUEL, I.draw_columns)):
                with self.subTest(world=world, draw=draw.__name__):
                    pat, hosts, _ = self._render(ins, draw, world)
                    self.assertIsNotNone(pat)
                    a = np.asarray(Image.open(pat % 6).convert("RGBA"))
                    self.assertEqual(int((a[..., 3] < 255).sum()), 0,
                                     "a transparent pixel: not a full-bleed world")
                    self.assertEqual(len(hosts), 6, "Data missing from a frame")
                    for cx, fy in hosts:
                        self.assertTrue(0 < cx < I.W and I.STAGE_TOP < fy <= I.GROUND_Y + 10,
                                        (cx, fy))

    def test_every_number_printed_is_the_datas(self):
        from data_learning import illustrated as I
        allowed_extra = {"25%", "50%", "75%"}
        for ins, draw in ((RANK, I.draw_columns), (TREND, I.draw_ridge),
                          (SHARE, I.draw_tank), (DUEL, I.draw_columns)):
            _, _, texts = self._render(ins, draw, "dusk", frames=12)
            unit = ins.unit
            ok = {I._fmt(p.value, unit) for p in ins.items}
            ok |= {f"{p.value:.0f}%" for p in ins.items}
            ok |= {str(p.label) for p in ins.items}
            last = texts[-(len(texts) // 12):]            # the final frame
            for s in last:
                nums = re.findall(r"\d[\d,.]*", s)
                if not nums or s in ok or s in allowed_extra:
                    continue
                if any(str(p.label) in s for p in ins.items):
                    stem = s
                    for p in ins.items:
                        stem = stem.replace(str(p.label), "")
                    if not re.findall(r"\d", stem) or stem.strip() in ok or any(
                            stem.strip() == f"{v:.0f}%" for v in
                            (100 - p.value for p in ins.items)):
                        continue
                self.assertTrue(any(s == o or s in o for o in ok),
                                f"{draw.__name__} printed {s!r}, not in the data")

    def test_no_world_holds_still_by_the_gates_own_measure(self):
        """The showrunner's temporal pre-gate, exactly: grey, 192px wide,
        `_max_block_diff` over a 12x12 grid, a pair under
        `BLOCK_MOTION_THRESH` is a HELD frame, and a video over 0.45 held is
        blocked before the judge looks. The first previews were: 0.459 and
        0.49, nearly all of it after the data had built. So this measures the
        frames AFTER the build — where only the world and the data's own
        flow can keep it moving — and holds every drawing in every world
        well under the ceiling."""
        from PIL import Image
        from data_learning import illustrated as I
        from scripts import showrunner_review as sr
        shapes = ((RANK, I.draw_columns), (TREND, I.draw_ridge),
                  (SHARE, I.draw_tank), (DUEL, I.draw_columns))
        # every world once (drawings rotated) + every drawing in the default
        # world: each world and each drawing is measured, at a third the cost
        combos = ([(w, shapes[k % 4]) for k, w in enumerate(look.WORLDS)]
                  + [("dusk", sh) for sh in shapes])
        held = {}
        for world, (ins, draw) in combos:
            td = Path(tempfile.mkdtemp())
            pat, _ = I.render_build(ins, td, "t", frames=64, full_by=0.3,
                                    draw=draw, world=world)
            px = [list(Image.open(pat % (f + 1)).convert("L")
                       .resize((192, 341)).getdata()) for f in range(24, 64)]
            dups = [sr._max_block_diff(a, b, 192) < sr.BLOCK_MOTION_THRESH
                    for a, b in zip(px, px[1:])]
            r = sum(dups) / len(dups)
            if r > 0.25:
                held[f"{world}/{draw.__name__}/{ins.items[0].label}"] = round(r, 2)
        self.assertEqual(held, {}, f"held after the build: {held}")

    def test_it_leaves_the_mascots_clock_as_it_found_it(self):
        from data_learning import illustrated as I, viz_scene as vs
        before = getattr(vs, "_BEAT_PHASE", None)
        I.render_build(RANK, Path(tempfile.mkdtemp()), "t", frames=3,
                       draw=I.draw_columns, world="dusk")
        self.assertEqual(getattr(vs, "_BEAT_PHASE", None), before)

    def test_a_claim_without_a_drawing_falls_back(self):
        from data_learning import illustrated as I
        with mock.patch("data_learning.relationships.classify", return_value="other"):
            rel, fn = I.drawing_for(RANK)
        self.assertEqual((rel, fn), ("other", None))


class TheTypeIsTheChannels(unittest.TestCase):
    @unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
    def test_anton_and_inter_resolve(self):
        import shutil
        import subprocess
        from data_learning import illustrated  # noqa: F401 — registers them
        if not shutil.which("fc-match"):
            self.skipTest("fontconfig tools not installed")
        for fam in ("Anton", "Inter"):
            out = subprocess.run(["fc-match", fam], capture_output=True,
                                 text=True).stdout
            self.assertIn(fam, out, f"{fam} does not resolve: {out!r}")

    def test_the_jobs_install_pycairo(self):
        req = (ROOT / "data_learning" / "requirements.txt").read_text()
        self.assertIn("pycairo", req)
        wf = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        self.assertIn("libcairo2-dev", wf)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class OneWorldPerVideo(unittest.TestCase):
    def test_the_story_picks_one_world_for_every_beat(self):
        from types import SimpleNamespace as NS
        from data_learning import illustrated as I
        st = NS(title="Why The Amazon Keeps Shrinking", hook="",
                segments=[NS(topic="Amazon deforestation by year", insight=None),
                          NS(topic="why the Amazon keeps disappearing",
                             insight=NS(topic="cattle pasture share"))])
        w = I.world_for_story(st)
        self.assertIn(w, look.WORLDS)
        self.assertEqual(w, I.world_for_story(st))
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("world=_il.world_for_story(st)", src)

    def test_percentages_that_make_a_whole_fill_the_tank(self):
        from data_learning import illustrated as I
        with mock.patch("data_learning.relationships.classify", return_value="duel"):
            self.assertIs(I.drawing_for(SHARE)[1], I.draw_tank)
            self.assertIs(I.drawing_for(RANK)[1], I.draw_columns)

    def test_the_share_is_full_before_the_beats_halfway(self):
        from data_learning import illustrated as I
        src = (ROOT / "data_learning" / "illustrated.py").read_text()
        body = src[src.index("def draw_tank("):src.index("\nDRAWINGS")]
        self.assertIn("seg(reveal, 0.02, 0.45)", body)


class TheWorldsLiveInTheLook(unittest.TestCase):
    def test_no_hex_in_the_drawing_code(self):
        src = (ROOT / "data_learning" / "illustrated.py").read_text()
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{6}\b", src), [])

    def test_every_world_names_its_tokens(self):
        for name, w in look.WORLDS.items():
            for k in ("sky", "glow", "far", "mid", "near", "form", "rim", "mote"):
                self.assertIn(k, w, f"{name} lacks {k}")

    def test_the_neutral_form_never_looks_like_an_accent(self):
        """One accent per story: every world's supporting marks must stay
        clearly apart from EVERY accent a story can be given."""
        for name, w in look.WORLDS.items():
            for acc, (bright, _dim) in look.ACCENTS.items():
                d = sum((a - b) ** 2 for a, b in zip(w["form"][0], bright)) ** 0.5
                self.assertGreater(d, 90, f"{name} form vs {acc} accent: {d:.0f}")

    def test_the_arm_uses_the_storys_one_accent(self):
        from data_learning import charts
        with mock.patch.object(charts, "HIGHLIGHT", "#ffd37a"):
            from data_learning import illustrated as I
            self.assertEqual(I.accent_pair()[0], (255, 211, 122))


class TheSplitLivesInTheRegistry(unittest.TestCase):
    def test_the_registry_declares_it_and_validates(self):
        from shared import channel_registry as reg
        r = json.loads((ROOT / "config" / "channel_registry.json").read_text())
        arms = r["channels"]["explainer"]["formats"]["data_story"]["style_arms"]
        self.assertIn("current", arms)
        self.assertIn("illustrated", arms)
        self.assertEqual(reg.validate(r), [])

    def test_bad_weights_are_refused(self):
        self.assertTrue(style_arms.problems({"current": 0, "illustrated": 0}))
        self.assertTrue(style_arms.problems({"sepia": 1}))
        self.assertTrue(style_arms.problems({"current": -1}))
        self.assertEqual(style_arms.problems({"current": 1, "illustrated": 0.5}), [])

    def test_the_choice_is_deterministic_and_follows_the_weights(self):
        reg = {"channels": {"explainer": {"formats": {"data_story": {
            "style_arms": {"current": 1, "illustrated": 1}}}}}}
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("EXPLAINER_STYLE", None)
            picks = [style_arms.choose(f"s{i}", reg) for i in range(400)]
            self.assertEqual(picks, [style_arms.choose(f"s{i}", reg) for i in range(400)])
            self.assertTrue(120 < picks.count("illustrated") < 280)
            off = {"channels": {"explainer": {"formats": {"data_story": {
                "style_arms": {"current": 1, "illustrated": 0}}}}}}
            self.assertEqual({style_arms.choose(f"s{i}", off) for i in range(200)},
                             {"current"})
        with mock.patch.dict("os.environ", {"EXPLAINER_STYLE": "illustrated"}):
            self.assertEqual(style_arms.choose("x", off), "illustrated")


class TheArmIsRecordedNeverJudged(unittest.TestCase):
    def test_the_render_writes_it_and_the_loop_records_fallbacks(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_style_arms.sidecar(out_path).write_text", src)
        self.assertIn('_style["fallback_beats"].append(', src)
        self.assertIn('_style["illustrated_beats"].append(i)', src)

    def test_the_posted_log_entry_carries_it(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import post_stories as ps
        with tempfile.TemporaryDirectory() as td:
            mp4 = Path(td) / "s.mp4"
            style_arms.sidecar(mp4).write_text(json.dumps(
                {"style_arm": "illustrated", "illustrated_beats": [0, 2],
                 "fallback_beats": [{"seg": 1}]}))
            f = ps._creative_facts("s", {"segments": []}, mp4, None)
        self.assertEqual(f["style_arm"], "illustrated")
        self.assertEqual((f["illustrated_beats"], f["fallback_beats"]), (2, 1))

    def test_the_ledger_carries_it(self):
        from scripts import showrunner_review as sr
        with tempfile.TemporaryDirectory() as td:
            led = Path(td) / "v.jsonl"
            with mock.patch.object(sr, "LEDGER", led):
                sr.append_ledger("s", {"score": 60, "verdict": "ship",
                                       "style_arm": "illustrated"})
            self.assertEqual(json.loads(led.read_text())["style_arm"], "illustrated")

    def test_the_judge_is_never_told(self):
        src = (ROOT / "scripts" / "showrunner_review.py").read_text()
        body = src[src.index("def review_video("):]
        i = body.index('ctx.pop("style_arm", None)')
        self.assertLess(i, body.index("json.dumps(ctx"))


class TheRetroSaysWhenItIsNoise(unittest.TestCase):
    def test_thin_arms_are_labelled_noise(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_retro as br
        with tempfile.TemporaryDirectory() as td:
            ana = Path(td) / "a.json"
            vids = [{"catalog_id": f"s{i}", "age_hours": 48, "views": 10 + i}
                    for i in range(24)]
            ana.write_text(json.dumps({"videos": vids}))
            log = Path(td) / "p.json"
            log.write_text(json.dumps({"posted": {
                f"s{i}": {"at": f"2026-09-{10 + i % 5:02d}T00:00:00",
                          "style_arm": "illustrated" if i % 2 else "current"}
                for i in range(24)}}))
            with mock.patch.object(br, "ROOT", Path("/")):
                out = br.style_arms_vs_performance(str(ana), posted_log=log)
        self.assertEqual(set(out["arms"]), {"current", "illustrated"})
        self.assertFalse(out["enough_to_judge"])
        self.assertIn("noise", out["caution"])


if __name__ == "__main__":
    unittest.main()
