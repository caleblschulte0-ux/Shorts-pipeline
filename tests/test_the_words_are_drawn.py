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

    def test_half_asleep_beside_her_is_the_two_of_them(self):
        # the 79 film: "the child is shown sleeping alone, without the mother
        # beside her" — the sleeper rule had run before the together rule
        scene = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                 "cast": [{"who": "woman", "pose": "sit", "action": "feed_fire"},
                          {"who": "child", "pose": "lie", "action": "sleep"}],
                 "props": ["brazier", "oil_lamp", "basket"]}
        sents = ["In the smaller house, the woman there sets her spindle down and banks the coals a little lower.",
                 "Her own child is already half asleep beside her, one hand still resting on an unfinished basket.",
                 "She will finish it tomorrow."]
        b = self._beat(scene, sents)
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b])
        t = next(l[0] for l in b.lines if "half asleep" in l[2])
        x = next(x for x in sh if x["start"] <= t < x["end"])
        self.assertEqual(len(x["scene"]["cast"]), 2, x.get("shot"))
        self.assertIn("basket", x["scene"]["props"])

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


class TheSleepersVary(unittest.TestCase):
    """The 79 film's judge: "vary the sleeper scenes (a bed, a mat by a
    wall, a parent and child together) so the second half does not repeat
    one composition"."""

    def _film(self, props_per_beat, say="A man sleeps, and the house is quiet."):
        beats = []
        for props in props_per_beat:
            beats.append({"say": say, "scene": {
                "setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "lie", "action": "sleep"},
                         {"who": "woman", "pose": "sit", "action": "hold"}],
                "props": list(props)}})
        return {"slug": "t", "era": "ancient", "title": "t", "chapters": [{"title": "Night", "beats": beats}]}

    def test_the_kit_draws_a_mat_under_the_sleeper(self):
        from data_learning.doodle import scene as S
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "lie", "action": "sleep"}], "props": ["mat", "oil_lamp"]}
        self.assertEqual(S.validate(sc, "ancient"), [])
        lay = S.layout(sc, 7)
        mat = next(p for p in lay["props"] if p["name"] == "mat")
        self.assertEqual(mat.get("under"), 0, "the mat is not under the sleeper")
        self.assertEqual(lay["collisions"], [])

    def test_sleepers_in_a_row_do_not_share_one_bedding(self):
        from scripts import ori_author as A
        ep = self._film([["oil_lamp"], ["oil_lamp"], ["oil_lamp"], ["oil_lamp"]])
        A.mend_film(ep, log=lambda *_: None)
        beds = [A._bedding_of(b["scene"]) for b in ep["chapters"][0]["beats"]]
        for a, b in zip(beds, beds[1:]):
            self.assertNotEqual(a, b, beds)
        self.assertGreaterEqual(len(set(beds)), 2, beds)

    def test_the_words_keep_their_bed(self):
        from scripts import ori_author as A
        ep = self._film([["bed", "oil_lamp"], ["bed", "oil_lamp"]],
                        say="On a low bed by the wall a man sleeps, and the house is quiet.")
        A.mend_film(ep, log=lambda *_: None)
        self.assertEqual([A._bedding_of(b["scene"]) for b in ep["chapters"][0]["beats"]], ["bed", "bed"])

    def test_nobody_sleeps_across_the_villa_doorway(self):
        from data_learning.doodle import scene as S, settings as ST
        sc = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "child", "pose": "lie", "action": "sleep"},
                       {"who": "woman", "pose": "lie", "action": "sleep"},
                       {"who": "man", "pose": "stand", "action": "idle"}],
              "props": ["mat", "oil_lamp", "brazier"]}
        for seed in range(1, 25):
            lay = S.layout(sc, seed)
            dx = ST.villa_doorway(seed)
            for it in S.spans(lay):
                if it.get("fig") is None or lay["people"][it["fig"]]["pose"] != "lie":
                    continue
                self.assertFalse(min(it["hi"], dx + ST.VILLA_DOOR_HALF) - max(it["lo"], dx - ST.VILLA_DOOR_HALF)
                                 > S.MARGIN,
                                 f"seed {seed}: {it['label']} lies across the doorway at {dx:.0f}")

    def test_the_mat_shows_past_the_sleeper(self):
        from data_learning.doodle import scene as S, people as P
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "lie", "action": "sleep"}], "props": ["mat", "oil_lamp"]}
        lay = S.layout(sc, 3)
        mat = next(p for p in lay["props"] if p["name"] == "mat")
        f = lay["people"][0]
        R = P.R0 * f["s"] * P.WHO["man"]["size"]
        lo, hi = S.figure_extent("lie", R)
        half = S.PROPS["mat"].width * mat["s"] / 2
        self.assertLess(mat["x"] - half, f["x"] + min(lo, -hi) - 0.3 * R)
        self.assertGreater(mat["x"] + half, f["x"] + max(hi, -lo) + 0.3 * R)


class TheEightyThreeNotes(unittest.TestCase):
    """Run 83's six notes, each a rule now."""

    def test_the_words_move_the_hour_forward_only(self):
        from scripts import ori_author as A
        b = {"say": "Soon the square will empty, its voices fading into the evening quiet.",
             "scene": {"setting": "forum", "time": "day", "weather": "clear", "shot": "close", "cast": [], "props": []}}
        self.assertIn("dusk", A.mend_time(b) or "")
        self.assertEqual(b["scene"]["time"], "dusk")
        b["say"] = "Stars have come out, scattered and quiet above the sleeping town."
        A.mend_time(b)
        self.assertEqual(b["scene"]["time"], "night")
        b2 = {"say": "The shepherd banks a small fire at the fold before settling in for the night, as the first stars show.",
              "scene": {"setting": "riverbank", "time": "dusk", "weather": "clear", "shot": "close", "cast": [], "props": []}}
        self.assertIsNone(A.mend_time(b2), "'for the night' and 'the first stars' are said at dusk")
        b3 = {"say": "Carts were loaded before dusk, olives and grain stacked and tied.",
              "scene": {"setting": "olive_grove", "time": "day", "weather": "clear", "shot": "close", "cast": [], "props": []}}
        self.assertIsNone(A.mend_time(b3), "'before dusk' is the day")
        b["say"] = "The evening is warm."
        self.assertIsNone(A.mend_time(b))
        self.assertEqual(b["scene"]["time"], "night", "a dusk word must not turn the night back")

    def test_a_candle_before_the_middle_ages_is_a_lamp_in_the_words(self):
        from scripts import ori_author as A
        b = {"say": "A woman sits alone with her spindle and a single candle. Candles were dear."}
        self.assertTrue(A.mend_say(b, "ancient"))
        self.assertEqual(b["say"], "A woman sits alone with her spindle and a single oil lamp. Oil lamps were dear.")
        b2 = {"say": "a single candle"}
        self.assertIsNone(A.mend_say(b2, "medieval"))

    def test_nobody_sits_on_air(self):
        from scripts import ori_author as A
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "old_woman", "pose": "sit_on", "action": "warm_hands"},
                       {"who": "child", "pose": "lie", "action": "sleep"}], "props": ["oil_lamp", "bed"]}
        self.assertIn("sit_on -> sit", A.mend_scene(sc, "ancient") or "")
        self.assertEqual(sc["cast"][0]["pose"], "sit")
        sc2 = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
               "cast": [{"who": "old_woman", "pose": "sit_on", "action": "warm_hands"}], "props": ["oil_lamp", "bench"]}
        A.mend_scene(sc2, "ancient")
        self.assertEqual(sc2["cast"][0]["pose"], "sit_on")

    def test_a_torch_beside_embers_goes_and_the_lantern_is_in_his_hand(self):
        from scripts import ori_author as A
        b = {"say": "The last person crossing the square carries a small lantern, its light swaying with each step. "
                    "Behind him, the corner fire has burned down to embers, glowing faint and red against the stone.",
             "scene": {"setting": "forum", "time": "night", "weather": "clear", "shot": "wide",
                       "cast": [{"who": "man", "pose": "walk", "action": "carry"},
                                {"who": "elder", "pose": "sit", "action": "warm_hands"}],
                       "props": ["brazier", "column", "torch"]}}
        A.mend_beats([b], "ancient", log=lambda *_: None)
        self.assertEqual(b["scene"]["cast"][0].get("item"), "lantern")
        self.assertEqual(b["scene"].get("fire"), "low")
        self.assertNotIn("torch", b["scene"]["props"], b["scene"])
        self.assertEqual(S.validate(b["scene"], "ancient"), [])

    def test_walkers_start_whole_inside_the_frame(self):
        from data_learning.doodle import scene as S, people as P
        for shot in ("wide", "close"):
            sc = {"setting": "forum", "time": "night", "weather": "clear", "shot": shot,
                  "cast": [{"who": "man", "pose": "walk", "action": "carry"}, {"who": "elder", "pose": "walk", "action": "idle"},
                           {"who": "woman", "pose": "sit", "action": "warm_hands"}], "props": ["brazier", "column"]}
            lay = S.layout(sc, 4)
            for w in lay["walkers"]:
                R = P.R0 * w["s"] * P.WHO[w["who"]]["size"]
                lo, hi = S.figure_extent("walk", R, w["action"], w.get("item"))
                x = S.walker_x(w, 0.0)
                self.assertGreaterEqual(x + lo, 0, (shot, w["who"]))
                self.assertLessEqual(x + hi, S.W, (shot, w["who"]))

    def test_the_dog_comes_in_whole_and_goes_round_the_lamp(self):
        from data_learning.doodle import scene as S, happen as H
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "old_woman", "pose": "sit", "action": "talk"},
                       {"who": "child", "pose": "lie", "action": "sleep"}], "props": ["oil_lamp", "bed"]}
        seen = 0
        for seed in range(1, 30):
            lay = S.layout(sc, seed)
            acts = H.plan(["dog"], sc, lay, seed, 7.0)
            if not acts:
                continue
            a = acts[0]
            seen += 1
            self.assertGreaterEqual(a["x0"], 0, seed)
            self.assertLessEqual(a["x0"], S.W, seed)
            if a.get("behind"):
                continue
            lamp = next(p for p in lay["props"] if p["name"] == "oil_lamp")
            lw = S.PROPS["oil_lamp"].width * lamp["s"] / 2
            lo, hi = sorted((a["x0"], a["x1"]))
            self.assertFalse(lo < lamp["x"] + lw and hi > lamp["x"] - lw, f"seed {seed}: the dog trots across the lamp")
        self.assertGreater(seen, 0)

    def test_a_reclining_drinker_holds_the_cup_up(self):
        from data_learning.doodle import people as P
        sk = P.skeleton("recline", 46.0, 0.0)
        if sk is None:
            self.skipTest("no skeleton()")
        for t in (0.0, 0.7, 1.9, 3.3):
            front, _back = P.hand_targets("drink", sk, 46.0, t, 0.0)
            self.assertLess(front[1], sk["hip"][1] - 0.2 * 46.0, "the cup is down in the lap, out of sight")

    def test_a_respec_keeps_the_hour_and_the_rules(self):
        import json
        from data_learning import ori_storyboard as SB
        fb = {"say": "In the market square, the last sellers pack away their baskets. Soon the square will empty "
                     "into the evening quiet.", "chapter": 0, "beat": 2,
              "scene": {"setting": "forum", "time": "dusk", "weather": "clear", "shot": "close",
                        "cast": [{"who": "man", "pose": "crouch", "action": "gather"}], "props": ["stall", "basket", "brazier"]}}
        brain = {"setting": "forum", "time": "day", "weather": "clear", "shot": "close",
                 "cast": [{"who": "woman", "pose": "stand", "action": "wave"}], "props": ["stall"]}
        did = SB.respec(fb, "ancient", "no packing away", lambda system, prompt: json.dumps(brain))
        self.assertEqual(did, "respecified")
        self.assertEqual(fb["scene"]["time"], "dusk")
        self.assertIn("basket", fb["scene"]["props"], "the author's named-prop rule did not run on the respec")

    def test_the_film_floor_is_his_twenty_minutes(self):
        import json
        cfg = json.load(open(ROOT / "data_learning" / "ori.config.json"))
        self.assertEqual(cfg["min_seconds"], 20 * 60)

    def test_a_couch_for_everyone_who_reclines(self):
        from scripts import ori_author as A
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "recline", "action": "drink", "at": "left"},
                       {"who": "man", "pose": "recline", "action": "drink", "at": "right"}],
              "props": ["oil_lamp", "couch"]}
        self.assertTrue(S.validate(sc, "ancient"), "one couch for two recliners passed")
        A.mend_scene(sc, "ancient")
        self.assertEqual(S.validate(sc, "ancient"), [])
        n_rec = sum(1 for c in sc["cast"] if c["pose"] == "recline")
        self.assertEqual(sc["props"].count("couch"), n_rec)
        self.assertGreaterEqual(n_rec, 1)



@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheSecondEightyThree(unittest.TestCase):
    """Run 92's notes (83 again), each a rule now. Most of them were the
    storyboard brain's doing: a respec that took the words' own subject out
    of the picture, run again every render."""

    def _beat(self, scene, sents):
        b = OS.Beat(chapter=0, index=0, text=" ".join(sents), scene=scene, start=0.0)
        t = 0.0
        for x in sents:
            d = len(x.split()) / 2.3
            b.lines.append((t, t + d, x))
            t += d + 0.7
        b.end = t
        return b

    def _shot_of(self, b, shots, words):
        return next(x for x in shots if any(words in l[2] for l in b.lines if x["start"] <= l[0] < x["end"]))

    def test_a_respec_may_not_take_the_words_subject_out(self):
        from data_learning import ori_storyboard as SB
        say = "Down toward the water, the man who went to the shore is already asleep. A dog rests near the doorway."
        old = {"setting": "seashore", "time": "night", "weather": "clear", "shot": "close",
               "cast": [{"who": "man", "pose": "lie", "action": "sleep"}], "props": ["torch", "dog"]}
        gone_sleeper = dict(old, cast=[{"who": "woman", "pose": "sit", "action": "yawn"}])
        self.assertTrue(SB.keeps_nothing_the_words_name(say, old, gone_sleeper))
        gone_dog = dict(old, props=["torch", "boat"])
        self.assertTrue(SB.keeps_nothing_the_words_name(say, old, gone_dog))
        kept = dict(old, props=["torch", "dog", "boat"], cast=old["cast"] + [{"who": "woman", "pose": "sit", "action": "yawn"}])
        self.assertIsNone(SB.keeps_nothing_the_words_name(say, old, kept))
        four = "Bread and a cup pass between them. A man, a woman, a child and an elder share the meal."
        old4 = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "wide",
                "cast": [{"who": "man", "pose": "sit", "action": "eat"}, {"who": "woman", "pose": "sit", "action": "eat"},
                         {"who": "child", "pose": "sit", "action": "eat"}, {"who": "elder", "pose": "sit", "action": "eat"}],
                "props": ["table", "oil_lamp"]}
        two = dict(old4, cast=old4["cast"][:2])
        self.assertTrue(SB.keeps_nothing_the_words_name(four, old4, two))

    def test_cups_are_filled_is_everyone_at_the_symposium(self):
        scene = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                 "cast": [{"who": "man", "pose": "recline", "action": "drink", "at": "left"},
                          {"who": "man", "pose": "recline", "action": "drink", "at": "right"}],
                 "props": ["oil_lamp", "couch", "couch"]}
        sents = ["Inside, in the room kept for guests, low couches line the walls.",
                 "Cups are filled, and the talk begins slowly, easing into the evening rather than rushing to fill it."]
        b = self._beat(scene, sents)
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b])
        cups = self._shot_of(b, sh, "Cups are filled")
        self.assertEqual(len(cups["scene"]["cast"]), 2, cups["scene"])

    def test_watching_the_sleeper_keeps_the_sleeper_in_shot(self):
        scene = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide",
                 "cast": [{"who": "child", "pose": "lie", "action": "sleep"},
                          {"who": "old_woman", "pose": "sit", "action": "hold"}],
                 "props": ["bed", "oil_lamp"]}
        sents = ["On a low bed near the wall, a child is already asleep, one arm loose over the edge of the blanket.",
                 "An old woman sits close by a moment longer, watching the small steady breathing."]
        b = self._beat(scene, sents)
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b])
        watching = self._shot_of(b, sh, "watching")
        self.assertTrue(any(c.get("pose") == "lie" for c in watching["scene"]["cast"]), watching["scene"])
        self.assertTrue(any(c.get("who") == "old_woman" for c in watching["scene"]["cast"]), watching["scene"])

    def test_one_named_person_gets_no_company(self):
        spec = {"setting": "seashore", "time": "night", "weather": "clear", "shot": "wide",
                "cast": [{"who": "elder", "pose": "sit", "action": "look_up"}], "props": ["boat", "reeds", "basket"]}
        for seed in range(6):
            got = OS.happenings(spec, "ancient", seed,
                                "An old fisherman, too restless to sleep, sits by the water and listens to it.", 7.0)
            self.assertFalse(set(got) & set(OS.NEWCOMERS), got)

    def test_the_passer_is_whole_at_both_ends(self):
        from data_learning.doodle import happen as HP
        spec = {"setting": "forum", "time": "night", "weather": "clear", "shot": "wide",
                "cast": [{"who": "elder", "pose": "sit", "action": "warm_hands"}], "props": ["brazier", "column"]}
        seen = 0
        for seed in range(8):
            lay = S.layout(spec, seed)
            a = HP.build("passer", spec, lay, seed, 7.0)
            if a is None:
                continue
            seen += 1
            for _t, x, _pose, _act, _facing in a["keys"]:
                self.assertGreaterEqual(x - 1.2 * a["R"], 0, seed)
                self.assertLessEqual(x + 1.2 * a["R"], S.W, seed)
            self.assertEqual(a["keys"][-1][2], "stand")
        self.assertGreater(seen, 0)

    def test_walkers_stop_whole_inside_the_far_edge(self):
        spec = {"setting": "forum", "time": "night", "weather": "clear", "shot": "wide",
                "cast": [{"who": "man", "pose": "walk", "action": "carry"},
                         {"who": "woman", "pose": "sit", "action": "warm_hands"}], "props": ["brazier", "column"]}
        lay = S.layout(spec, 4)
        (w,) = lay["walkers"]
        R = P.R0 * w["s"] * P.WHO["man"]["size"]
        lo, hi = S.figure_extent("walk", R, w["action"], w.get("item"))
        x = S.walker_x(w, 60.0)
        self.assertGreaterEqual(x + lo, 0)
        self.assertLessEqual(x + hi, S.W)
        self.assertEqual(S.walker_pose(w, 60.0), "stand")
        self.assertEqual(S.walker_pose(w, 0.5), "walk")

    def test_the_frame_holds_the_lamp_and_spares_the_beams(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "elder", "pose": "lie", "action": "sleep"}], "props": ["brazier", "oil_lamp"]}
        from data_learning.doodle.props import PROPS
        for seed in range(1, 12):
            opts = OS.coverage(spec, "ancient", seed)
            for name, (sp, sd) in opts.items():
                fr = sp.get("frame")
                if not fr:
                    continue
                cx, cy, k = fr
                x0 = min(max(cx * k - S.W / 2, 0.0), (k - 1) * S.W) / k
                y0 = min(max(cy * k - S.H / 2, 0.0), (k - 1) * S.H) / k
                lay = S.layout(sp, sd)
                x1 = x0 + S.W / k
                for q in lay["props"]:
                    if q["name"] in ("oil_lamp", "brazier"):
                        # whole in the window, or wholly out of it (an insert
                        # is of ONE light): never cut by its edge
                        hw = PROPS[q["name"]].width * q["s"] / 2
                        inside = q["x"] - hw >= x0 - 1 and q["x"] + hw <= x1 + 1
                        outside = q["x"] + hw <= x0 + 1 or q["x"] - hw >= x1 - 1
                        self.assertTrue(inside or outside, (seed, name, q["name"], "cut by the window's edge"))
                self.assertFalse(0 < y0 < OS.TOP_BAND, (seed, name, f"the window's top cuts the beams at {y0:.0f}"))


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheThirdEightyThree(unittest.TestCase):
    """Run 93: 83, BLOCKED on two frames that showed the wrong activity —
    the old woman warming her hands stood up beside an identical old woman
    who had just walked in; the spinners lost one to `leave`."""

    def test_nobody_walks_in_as_somebody_s_twin(self):
        from data_learning.doodle import happen as HP
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["oil_lamp", "brazier"]}
        seen = 0
        for seed in range(12):
            lay = S.layout(sp, seed)
            for k in ("arrive", "serve", "feed"):
                a = HP.build(k, sp, lay, seed, 7.0)
                if a is not None:
                    seen += 1
                    self.assertNotEqual(a["who"], "old_woman", (seed, k))
        self.assertGreater(seen, 0)

    def test_the_words_say_she_sits_so_she_stays_sitting_and_alone(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["oil_lamp", "mat"]}
        text = "In another house nearby, an old woman sits up a little longer, warming her hands near a small lamp."
        for seed in range(6):
            got = OS.happenings(spec, "ancient", seed, text, 7.0)
            self.assertNotIn("stretch", got, got)
            self.assertFalse(set(got) & set(OS.NEWCOMERS), got)

    def test_nobody_leaves_while_the_others_keep_spinning(self):
        spec = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "spin"}, {"who": "woman", "pose": "sit", "action": "spin"},
                         {"who": "woman", "pose": "sit", "action": "sew"}], "props": ["oil_lamp"]}
        text = "The others do not stop spinning to listen, but you can tell they are, a small pause in the rhythm."
        for seed in range(6):
            got = OS.happenings(spec, "ancient", seed, text, 7.0)
            self.assertNotIn("leave", got, got)
            self.assertNotIn("stretch", got, got)

    def test_nothing_stands_in_the_pool(self):
        sc = {"setting": "spring", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "crouch", "action": "gather", "item": "basket", "at": "center"}],
              "props": ["amphora", "torch", "rock", "reeds"]}
        lo, hi = S.W * ST.SPRING_X[0], S.W * ST.SPRING_X[1]
        for seed in range(1, 10):
            lay = S.layout(sc, seed)
            for p in lay["props"]:
                if p["layer"] != "back":
                    self.assertFalse(lo < p["x"] < hi, (seed, p["name"], "stands in the pool"))

    def test_a_sleeper_on_a_bed_lies_on_the_mattress(self):
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "man", "pose": "lie", "action": "sleep"}], "props": ["bed", "oil_lamp"]}
        lay = S.layout(sc, 8)
        bed = next(p for p in lay["props"] if p["name"] == "bed")
        f = lay["people"][0]
        self.assertLess(f["y"], bed["y"] - 60 * bed["s"], "the sleeper is drawn through the bed frame")

    def test_a_lamp_keeps_a_head_away_from_a_sleeper(self):
        sc = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "man", "pose": "lie", "action": "sleep"}, {"who": "woman", "pose": "lie", "action": "sleep"}],
              "props": ["brazier", "oil_lamp", "bed"], "fire": "low"}
        from data_learning.doodle.props import PROPS
        for seed in range(1, 10):
            lay = S.layout(sc, seed)
            lamp = next(p for p in lay["props"] if p["name"] == "oil_lamp")
            hw = PROPS["oil_lamp"].width * lamp["s"] / 2
            for f in lay["people"]:
                R = P.R0 * f["s"] * P.WHO[f["who"]]["size"]
                lo, hi = S.figure_extent("lie", R)
                if f["facing"] == "left":
                    lo, hi = -hi, -lo
                gap = max(f["x"] + lo - (lamp["x"] + hw), lamp["x"] - hw - (f["x"] + hi))
                self.assertGreaterEqual(gap, 0.5 * R, (seed, f["who"], "a lamp at a sleeper's head"))

    def test_cups_are_filled_brings_the_krater(self):
        self.assertEqual(OS.named_in("Cups are filled, and the talk begins slowly.", ["oil_lamp", "krater"]), ["krater"])

    def test_a_respec_keeps_the_company_the_words_name(self):
        from data_learning import ori_storyboard as SB
        say = "The talk turns to riddles now, and someone laughs softly at a guess gone wrong."
        old = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "wide",
               "cast": [{"who": "elder", "pose": "sit", "action": "talk"}, {"who": "man", "pose": "recline", "action": "talk"},
                        {"who": "woman", "pose": "sit", "action": "wave"}, {"who": "old_woman", "pose": "sit", "action": "look_up"}],
               "props": ["oil_lamp", "couch"]}
        one = dict(old, cast=old["cast"][:1])
        self.assertTrue(SB.keeps_nothing_the_words_name(say, old, one))
        two = dict(old, cast=old["cast"][:2])
        self.assertIsNone(SB.keeps_nothing_the_words_name(say, old, two))
