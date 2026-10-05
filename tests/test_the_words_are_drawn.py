"""What the sentence names is in the picture.

The Greek film's judge, three renders running (70, 74, 74): "no boats in the
harbor, no stream, no bread, no couches, a sleeping child drawn as adults
awake ... wax pillar candles and a kettle-grill brazier are out of period".
Every one of those is a rule here, held in code: the kit draws the thing, the
author puts it in the scene when the words name it, and the shot planner
keeps it in the picture for the sentence that names it."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

try:
    import numpy as np
    from data_learning.doodle import scene as S, people as P, settings as ST
    from data_learning.doodle.props import PROPS
    from data_learning import ori_sleep as OS
    import ori_author as A
    HAVE = True
except Exception:                                     # noqa: BLE001
    HAVE = False


def _probe(spec, era, seconds=4.0, seed=3):
    """The showrunner's own cadence probe over a rendered clip."""
    import cairo
    import showrunner_review as SR
    sc = S.Scene(spec, era, seed)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1920, 1080)
    with tempfile.TemporaryDirectory() as td:
        mp4 = Path(td) / "s.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0",
                              "-s", "1920x1080", "-r", "24", "-i", "-", "-c:v", "libx264", "-preset",
                              "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(mp4)], stdin=subprocess.PIPE)
        for i in range(int(seconds * 24)):
            sc.frame(i / 24, surf)
            p.stdin.write(bytes(surf.get_data()))
        p.stdin.close()
        p.wait()
        return SR._temporal_evidence(mp4, Path(td))


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheKitDrawsIt(unittest.TestCase):

    def test_a_greek_dinner_reclines_on_couches(self):
        # "low couches line the walls ... reclining rather than sitting"
        sp = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "recline", "action": "drink"},
                       {"who": "elder", "pose": "recline", "action": "talk"}],
              "props": ["couch", "couch", "oil_lamp"]}
        self.assertEqual(S.validate(sp, "ancient"), [])
        lay = S.layout(sp, 5)
        self.assertEqual(lay["collisions"], [])
        couches = [p for p in lay["props"] if p["name"] == "couch"]
        self.assertEqual(len(couches), 2)
        for c in couches:
            self.assertIsNotNone(c.get("under"), "a couch with nobody on it")
            f = lay["people"][c["under"]]
            self.assertEqual(f["pose"], "recline")
            R = P.R0 * f["s"] * P.WHO[f["who"]]["size"]
            # the body lies along the couch: head end and feet both over it
            self.assertLess(abs(c["x"] - f["x"]), 1.2 * R)
        # the hips sit ON the couch, at the height the couch is drawn to
        sk = P.skeleton("recline", 46.0, 0.0)
        self.assertAlmostEqual(-sk["hip"][1] / 46.0, 1.4, places=2)
        # and a recliner with no couch is refused
        self.assertTrue(S.validate(dict(sp, props=["oil_lamp"]), "ancient"))
        S.Scene(sp, "ancient", 5).frame(1.0)

    def test_a_spindle_is_a_thing_in_a_hand_and_spinning_is_an_act(self):
        self.assertIn("spindle", P.ITEMS)
        self.assertIn("spin", P.ACTIONS)
        self.assertEqual(P.ACTIONS["spin"]["item"], "spindle")
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "sit_on", "action": "spin"}], "props": ["oil_lamp"]}
        self.assertEqual(S.validate(sp, "ancient"), [])
        sc = S.Scene(sp, "ancient", 5)
        a = np.frombuffer(sc.frame(0.0).get_data(), np.uint8).reshape(S.H, S.W, 4)[:, :, :3].astype(int)
        b = np.frombuffer(sc.frame(0.3).get_data(), np.uint8).reshape(S.H, S.W, 4)[:, :, :3].astype(int)
        self.assertGreater(np.abs(a - b).max(), 6, "the spindle does not turn")
        # the author reads it: "spindles turning in their hands" is spinning, not sewing
        self.assertEqual(A.action_for_words("spindles turning in their hands, wool catching the lamp's glow",
                                            {"cast": [{"who": "woman"}]}), "spin")

    def test_a_boat_stands_on_the_sand_and_a_cart_never_crosses_the_bay(self):
        self.assertIn("boat", PROPS)
        self.assertIn("seashore", PROPS["boat"].settings)
        sp = {"setting": "seashore", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "elder", "pose": "sit", "action": "look_up"}], "props": ["boat", "torch", "cart"]}
        self.assertEqual(S.validate(sp, "ancient"), [])
        lay = S.layout(sp, 4)
        gy = lay["ground_y"]
        water_bot = gy - ST.WATER_BAND["sea"][1]
        for p in lay["props"]:
            if p["name"] in ("boat", "cart"):
                self.assertGreater(p["y"], water_bot - 40, f"the {p['name']} stands on the water")
        # the words put it there
        beat = {"say": "Its small harbor lies just as still, boats pulled up on the sand, sails furled.",
                "scene": dict(sp, props=["torch"])}
        self.assertEqual(A.add_named_props(beat, "ancient"), "added the boat the words name")

    def test_the_brazier_is_a_bronze_bowl_on_a_stand_and_a_greek_room_burns_oil(self):
        import inspect
        src = inspect.getsource(PROPS["brazier"].base)
        self.assertIn("bronze", src)
        self.assertNotIn("iron =", src)
        self.assertNotIn("ancient", PROPS["candle"].eras)
        self.assertNotIn("egypt", PROPS["candle"].eras)
        sc = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "sit_on", "action": "sew"}], "props": ["candle", "brazier"]}
        did = A.mend_scene(sc, "ancient")
        self.assertIn("candle -> oil_lamp", did or "")
        self.assertEqual(sc["props"], ["oil_lamp", "brazier"])
        self.assertEqual(S.validate(sc, "ancient"), [])

    def test_a_stream_and_a_spring_are_places_of_their_own_and_alive(self):
        for name in ("stream", "spring"):
            self.assertIn(name, ST.SETTINGS)
            sp = {"setting": name, "time": "night", "weather": "clear", "shot": "close", "cast": [], "props": []}
            self.assertEqual(S.validate(sp, "ancient"), [], name)
            ev = _probe(sp, "ancient")
            self.assertTrue(ev["measured"])
            self.assertLessEqual(ev["duplicate_ratio"], 0.30, (name, ev))
            self.assertLessEqual(ev["max_dup_run"], 45, (name, ev))
        # the words choose them: a stream is not the river, a spring is water, not the season
        self.assertEqual(A.place_class("where the town gives way to open ground, a stream keeps moving"), "stream")
        self.assertEqual(A.place_class("where the ground slopes to a spring, a woman fills a jar with water"),
                         "spring")
        self.assertIsNone(A.place_class("on a spring evening the talk is slow"))
        self.assertEqual(A.place_settings("stream", "ancient"), ["stream"])

    def test_in_a_house_is_indoors(self):
        # "a few streets away, in a smaller house, a woman sits close to a
        # single lamp" was drawn on the rooftops
        self.assertEqual(A.place_class("A few streets away, in a smaller house, a woman sits close to a lamp."),
                         "interior")
        self.assertEqual(A.place_class("In the smaller house, the woman sets her spindle down."), "interior")
        # a house seen from the street, or left, is not
        self.assertNotEqual(A.place_class("Outside the house the street is dark and the stalls shuttered."),
                            "interior")
        self.assertEqual(A.place_class("The last person crossing the square carries a lantern past the houses."),
                         "city")


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheShotKeepsWhatTheSentenceNames(unittest.TestCase):

    def _beat(self, scene, sents):
        b = OS.Beat(chapter=0, index=0, text=" ".join(sents), scene=scene, start=0.0)
        t = 0.0
        for x in sents:
            d = len(x.split()) / 2.3
            b.lines.append((t, t + d, x))
            t += d + 0.7
        b.end = t
        return b

    def _text_of(self, b, x):
        return " ".join(l[2] for l in b.lines if x["start"] <= l[0] < x["end"])

    def test_the_meal_keeps_its_table_and_both_people(self):
        scene = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
                 "cast": [{"who": "man", "pose": "sit_on", "action": "eat"},
                          {"who": "woman", "pose": "sit_on", "action": "drink"}],
                 "props": ["oil_lamp", "table"]}
        sents = ["The house is quiet now.",
                 "At the table, a man breaks bread and passes it across, and a woman lifts a cup of watered wine.",
                 "Olives sit in a small bowl between them.",
                 "The lamp burns low and steady, and neither of them is in any hurry to finish."]
        b = self._beat(scene, sents)
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b])
        # the long sentence is two clauses, so two shots: his, then hers —
        # each at the table, each the person the clause names
        t_meal = next(l[0] for l in b.lines if "breaks bread" in l[2])
        his = next(x for x in sh if x["start"] <= t_meal < x["end"])
        self.assertEqual([c["who"] for c in his["scene"]["cast"]], ["man"], his.get("shot"))
        self.assertIn("table", his["scene"]["props"])
        hers = sh[sh.index(his) + 1]
        self.assertEqual([c["who"] for c in hers["scene"]["cast"]], ["woman"], hers.get("shot"))
        self.assertIn("table", hers["scene"]["props"])
        lamp = next(x for x in sh if "lamp burns" in self._text_of(b, x))
        self.assertTrue(lamp["scene"]["cast"], "a lamp with nobody at it")

    def test_a_sleeping_child_is_the_child_asleep(self):
        scene = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide",
                 "cast": [{"who": "child", "pose": "lie", "action": "sleep"},
                          {"who": "old_woman", "pose": "sit_on", "action": "hold"}],
                 "props": ["bed", "oil_lamp"]}
        sents = ["On a low bed near the wall, a child is already asleep, one arm loose over the edge of the blanket.",
                 "An old woman sits close by a moment longer, watching the small steady breathing.",
                 "Then she covers the child more warmly and rises to find her own rest."]
        b = self._beat(scene, sents)
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b])
        asleep = next(x for x in sh if "already asleep" in self._text_of(b, x))
        self.assertTrue(any(c.get("pose") == "lie" for c in asleep["scene"]["cast"]), asleep.get("shot"))
        self.assertIn("bed", asleep["scene"]["props"])

    def test_a_repeated_angle_beats_a_wrong_picture(self):
        opts = {"two": ({"cast": [{"who": "man"}, {"who": "woman"}], "props": ["oil_lamp", "table"]}, 1),
                "single:0": ({"cast": [{"who": "man"}], "props": ["oil_lamp"]}, 2),
                "insert": ({"cast": [{"who": "man"}], "props": ["oil_lamp"]}, 3)}
        got = OS._choose(opts, "At the table a man breaks bread and a woman lifts a cup.", "two", False, ["two"],
                         needs=["table"])
        self.assertEqual(got, "two")

    def test_the_words_say_couches_and_the_author_reclines_them(self):
        beat = {"say": "Inside, in the room kept for guests, low couches line the walls. The men settle onto them "
                       "the way custom asks, reclining rather than sitting upright.",
                "scene": {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                          "cast": [{"who": "man", "pose": "sit_on", "action": "drink"},
                                   {"who": "man", "pose": "sit_on", "action": "talk"}],
                          "props": ["oil_lamp"]}}
        did = A.mend_recline(beat, "ancient")
        self.assertTrue(did, "nobody reclined")
        sc = beat["scene"]
        self.assertTrue(any(c["pose"] == "recline" for c in sc["cast"]))
        self.assertIn("couch", sc["props"])
        self.assertEqual(S.validate(sc, "ancient"), [])
        # and it holds: a second pass changes nothing
        self.assertIsNone(A.mend_recline(beat, "ancient"))

    def test_the_judge_is_told_the_sentence_spoken_at_that_moment(self):
        # the 83 film: "a man breaks bread" was held against the shot of the
        # passage's third sentence, because the judge was given each
        # passage's FIRST line at every moment it looked
        b = OS.Beat(chapter=0, index=0, text="First sentence here. Second sentence here. Third one.", scene={},
                    start=0.0)
        b.lines = [(0.0, 4.0, "First sentence here."), (4.7, 8.7, "Second sentence here."), (9.4, 12.0, "Third one.")]
        b.end = 13.9
        lines = OS.judged_lines([b], [{"t": 0.0, "label": "c"}], 13.9)
        # 55% of 13.9 s is 7.6 s: the second sentence
        self.assertEqual(lines["seg0:mid"], "Second sentence here.")
        self.assertEqual(lines["seg0:end"], "Third one.")
        self.assertEqual(lines["seg0:start"], "First sentence here.")

    def test_the_water_sparkle_never_crosses_a_face(self):
        # the 83 film: "sea and spring sparkle dots are painted on top of the
        # figures' heads" — on the woman a happening had just walked to the pool
        sp = {"setting": "spring", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "crouch", "action": "gather"}], "props": ["amphora", "torch"],
              "happen": ["arrive"], "happen_s": 7.0}
        sc = S.Scene(sp, "ancient", 4)
        self.assertEqual([a["kind"] for a in sc.acts], ["arrive"])
        a = sc.acts[0]
        t = a["keys"][-1][0] - 1.0 if a["keys"][-1][0] < 7 else 6.5
        holes = sc._figure_holes(t)
        from data_learning.doodle import happen as HP
        x, *_ = HP._state(a, t)
        self.assertTrue(any(lo <= x <= hi for lo, hi, _top, _bot in holes), "the newcomer has no hole in the glints")

    def test_several_sellers_are_several(self):
        beat = {"say": "In the market square, the last sellers pack away their baskets, and the stalls stand empty.",
                "scene": {"setting": "forum", "time": "dusk", "weather": "clear", "shot": "close",
                          "cast": [{"who": "man", "pose": "crouch", "action": "gather"}],
                          "props": ["stall", "basket", "brazier"]}}
        did = A.mend_plural(beat, "ancient")
        self.assertIn("second person", did or "")
        self.assertEqual(len(beat["scene"]["cast"]), 2)
        self.assertEqual(S.validate(beat["scene"], "ancient"), [])

    def test_the_shelf_scripts_stand_mended_and_valid(self):
        for p in sorted((ROOT / "data_learning" / "ori_episodes").glob("*.json")):
            ep = json.loads(p.read_text())
            for c in ep["chapters"]:
                for b in c["beats"]:
                    self.assertEqual(S.validate(b["scene"], ep["era"]), [], p.name)
                    names = [q if isinstance(q, str) else q.get("name") for q in b["scene"].get("props") or []]
                    self.assertNotIn("candle", names if ep["era"] in ("ancient", "egypt") else [], p.name)


if __name__ == "__main__":
    unittest.main()
