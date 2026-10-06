"""What the sentence names is in the picture.

The Greek film's judge, three renders running (70, 74, 74): "no boats in the
harbor, no stream, no bread, no couches, a sleeping child drawn as adults
awake ... wax pillar candles and a kettle-grill brazier are out of period".
Every one of those is a rule here, held in code: the kit draws the thing, the
author puts it in the scene when the words name it, and the shot planner
keeps it in the picture for the sentence that names it."""
from __future__ import annotations

import inspect
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


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheEightyTwo(unittest.TestCase):
    """Run 94: 82, SHIP. A gatherer stood up out of her gathering, a bare
    wall behind a zoomed-in sitter, a dissolve that ghosted two sleepers."""

    def test_nobody_at_work_stands_up_out_of_it(self):
        from data_learning.doodle import happen as HP
        sp = {"setting": "olive_grove", "time": "dusk", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "crouch", "action": "gather", "item": "basket"}], "props": ["tree", "basket"]}
        for seed in range(6):
            self.assertIsNone(HP.build("stretch", sp, S.layout(sp, seed), seed, 7.0))
        sp2 = dict(sp, cast=[{"who": "woman", "pose": "sit", "action": "talk"}])
        self.assertIsNotNone(HP.build("stretch", sp2, S.layout(sp2, 1), 1, 7.0))

    def test_a_bare_room_gets_a_piece_of_furniture(self):
        from scripts import ori_author as A
        b = {"say": "In another house nearby, an old woman sits up a little longer, warming her hands near a small lamp.",
             "scene": {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                       "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"},
                                {"who": "child", "pose": "lie", "action": "sleep"}], "props": ["oil_lamp", "mat"]}}
        did = A.mend_furnish(b, "ancient", turn=3)
        self.assertTrue(did, b["scene"]["props"])
        self.assertTrue(any(n in A.FURNISHINGS for n in b["scene"]["props"]), b["scene"]["props"])
        self.assertEqual(S.validate(b["scene"], "ancient"), [])

    def test_the_dissolve_is_short_and_a_room_is_framed_loosely(self):
        self.assertLessEqual(OS.XFADE, 0.4)
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["oil_lamp", "table"]}
        for seed in range(1, 8):
            for name, (sp, _sd) in OS.coverage(spec, "ancient", seed).items():
                if name.startswith("single:") and sp.get("frame"):
                    self.assertLessEqual(sp["frame"][2], OS.SINGLE_ZOOM_INTERIOR + 1e-9, (seed, name))

    def test_a_single_keeps_the_room_but_not_another_s_bed(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"},
                         {"who": "child", "pose": "lie", "action": "sleep"}], "props": ["oil_lamp", "mat", "barrel", "basket"]}
        opts = OS.coverage(spec, "ancient", 3)
        self.assertIn("barrel", opts["single:0"][0]["props"])
        self.assertNotIn("mat", opts["single:0"][0]["props"])
        self.assertIn("mat", opts["single:1"][0]["props"])

    def test_the_fire_does_not_stand_in_the_villa_doorway(self):
        sc = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "sit", "action": "sew"}], "props": ["oil_lamp", "table", "brazier"]}
        for seed in range(1, 16):
            lay = S.layout(sc, seed)
            dx = ST.villa_doorway(seed)
            fire = next(p for p in lay["props"] if p["name"] == "brazier")
            hw = S.PROPS["brazier"].width * fire["s"] / 2
            self.assertFalse(min(fire["x"] + hw, dx + ST.VILLA_DOOR_HALF) - max(fire["x"] - hw, dx - ST.VILLA_DOOR_HALF) > S.MARGIN,
                             f"seed {seed}: the brazier stands in the doorway")



@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheSeventyEight(unittest.TestCase):
    """Run 95: 78, BLOCKED — the embers beat drawn as a square full of
    walkers, spinners with no visible spindle, floor-sitters "floating",
    a barrel with the water showing through, one house in every chapter,
    a passer through the goats."""

    def test_the_embers_get_an_insert_even_where_the_only_person_walks(self):
        spec = {"setting": "forum", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "walk", "action": "carry", "item": "lantern"}],
                "props": ["brazier", "column"], "fire": "low"}
        opts = OS.coverage(spec, "ancient", 4)
        self.assertIn("insert", opts)
        ins = opts["insert"][0]
        self.assertEqual(ins["cast"][0]["pose"], "stand")
        self.assertIn("frame", ins)
        b = TheSecondEightyThree._beat(self, spec, ["The last person crossing the square carries a small lantern.",
                                                    "Behind him, the corner fire has burned down to embers, glowing faint against the stone."])
        sh = OS.shots({"slug": "t", "era": "ancient"}, [b])
        embers = TheSecondEightyThree._shot_of(self, b, sh, "embers")
        self.assertEqual(embers["shot"], "insert", embers["shot"])

    def test_a_floor_sitter_indoors_sits_on_a_cushion(self):
        import numpy as np
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["oil_lamp", "table"]}
        sc = S.Scene(sp, "ancient", 2)
        self.assertTrue(sc.cushions)
        out = {"setting": "forum", "time": "night", "weather": "clear", "shot": "close",
               "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["brazier"]}
        self.assertFalse(S.Scene(out, "ancient", 2).cushions)
        self.assertGreaterEqual(P.SPINDLE_WHORL, 0.45)

    def test_the_water_does_not_show_through_a_barrel(self):
        import numpy as np
        sp = {"setting": "seashore", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "elder", "pose": "sit", "action": "look_up"}], "props": ["barrel", "boat"]}
        sc = S.Scene(sp, "ancient", 3)
        bar = next(p for p in sc.lay["props"] if p["name"] == "barrel")
        xs, ys = int(bar["x"]), int(bar["y"] - 70 * bar["s"])
        seen = set()
        for k in range(40):
            surf = sc.frame(k / 10.0)
            buf = np.ndarray(shape=(S.H, S.W, 4), dtype=np.uint8, buffer=surf.get_data())
            seen.add(tuple(int(v) for v in buf[ys, xs, :3]))
        self.assertLessEqual(len(seen), 2, f"the barrel's face changes colour with the water: {sorted(seen)[:4]}")

    def test_no_passer_through_the_herd(self):
        from data_learning.doodle import happen as HP
        pen = {"setting": "olive_grove", "time": "night", "weather": "clear", "shot": "close",
               "cast": [{"who": "man", "pose": "stand", "action": "hold", "item": "torch"}], "props": ["fence", "campfire", "goat"]}
        self.assertFalse(HP.fits("passer", pen))
        self.assertTrue(HP.fits("passer", dict(pen, props=["fence", "campfire"])))

    def test_the_rooms_are_not_one_room(self):
        import numpy as np
        walls = set()
        for seed in range(3):
            sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide", "cast": [], "props": ["oil_lamp", "table"]}
            surf = S.Scene(sp, "ancient", seed).still
            buf = np.ndarray(shape=(S.H, S.W, 4), dtype=np.uint8, buffer=surf.get_data())
            walls.add(tuple(int(v) for v in buf[500, 960, :3]))
        self.assertGreaterEqual(len(walls), 2, walls)


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheThirdBlock(unittest.TestCase):
    """Run 96: 83, BLOCKED again on the embers beat — the insert of the man
    at the banked brazier had a cat crossing the far lane through the bowl
    and a lantern flame in his hand, and read as "a brazier in full flame
    with an animal standing in the fire"."""

    def test_nothing_crosses_the_back_lane_of_a_framed_close_up(self):
        from data_learning.doodle import happen as HP
        spec = {"setting": "forum", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "stand", "action": "idle"}], "props": ["brazier"], "fire": "low",
                "frame": [683.2, 670.9, 2.0]}
        for seed in range(8):
            lay = S.layout(spec, seed)
            acts = HP.plan(["passer", "cat", "dog"], spec, lay, seed, 7.0)
            self.assertFalse(any(a.get("behind") for a in acts), [a["kind"] for a in acts])
            got = OS.happenings(spec, "ancient", seed, "Behind him, the corner fire has burned down to embers.", 7.0)
            self.assertNotIn("passer", got)

    def test_the_embers_insert_is_tight_and_alone(self):
        spec = {"setting": "forum", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "walk", "action": "carry", "item": "lantern"}],
                "props": ["brazier"], "fire": "low"}
        opts = OS.coverage(spec, "ancient", 4)
        ins = opts["insert"][0]
        self.assertGreater(ins["frame"][2], 1.6, "the rooftops stay in a loose insert")
        self.assertEqual(len(ins["cast"]), 1)
        for seed in range(6):
            got = OS.happenings(ins, "ancient", seed, "Behind him, the corner fire has burned down to embers.", 7.0)
            self.assertFalse(set(got) & set(OS.NEWCOMERS), got)

    def test_a_drinker_keeps_the_cup_up_whatever_the_pose(self):
        for pose in ("sit", "sit_on", "recline", "stand"):
            sk = P.skeleton(pose, 46.0, 0.0)
            for t in (0.0, 0.7, 1.9, 3.3):
                front, _ = P.hand_targets("drink", sk, 46.0, t, 0.0)
                self.assertLess(front[1], sk["hip"][1] - 0.2 * 46.0, (pose, t))

    def test_the_house_wall_has_something_on_it_at_eye_height(self):
        import numpy as np
        for seed in range(3):
            sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide", "cast": [], "props": ["oil_lamp", "table"]}
            surf = S.Scene(sp, "ancient", seed).still
            buf = np.ndarray(shape=(S.H, S.W, 4), dtype=np.uint8, buffer=surf.get_data())
            x = int(ST.house_hanging_x(seed))
            on = tuple(int(v) for v in buf[600, x, :3])
            off = tuple(int(v) for v in buf[600, (x + 400) % S.W if x < S.W / 2 else x - 400, :3])
            self.assertNotEqual(on, off, f"seed {seed}: nothing hangs on the wall at {x}")


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheEightyThreeShip(unittest.TestCase):
    """Run 97: 83, SHIP — the spinners' sentence was cut at a comma and its
    second half given a single ("only one woman appears"); a man left the
    couch while "cups are filled, and the talk begins"; the old woman sat
    at the slot the wide shot gave her, hands nowhere near the lamp, and
    "does not read as old"; the storyteller's close-up dropped the sleeping
    child; the forum close-up read as a rooftop; the shepherd frowned."""

    def _beats(self, ep):
        beats, t, i = [], 0.0, 0
        for ci, ch in enumerate(ep["chapters"]):
            for bt in ch["beats"]:
                b = OS.Beat(chapter=ci, index=i, text=bt["say"], scene=bt["scene"], start=t)
                for x in OS.sentences(bt["say"]):
                    d = len(x.split()) / 2.3
                    b.lines.append((t, t + d, x))
                    t += d + 0.7
                b.end = t
                t += 1.9
                beats.append(b)
                i += 1
        return beats

    def test_a_clause_cut_from_a_sentence_is_chosen_by_the_whole_sentence(self):
        scene = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "wide",
                 "cast": [{"who": "old_woman", "pose": "sit", "action": "spin"},
                          {"who": "woman", "pose": "sit", "action": "spin"},
                          {"who": "woman", "pose": "sit", "action": "sew"}],
                 "props": ["oil_lamp", "amphora", "bench"]}
        say = ("An older woman begins to talk, low and unhurried, while her hands keep working. "
               "The others do not stop spinning to listen, but you can tell they are, a small pause in the "
               "rhythm, a softening of shoulders.")
        ep = {"slug": "t", "era": "ancient", "chapters": [{"beats": [{"say": say, "scene": scene}]}]}
        sh = OS.shots(ep, self._beats(ep))
        halves = [x for x in sh if x["start"] >= sh[1]["start"]]
        self.assertGreaterEqual(len(halves), 2, "the long sentence is cut at a comma")
        for x in halves:
            self.assertGreaterEqual(len(x["scene"]["cast"]), 2, (x.get("shot"), "a half of 'the others' is of the others"))
            self.assertNotIn("leave", x["scene"].get("happen") or [], "nobody leaves while the others keep spinning")

    def test_nobody_leaves_a_sentence_about_the_company(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "recline", "action": "drink", "item": "cup"},
                         {"who": "man", "pose": "sit", "action": "drink"}],
                "props": ["oil_lamp", "couch", "amphora", "krater"]}
        for seed in range(8):
            got = OS.happenings(spec, "ancient", seed, "Cups are filled, and the talk begins slowly.", 7.0)
            self.assertNotIn("leave", got, seed)

    def test_the_hand_warmer_sits_at_the_lamp_with_her_hands_out(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands", "at": "center_left"},
                         {"who": "child", "pose": "lie", "action": "sleep", "at": "right"}],
                "props": ["oil_lamp", "mat", "barrel", "basket"]}
        opts = OS.coverage(spec, "ancient", 5)
        ins = opts["insert"][0]
        self.assertNotIn("at", ins["cast"][0], "the slot of the wide shot does not follow her into the insert")
        lay = S.layout(ins, 12)
        her = next(f for f in lay["people"] if f["action"] == "warm_hands")
        lamp = next(q for q in lay["props"] if q["name"] == "oil_lamp")
        R = P.R0 * her["s"] * P.WHO["old_woman"]["size"]
        d = 1 if her["facing"] == "right" else -1
        self.assertGreater(d * (lamp["x"] - her["x"]), 0, "she faces the lamp")
        self.assertLess(abs(lamp["x"] - her["x"]), 3.2 * R, "she sits at the lamp, not across the room")
        sk = P.skeleton("sit", R, 0.0)
        front, back = P.hand_targets("warm_hands", sk, R, 0.0, 0.0)
        self.assertGreater(front[0], 1.7 * R, "seated, the hands reach past the knees toward the fire")
        self.assertGreater(back[0], 1.5 * R)
        # and the slot still holds where nobody is at the light
        lay2 = S.layout(spec, 5)
        self.assertEqual(lay2["collisions"], [])

    def test_a_grey_head_reads_as_old(self):
        import cairo
        for who in ("old_woman", "elder"):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 400)
            cr = cairo.Context(surf)
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            P.draw(cr, who=who, era="ancient", seed=3, pose="sit", action="talk", facing="right", x=160,
                   ground_y=380, scale=1.0, t=0.0)
            lk = P.look(who, "ancient", 3)
            self.assertTrue(lk["grey"])
            self.assertFalse(P.look("woman", "ancient", 3)["grey"])
        # the age lines are drawn by name, under the eyes, and only on grey heads
        src = inspect.getsource(P.draw)
        self.assertIn('if lk["grey"]', src)
        self.assertIn("_age_lines", src)

    def test_the_storyteller_s_close_up_keeps_the_sleeping_child(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "talk", "at": "left"},
                         {"who": "child", "pose": "lie", "action": "sleep", "at": "center"}],
                "props": ["oil_lamp", "mat", "basket", "woodpile"]}
        opts = OS.coverage(spec, "ancient", 5)
        ins = opts["insert"][0]
        self.assertEqual([c["pose"] for c in ins["cast"]], ["sit", "lie"])
        self.assertIn("mat", ins["props"], "the sleeper keeps her bedding")
        self.assertIsNotNone(ins.get("frame"))
        # the two chapters' close-ups are no longer one picture: one has a child in it
        other = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                 "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["oil_lamp"]}
        self.assertNotEqual([c["who"] for c in ins["cast"]], [c["who"] for c in OS.coverage(other, "ancient", 5)["insert"][0]["cast"]])

    def test_the_forum_close_up_stands_against_stone(self):
        import cairo

        def still(shot):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, S.W, S.H)
            ST.draw_still(cairo.Context(surf), "forum", "night", "clear", 2, shot=shot, era="ancient")
            return np.ndarray(shape=(S.H, S.W, 4), dtype=np.uint8, buffer=surf.get_data())
        c, w = still("close"), still("wide")
        y = int(S.H * ST.SETTINGS["forum"].horizon) + 150 - 100     # between the beam and the ground, behind the columns
        xs = [x for x in range(60, S.W - 60, 7)]
        wall = tuple(int(round(v * 255)) for v in ST.STOA_WALL)

        def stone(buf):
            # cairo's buffer is BGRA
            return sum(1 for x in xs if max(abs(int(buf[y, x, 2 - i]) - wall[i]) for i in range(3)) < 40) / len(xs)
        self.assertGreater(stone(c), 0.6, "close in, the stoa's back wall stands behind the columns")
        self.assertLess(stone(w), 0.2, "wide, the town shows between the columns")

    def test_nobody_frowns_in_a_sleep_film(self):
        sp = {"setting": "olive_grove", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "stand", "action": "hold", "mood": "focused", "item": "torch"},
                       {"who": "woman", "pose": "stand", "action": "hold", "mood": "worried", "item": "lantern"}],
              "props": ["fence", "campfire", "goat"]}
        ep = {"slug": "t", "era": "ancient", "chapters": [{"beats": [{"say": "The goats are settled. By torchlight you fasten the gate.", "scene": sp}]}]}
        for x in OS.shots(ep, self._beats(ep)):
            for c in x["scene"]["cast"]:
                self.assertIn(c.get("mood", "calm"), OS.CALM_MOODS, x.get("shot"))
        beat = {"say": "x", "scene": json.loads(json.dumps(sp))}
        A.mend_scene(beat["scene"], "ancient")
        self.assertTrue(all(c["mood"] in OS.CALM_MOODS for c in beat["scene"]["cast"]), "the author's mend says calm too")

    def test_the_spinner_s_lamp_is_not_in_her_hands(self):
        sp = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "old_woman", "pose": "sit", "action": "spin"}], "props": ["oil_lamp", "amphora", "bench"]}
        for seed in range(6):
            lay = S.layout(sp, seed)
            her = lay["people"][0]
            lamp = next(q for q in lay["props"] if q["name"] == "oil_lamp")
            R = P.R0 * her["s"] * P.WHO["old_woman"]["size"]
            d = 1 if her["facing"] == "right" else -1
            ahead = d * (lamp["x"] - her["x"])
            if ahead > 0:
                self.assertGreater(ahead, 2.3 * R, (seed, "the lamp stands in front of the spindle"))


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheEightySeven(unittest.TestCase):
    """Run 98: 87, SHIP, not a note left — and temporal craft still 2 of 3,
    which is graded in code from the cadence probe: effective 21.8 fps over
    the film, 19 in every lamplit room (the firelight noise sat still one
    frame in ten), 1.0 on a close shot of the shore at dawn (the sun's path,
    the one thing that moves on open water, was clipped away behind the
    fisherman's rod and the rock)."""

    def test_the_firelight_is_never_still_and_never_jumps(self):
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "sit", "action": "talk"}], "props": ["oil_lamp"]}
        for seed in range(4):
            sc = S.Scene(sp, "ancient", seed)
            levels = [sc._flicker_level(i / S.Scene.FLICKER_FPS) for i in range(400)]
            for a, b in zip(levels, levels[1:]):
                self.assertIn(abs(a - b), S.Scene.FLICKER_STEPS, (seed, a, b))
            self.assertTrue(all(0 <= v < S.Scene.LIGHT_LEVELS for v in levels))
            self.assertGreater(len(set(levels)), 12, "the walk covers the range")

    def test_a_lamplit_room_reads_alive_on_every_frame(self):
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "recline", "action": "drink", "item": "cup"},
                       {"who": "man", "pose": "sit", "action": "drink"}],
              "props": ["oil_lamp", "couch", "amphora", "krater"]}
        ev = _probe(sp, "ancient", seconds=3.0, seed=7)
        self.assertEqual(ev["duplicate_ratio"], 0.0, ev)

    def test_the_sun_stands_where_the_water_is_in_view(self):
        sp = {"setting": "seashore", "time": "dawn", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "stand", "action": "fish", "item": "rod"},
                       {"who": "woman", "pose": "crouch", "action": "gather", "item": "basket"}],
              "props": ["reeds", "rock", "basket"]}
        for seed in (3, 5, 9):
            sc = S.Scene(sp, "ancient", seed)
            sx = sc.facts["sky_light"][0]
            for lo, hi in sc._cover_spans():
                self.assertFalse(lo <= sx <= hi, (seed, "the sun's path is behind somebody"))
        ev = _probe(sp, "ancient", seconds=3.0, seed=3)
        self.assertLess(ev["duplicate_ratio"], 0.1, ev)

    def test_the_glint_hole_is_the_body_not_the_rod(self):
        sp = {"setting": "seashore", "time": "dawn", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "stand", "action": "fish", "item": "rod"}], "props": []}
        sc = S.Scene(sp, "ancient", 3)
        f = sc.lay["people"][0]
        R = P.R0 * f["s"] * P.WHO["man"]["size"]
        lo, hi, _t, _b = sc._figure_holes()[0]
        self.assertLess(hi - lo, 3.0 * R, "the hole took the rod's reach with it")
        self.assertGreater(hi - lo, 1.6 * R)

    def test_the_water_s_speed_is_data(self):
        self.assertIn("sea", ST.WATER_SPEED)
        self.assertIn("river", ST.WATER_SPEED)


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheSeventyEightAgain(unittest.TestCase):
    """Run 99: 78, SHIP (87 the run before, on the same shelf — the judge
    is noisy, the notes are not): "goats and sheep settled" showed one
    spindly standing animal and no pen; spinning could not be read at phone
    size; the old woman did not read as old, sampled as she glanced up; one
    house room carried six judged moments."""

    def test_settled_animals_lie_in_a_pen(self):
        beat = {"say": "The goats and sheep are already settled for the night, and by torchlight you make sure "
                       "the gate is fastened before heading back toward the hut.",
                "scene": {"setting": "olive_grove", "time": "night", "weather": "clear", "shot": "close",
                          "cast": [{"who": "man", "pose": "stand", "action": "hold", "item": "torch"}],
                          "props": ["campfire", "goat"]}}
        note = A.mend_settled(beat, "ancient")
        self.assertTrue(note)
        self.assertIn("flock", beat["scene"]["props"])
        self.assertNotIn("goat", beat["scene"]["props"])
        self.assertIn("fence", beat["scene"]["props"], "the gate the words name")
        self.assertEqual(S.validate(beat["scene"], "ancient"), [])
        self.assertIsNone(A.mend_settled(beat, "ancient"), "mended once")
        # a standing goat stays standing where nothing says they settled
        up = {"say": "A goat wanders along the wall.", "scene": {"setting": "olive_grove", "time": "dusk", "weather": "clear",
                                                              "shot": "close", "cast": [], "props": ["campfire", "goat"]}}
        self.assertIsNone(A.mend_settled(up, "ancient"))
        self.assertIn("flock", PROPS)
        self.assertIn("flock", OS.stands_for("goat"))

    def test_the_animals_have_bodies_and_the_pen_has_a_gate(self):
        import cairo
        from data_learning.doodle import props as PR
        self.assertGreaterEqual(PR.ANIMAL_LEG, 8.0, "stick legs")
        self.assertGreaterEqual(PR.GOAT_BODY[1], 50)
        for name in ("goat", "sheep", "flock", "fence"):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1400, 500)
            cr = cairo.Context(surf)
            PROPS[name].draw(cr, 700, 470, 1.0, 0.7, 3)
            buf = np.ndarray(shape=(500, 1400, 4), dtype=np.uint8, buffer=surf.get_data())
            self.assertGreater(int((buf[:, :, 3] > 0).sum()), 20000, name)
        self.assertGreaterEqual(PR.FENCE_HALF, 300, "a pen, not a hurdle")
        src = inspect.getsource(PR.fence)
        self.assertNotIn("hatch", src, "the wattle hurdle read as a hide frame")

    def test_a_shot_of_several_people_is_framed_on_them_and_their_things(self):
        sp = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "old_woman", "pose": "sit", "action": "spin"},
                       {"who": "woman", "pose": "sit", "action": "spin"},
                       {"who": "woman", "pose": "sit", "action": "sew"}],
              "props": ["oil_lamp", "amphora", "bench"]}
        opts = OS.coverage(sp, "ancient", 28)
        for name in ("two", "arr"):
            fr = opts[name][0].get("frame")
            self.assertIsNotNone(fr, name)
            self.assertGreater(fr[2], 1.1)
        pen = {"setting": "olive_grove", "time": "night", "weather": "clear", "shot": "close",
               "cast": [{"who": "man", "pose": "stand", "action": "hold", "item": "torch"},
                        {"who": "woman", "pose": "stand", "action": "hold", "item": "lantern"}],
               "props": ["fence", "campfire", "flock"]}
        for seed in (29, 4):
            spec = OS.coverage(pen, "ancient", seed, named=("flock",))["arr"][0]
            fr = spec.get("frame")
            if fr is None:
                continue
            lay = S.layout(spec, seed + 3)
            cx, _cy, k = fr
            x0 = min(max(cx * k - S.W / 2, 0.0), (k - 1) * S.W) / k
            x1 = x0 + S.W / k
            q = next(q for q in lay["props"] if q["name"] == "flock")
            hw = PROPS["flock"].width * q["s"] / 2
            self.assertTrue(q["x"] - hw >= x0 - 1 and q["x"] + hw <= x1 + 1, (seed, "the flock is cut by the window"))
        # a walker's shot is the pan, not a framed group
        walk = dict(sp, cast=[dict(sp["cast"][0]), {"who": "man", "pose": "walk", "action": "carry", "item": "basket"}])
        self.assertIsNone(OS.coverage(walk, "ancient", 28)["two"][0].get("frame"))

    def test_the_spindle_reads_at_a_glance(self):
        self.assertGreaterEqual(P.SPINDLE_WHORL, 0.6)
        self.assertGreaterEqual(P.SPINDLE_DROP, 1.4)
        src = inspect.getsource(P._item)
        self.assertIn("spoke", src, "the turn you can see")

    def test_an_old_face_is_old_looking_up_too_and_stoops(self):
        src = inspect.getsource(P.draw)
        self.assertIn("_age_lines(cr, hcx, hcy, R, lw, up=(action == \"look_up\"))", src)
        self.assertIn("STOOPED", src)
        sk_young = P.skeleton("sit", 46.0, 0.0)
        self.assertGreater(P.STOOP, 0.1)
        self.assertIn("sit", P.STOOPED)
        self.assertIn("stand", P.STOOPED)
        self.assertNotIn("walk", P.STOOPED)
        # white hair, not the grey that read as a hood
        self.assertTrue(all(sum(c) / 3 > 0.78 for c in P.GREY_HAIR), P.GREY_HAIR)
        del sk_young

    def test_the_house_has_four_rooms(self):
        import cairo
        walls = set()
        looks = []
        for seed in range(4):
            surf = cairo.ImageSurface(cairo.FORMAT_RGB24, S.W, S.H)
            ST.draw_still(cairo.Context(surf), "house_inside", "night", "clear", seed, "wide", era="ancient")
            buf = np.ndarray(shape=(S.H, S.W, 4), dtype=np.uint8, buffer=surf.get_data())
            walls.add(tuple(int(v) for v in buf[150, 960, :3]))
            looks.append(buf[300:800, :, :3].astype(np.int32))
        self.assertEqual(len(walls), 4, "one wall colour a room")
        for a in range(4):
            for b in range(a + 1, 4):
                diff = (np.abs(looks[a] - looks[b]).max(axis=2) > 40).mean()
                self.assertGreater(diff, 0.02, (a, b, "two rooms that look the same"))
        self.assertEqual({ST.house_room(s) for s in range(40)}, {0, 1, 2, 3})


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheSeventyFourBlock(unittest.TestCase):
    """Run 100: 74, BLOCKED on junk imagery — the spinners "just sit on the
    floor" (a `pause` happening stopped them, and the spindle was still
    small), and "behind shuttered windows a few houses are still lit" got
    a man at a cauldron in close-up. Plus: the child was in a bed across
    the room from "beside her"; the old woman's fringe covered her eyes
    looking up; the child who came to feed the brazier sat behind it with
    the flames over him; "she fills it slowly" held a basket away from
    the spout."""

    def test_nobody_pauses_while_the_words_say_they_keep_on(self):
        spec = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "spin"},
                         {"who": "woman", "pose": "sit", "action": "spin"}],
                "props": ["oil_lamp", "amphora", "bench"]}
        for seed in range(8):
            got = OS.happenings(spec, "ancient", seed, "The others do not stop spinning to listen.", 7.0)
            self.assertNotIn("pause", got, seed)
            self.assertNotIn("leave", got, seed)

    def test_a_spinner_holds_a_distaff(self):
        src = inspect.getsource(P.draw)
        self.assertIn("_distaff(", src)
        self.assertGreaterEqual(P.DISTAFF_RISE, 1.5, "the wool stands above the shoulder")
        import cairo
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 600)
        cr = cairo.Context(surf)
        P.draw(cr, who="woman", era="ancient", seed=3, pose="sit", action="spin", facing="right", x=250,
               ground_y=560, scale=1.0, t=0.4)
        buf = np.ndarray(shape=(600, 600, 4), dtype=np.uint8, buffer=surf.get_data())
        R = P.R0 * P.WHO["woman"]["size"]
        head_top = 560 - 4.6 * R
        # something drawn above the head: the wool on the distaff
        self.assertGreater(int((buf[:int(head_top - 0.2 * R), :, 3] > 0).sum()), 300, "nothing stands above the head")

    def test_a_sentence_about_the_place_is_the_wide_shot(self):
        spec = {"setting": "forum", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "elder", "pose": "sit", "action": "warm_hands"},
                         {"who": "man", "pose": "walk", "action": "carry", "item": "basket"}],
                "props": ["cauldron", "torch", "column", "stall"]}
        opts = OS.coverage(spec, "ancient", 9)
        self.assertIn("est", opts)
        self.assertEqual(OS._choose(opts, "Behind shuttered windows a few houses are still lit; most are already dark.",
                                    "single:0", False, ["single:0"]), "est")
        self.assertEqual(OS._choose(opts, "Doors are shut now, one by one.", "two", False, ["two"]), "est")
        # a sentence naming a person is still of them
        self.assertNotEqual(OS._choose(opts, "An old man warms his hands at the cauldron.", "two", False, ["two"]), "est")

    def test_the_fringe_falls_back_off_a_face_turned_up(self):
        src = inspect.getsource(P.draw)
        self.assertIn('hcy - (0.32 * R if action == "look_up" else 0.0)', src)

    def test_a_child_feeding_the_fire_sits_beside_it_not_behind(self):
        from data_learning.doodle import happen as HP
        spec = {"setting": "forum", "time": "dusk", "weather": "clear", "shot": "close",
                "cast": [{"who": "woman", "pose": "stand", "action": "wave"}, {"who": "man", "pose": "stand", "action": "gather"}],
                "props": ["stall", "brazier", "basket"]}
        for seed in range(6):
            lay = S.layout(spec, seed)
            acts = [a for a in HP.plan(["feed"], spec, lay, seed, 8.0) if a["kind"] == "feed"]
            if not acts:
                continue
            a = acts[0]
            fire = next(q for q in lay["props"] if q["name"] == "brazier")
            hw = PROPS["brazier"].width * fire["s"] / 2
            end_x = a["keys"][-1][1]
            self.assertGreater(abs(end_x - fire["x"]), hw, (seed, "the child ends up behind the brazier"))

    def test_a_sleeper_lies_by_the_fire_and_whoever_tends_it(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "woman", "pose": "sit", "action": "feed_fire"}, {"who": "child", "pose": "lie", "action": "sleep"}],
                "props": ["brazier", "oil_lamp", "basket", "bed", "amphora"]}
        for seed in (3, 8, 12):
            lay = S.layout(spec, seed)
            self.assertEqual(lay["collisions"], [])
            woman = next(f for f in lay["people"] if f["who"] == "woman")
            child = next(f for f in lay["people"] if f["who"] == "child")
            R = P.R0 * woman["s"]
            # the child's bed ends within reach of her: the gap between her
            # span and the bed's span is small (the bed itself is long)
            bed = next(q for q in lay["props"] if q["name"] == "bed")
            bw = PROPS["bed"].width * bed["s"] / 2
            lo, hi = S.figure_extent("sit", R, "feed_fire")
            if woman["facing"] == "left":
                lo, hi = -hi, -lo
            gap = max(0.0, max(woman["x"] + lo, bed["x"] - bw) - min(woman["x"] + hi, bed["x"] + bw))
            # ...or just across the fire from her (the brazier's own width)
            self.assertLess(gap, 3.6 * R, (seed, "the child is across the room"))

    def test_she_fills_a_jar_at_the_pool(self):
        beat = {"say": "She fills it slowly, listening to the water more than watching it.",
                "scene": {"setting": "spring", "time": "night", "weather": "clear", "shot": "close",
                          "cast": [{"who": "woman", "pose": "crouch", "action": "gather", "mood": "calm", "item": "basket", "at": "center"}],
                          "props": ["amphora", "torch"]}}
        self.assertTrue(A.mend_fill(beat, "ancient"))
        c = beat["scene"]["cast"][0]
        self.assertEqual((c["action"], c["item"]), ("fill", "jar"))
        self.assertEqual(S.validate(beat["scene"], "ancient"), [])
        for seed in (7, 2, 11):
            lay = S.layout(beat["scene"], seed)
            f = lay["people"][0]
            R = P.R0 * f["s"] * P.WHO["woman"]["size"]
            pool_left = S.W * ST.SPRING_X[0]
            self.assertEqual(f["facing"], "right", (seed, "she faces away from the water"))
            self.assertLess(f["x"], pool_left, seed)
            self.assertLess(pool_left - f["x"], 3.5 * R, (seed, "she crouches far from the pool"))
        self.assertIsNone(A.mend_fill(beat, "ancient"), "mended once")
        self.assertIn("jar", P.ITEMS)
        self.assertEqual(A.action_for_words("She fills it slowly.", beat["scene"]), "fill")


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class TheEightySevenAgain(unittest.TestCase):
    """Run 101: 87, SHIP, five notes. The old woman "warming her hands" was
    looking up with her hands off the lamp (a pause), the lamp's glow was
    cut at the window's edge, her mat read as "a rope across the floor";
    the embers insert was "an open rooftop brazier" with the man's elbow
    cut by the frame; an old woman "close by" the child sat across the
    room; the hook's subtitle was sampled mid-fade."""

    def test_nobody_pauses_from_the_work_the_words_describe(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"}], "props": ["oil_lamp"]}
        for seed in range(6):
            got = OS.happenings(spec, "ancient", seed, "An old woman sits up a little longer, warming her hands near a small lamp.", 7.0)
            self.assertNotIn("pause", got, seed)

    def test_a_framed_window_holds_the_lamp_s_glow_and_the_elbow(self):
        q = {"name": "oil_lamp", "x": 1000.0, "y": 900.0, "s": 2.0}
        x0, _t, x1, _b = OS._prop_box(q)
        self.assertGreater(x1 - 1000.0, PROPS["oil_lamp"].width * 2.0 / 2 * 1.5, "the glow is outside the box")
        self.assertGreaterEqual(OS.FIGURE_AIR, 0.6)
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "old_woman", "pose": "sit", "action": "warm_hands"},
                         {"who": "child", "pose": "lie", "action": "sleep"}], "props": ["oil_lamp", "mat"]}
        for seed in (5, 2818272419):
            ins = OS.coverage(spec, "ancient", seed)["insert"][0]
            fr = ins.get("frame")
            if not fr:
                continue
            lay = S.layout(ins, seed + 7)
            cx, _cy, k = fr
            win0 = min(max(cx * k - S.W / 2, 0.0), (k - 1) * S.W) / k
            win1 = win0 + S.W / k
            lamp = next(p for p in lay["props"] if p["name"] == "oil_lamp")
            self.assertLessEqual(lamp["x"] + PROPS["oil_lamp"].width * lamp["s"] * 0.8, win1 + 1, (seed, "the lamp's flame is cut"))

    def test_the_mat_is_a_mat_not_a_rope(self):
        from data_learning.doodle import props as PR
        self.assertGreaterEqual(PR.MAT_THICK, 30)

    def test_the_forum_close_up_is_walled_to_the_top(self):
        import cairo
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, S.W, S.H)
        ST.draw_still(cairo.Context(surf), "forum", "night", "clear", 2, shot="close", era="ancient")
        buf = np.ndarray(shape=(S.H, S.W, 4), dtype=np.uint8, buffer=surf.get_data())
        wall = tuple(int(round(v * 255)) for v in ST.STOA_WALL)
        for y in (120, 300):
            xs = range(60, S.W - 60, 9)
            stone = sum(1 for x in xs if max(abs(int(buf[y, x, 2 - i]) - wall[i]) for i in range(3)) < 40) / len(xs)
            self.assertGreater(stone, 0.6, (y, "sky or roofs over the wall"))
        # and no window of the town behind it glows on the stone (the still
        # and the evening pass alone, without the firelight's own warm pool)
        sf = cairo.ImageSurface(cairo.FORMAT_RGB24, S.W, S.H)
        cr = cairo.Context(sf)
        fx = ST.draw_still(cr, "forum", "night", "clear", 2, "close", era="ancient")
        self.assertLessEqual(fx["town"]["hidden_below"], 0)
        ST.ambient(cr, "forum", "night", "clear", fx, 0.5, 2)
        sf.flush()
        a = np.frombuffer(sf.get_data(), np.uint8).reshape(S.H, S.W, 4)
        lit = sum(1 for (wx, wy) in fx["town"]["windows"] if a[int(wy), int(wx), 2] > 200 and a[int(wy), int(wx), 0] < 150)
        self.assertEqual(lit, 0, "a window glows on the wall")

    def test_the_one_other_person_sits_by_the_sleeper(self):
        spec = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "child", "pose": "lie", "action": "sleep"}, {"who": "old_woman", "pose": "sit", "action": "hold"}],
                "props": ["bed", "oil_lamp", "barrel", "table"]}
        for seed in (3, 3703769626, 11):
            lay = S.layout(spec, seed)
            self.assertEqual(lay["collisions"], [])
            child = next(f for f in lay["people"] if f["who"] == "child")
            her = next(f for f in lay["people"] if f["who"] == "old_woman")
            R = P.R0 * her["s"]
            bed = next(q for q in lay["props"] if q["name"] == "bed")
            bw = PROPS["bed"].width * bed["s"] / 2
            lo, hi = S.figure_extent("sit", R, "hold")
            if her["facing"] == "left":
                lo, hi = -hi, -lo
            gap = max(0.0, max(her["x"] + lo, bed["x"] - bw) - min(her["x"] + hi, bed["x"] + bw))
            self.assertLess(gap, 1.5 * R, (seed, "across the room"))
            self.assertEqual(her["facing"], "right" if her["x"] < child["x"] else "left", (seed, "facing away from the child"))

    def test_the_hook_s_subtitle_is_in_by_the_time_the_judge_looks(self):
        ep = {"title": "What Did Ancient Greeks Do After Dark? | Cozy History for Sleep", "chapters": [{"title": "x"}]}
        caps = OS._captions(ep, [])
        tail = next(c for c in caps if c["text"] == "Cozy History for Sleep")
        self.assertLessEqual(tail["t0"] + tail.get("fade", 1.2), 2.0, "still fading in at 2.2 s")
        self.assertGreaterEqual(sum(tail["color"]) / 3, 240)
