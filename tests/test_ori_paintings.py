"""Real paintings in the sleep films, with the camera dead still.

The operator, 2026-10-01, on the Greek film ("3/10 AI slop"): "throw in some"
real paintings, and of his ruling against camera movement: "Keep the camera
dead still". These tests hold what a painting must be to be shown — public
domain, of the film's era (and place), after dark, calm, and about what the
passage says — and that it is drawn still, moving only by a candle's real
flicker, and credited. No network: the museums are stubbed.
"""
from __future__ import annotations

import inspect
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from data_learning import ori_paintings as P     # noqa: E402


def _p(id_, title, date="1648", made="", kind="print"):
    return dict(source="The Metropolitan Museum of Art", id=id_, title=title, artist="A. Painter", date=date,
                kind=kind, made=made, license="public domain", image_url="http://x/y.jpg", page="")


class WhatMayBeShown(unittest.TestCase):
    def test_the_era_the_place_and_the_hour(self):
        sym = _p("met:1", "Plato's symposium: Socrates and his companions seated around a table")
        self.assertTrue(P.era_ok(sym, "ancient"))
        self.assertFalse(P.era_ok(_p("met:2", "Greek Lovers", "1825"), "ancient"), "a modern Greek scene")
        self.assertFalse(P.era_ok(_p("aic:3", "York Harbor, Coast of Maine", "1877"), "ancient"))
        # a Victorian film is London: the right year in France is not enough
        self.assertFalse(P.era_ok(_p("aic:4", "Street in Moret", "1888", made="French"), "victorian"))
        self.assertTrue(P.era_ok(_p("aic:5", "The Thames at Night", "1880", made="English"), "victorian"))
        # after dark: a sunlit landscape contradicts a night passage
        self.assertTrue(P.after_dark(sym))
        self.assertTrue(P.after_dark(_p("aic:6", "Moonrise", "1891")))
        self.assertFalse(P.after_dark(_p("aic:7", "A Sunday on La Grande Jatte", "1884")))
        # calm and for everyone
        self.assertFalse(P.suitable(_p("aic:8", "Venus and Adonis")))
        self.assertFalse(P.suitable(_p("aic:9", "The Battle of Issus")))
        self.assertTrue(P.suitable(sym))

    def test_a_painting_is_chosen_only_for_what_a_passage_is_about(self):
        sym = _p("met:1", "Plato's symposium: Socrates and his companions seated around a table")
        nude = _p("met:2", "Nude at a symposium")
        day = _p("aic:3", "Harbor at Noon", "1640")
        asked = []

        def search(q, n=10):
            asked.append(q)
            return [sym, nude, day]
        say = "The men recline on couches along the walls, and a lamp burns low as the talk goes on. " * 3
        ep = {"era": "ancient", "chapters": [
            {"title": "Evening Falls", "beats": [{"say": "The sun goes down over the hills. " * 5}] * 3},
            {"title": "The Men's Symposium", "beats": [{"say": say}, {"say": say}]},
            {"title": "The Harbour", "beats": [{"say": "Boats rock at the harbour wall. " * 5}]}]}
        n = P.pick_for_film(ep, search_fn=search, log=lambda *_: None)
        self.assertEqual(n, 1)
        self.assertEqual(ep["chapters"][1]["beats"][0]["painting"]["id"], "met:1")
        # the film's opening keeps its drawn establishing shot; nothing else
        # was given a painting that does not match, and none is used twice
        self.assertNotIn("painting", ep["chapters"][0]["beats"][0])
        self.assertTrue(all("painting" not in b for b in ep["chapters"][2]["beats"]))
        self.assertLessEqual(len(asked), 2 * 4 * 3, "a search per passage again")
        # credited, and the description stops saying every picture is drawn
        self.assertIn("Plato's symposium", P.credits(ep))
        import post_ori
        d = post_ori.description(dict(ep, title="T | Cozy History for Sleep", description="x", tags=[]),
                                 {"chapters": []})
        self.assertIn("Paintings:", d)
        self.assertIn(post_ori.DRAWN_WITH_PAINTINGS, d)
        self.assertNotIn(post_ori.DRAWN, d)


class ThePaintingIsHeldStill(unittest.TestCase):
    def test_still_by_candlelight_and_alive_to_the_gate(self):
        import cairo
        import numpy as np
        from PIL import Image
        import showrunner_review as SR
        with tempfile.TemporaryDirectory() as td:
            img = Path(td) / "p.jpg"
            rng = np.random.default_rng(3)
            a = (rng.random((900, 1300, 3)) * 60 + np.linspace(60, 190, 1300)[None, :, None]).astype("uint8")
            Image.fromarray(a).save(img, quality=90)
            sc = P.PaintingScene(img, 7)
            surf = cairo.ImageSurface(cairo.FORMAT_RGB24, P.W, P.H)
            mp4 = Path(td) / "p.mp4"
            pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0",
                                   "-s", f"{P.W}x{P.H}", "-r", "24", "-i", "-", "-c:v", "libx264", "-preset",
                                   "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(mp4)], stdin=subprocess.PIPE)
            for i in range(96):
                sc.frame(i / 24, surf)
                pr.stdin.write(bytes(surf.get_data()))
            pr.stdin.close()
            pr.wait()
            ev = SR._temporal_evidence(mp4, Path(td))
        self.assertLess(ev["max_dup_run"], 45, ev)
        self.assertLessEqual(ev["duplicate_ratio"], 0.6, ev)
        # still: nothing in the drawing scales, translates or crops by time
        src = inspect.getsource(P.PaintingScene.frame)
        for banned in ("translate", "scale(", "zoom", "pan"):
            self.assertNotIn(banned, src, f"the camera moves ({banned})")

    def test_a_passage_with_a_painting_opens_on_it(self):
        from data_learning import ori_sleep as OS
        scene = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
                 "cast": [{"who": "man", "pose": "sit", "action": "eat"}], "props": ["table", "oil_lamp"]}
        b = OS.Beat(chapter=0, index=4, text="x", scene=scene, start=10.0, end=50.0)
        b.lines = [(10.0 + k * 8, 17.0 + k * 8, f"S{k}.") for k in range(5)]
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b], {4: Path("/tmp/x.jpg")})
        self.assertTrue(sh[0].get("painting"))
        self.assertEqual(sh[0]["start"], 10.0)
        self.assertLessEqual(sh[0]["end"] - sh[0]["start"], OS.SHOT_MAX + 8)
        self.assertTrue(all(not x.get("painting") for x in sh[1:]))
        self.assertEqual(sh[-1]["end"], 50.0)


if __name__ == "__main__":
    unittest.main()
