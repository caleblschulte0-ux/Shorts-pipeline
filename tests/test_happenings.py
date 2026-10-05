"""Happenings: every shot has something HAPPEN in it, not arms going round.

The operator, 2026-10-03, on the Greek film in sentence-long shots: "it's
still just stick figures moving their arms ... more needs to be happening per
scene. Significantly more." These hold the rules data_learning/doodle/happen.py
was built to: every shot gets events, every event is worked out against the
picture (nobody walks to where somebody already sits, no animal walks over a
sleeper, nothing walks up the wall or across the water), every kind named
actually draws, and what an event changes is measured in pixels."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import numpy as np
    from data_learning.doodle import scene as S, happen as HP, people as P
    HAVE = True
except Exception:                                     # noqa: BLE001
    HAVE = False


def _px(sc, t):
    return np.frombuffer(sc.frame(t).get_data(), np.uint8).reshape(S.H, S.W, 4)[:, :, :3].astype(int)


FIRE_ROOM = {"setting": "forum", "time": "night", "weather": "clear", "shot": "close",
             "cast": [{"who": "old_woman", "pose": "sit_on", "action": "warm_hands"}], "props": ["brazier", "torch"]}
LAMP_ROOM = {"setting": "house_inside", "time": "dusk", "weather": "clear", "shot": "close",
             "cast": [{"who": "woman", "pose": "sit_on", "action": "sew"}], "props": ["oil_lamp", "oil_lamp"]}
BED_ROOM = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
            "cast": [{"who": "man", "pose": "lie", "action": "sleep"}], "props": ["oil_lamp", "bed"]}


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class Happenings(unittest.TestCase):

    def test_every_kind_named_is_a_kind_that_happens(self):
        # a name looked up with a silent default is a capability that does
        # not exist (CLAUDE.md): every kind has a picture it fits and draws
        homes = {
            "arrive": FIRE_ROOM, "feed": FIRE_ROOM, "leave": dict(FIRE_ROOM, cast=FIRE_ROOM["cast"] + [
                {"who": "man", "pose": "stand", "action": "talk"}]),
            "serve": FIRE_ROOM, "light": LAMP_ROOM, "snuff": dict(LAMP_ROOM, time="night"),
            "child": FIRE_ROOM, "passer": FIRE_ROOM, "dog": FIRE_ROOM, "cat": LAMP_ROOM,
            "hens": dict(FIRE_ROOM, time="dusk"), "birds": dict(FIRE_ROOM, time="dusk"),
            "bats": FIRE_ROOM, "fish": {"setting": "seashore", "time": "dusk", "weather": "clear", "shot": "close",
                                        "cast": [{"who": "man", "pose": "sit", "action": "fish"}], "props": []},
            "mouse": dict(LAMP_ROOM, time="night"), "moth": dict(LAMP_ROOM, time="night"), "turn": BED_ROOM,
            "stretch": LAMP_ROOM,
        }
        self.assertEqual(set(homes), set(HP.KINDS))
        for k, spec in homes.items():
            sp = dict(spec, happen=[k], happen_s=7.0)
            self.assertEqual(S.validate(sp, "ancient"), [], k)
            sc = S.Scene(sp, "ancient", 11)
            self.assertEqual([a["kind"] for a in sc.acts], [k], f"{k} did not happen in a picture it fits")
            for t in (0.5, 3.0, 6.0):
                sc.frame(t)                              # and it draws, start to end

    def test_somebody_who_arrives_walks_in_from_outside_to_a_free_place(self):
        sp = dict(FIRE_ROOM, happen=["arrive"], happen_s=7.0)
        sc = S.Scene(sp, "ancient", 11)
        a = sc.acts[0]
        x_start, x_end = a["keys"][0][1], a["keys"][-1][1]
        self.assertTrue(x_start < 0 or x_start > S.W or abs(x_end - x_start) > 3 * a["R"], (x_start, x_end))
        lo, hi = a["claim"]
        for it in S.spans(sc.lay):
            self.assertLessEqual(min(hi, it["hi"]) - max(lo, it["lo"]), HP.GAP,
                                 f"arrived on top of {it['label']}")

    def test_somebody_who_leaves_is_gone_by_the_end(self):
        sp = dict(FIRE_ROOM, cast=FIRE_ROOM["cast"] + [{"who": "man", "pose": "stand", "action": "talk"}],
                  happen=["leave"], happen_s=7.0)
        sc = S.Scene(sp, "ancient", 11)
        a = sc.acts[0]
        x, *_ = HP._state(a, 60.0)
        # at the frame's edge, whole — never half across it (the 79 film)
        self.assertTrue(x <= 1.5 * a["R"] or x >= S.W - 1.5 * a["R"], x)
        self.assertGreater(abs(x - a["keys"][0][1]), 2 * a["R"])

    def test_feeding_the_fire_makes_it_flare(self):
        sp = dict(FIRE_ROOM, happen=["feed"], happen_s=7.0)
        sc = S.Scene(sp, "ancient", 11)
        a = sc.acts[0]
        f = a["flare"]
        dx, dy, size = HP.FLAME_AT[f["name"]]
        x, y = int(f["x"] + dx * f["s"]), int(f["y"] + dy * f["s"])
        box = (slice(max(0, y - 260), y + 40), slice(max(0, x - 160), x + 160))
        before = _px(sc, f["t"] - 0.6)[box].sum()
        at = _px(sc, f["t"] + 0.5)[box].sum()
        self.assertGreater(at, before * 1.01, "the fire did not take the wood")

    def test_lighting_the_lamp_brightens_the_room(self):
        sp = dict(LAMP_ROOM, happen=["light"], happen_s=7.0)
        sc = S.Scene(sp, "ancient", 11)
        t = sc.acts[0]["lamp"]["t"]
        self.assertGreater(_px(sc, t + 1.5).mean(), _px(sc, t - 1.0).mean() + 2.0)

    def test_no_animal_walks_over_a_person(self):
        # the first sample: a dog trotting across a man asleep in bed
        bed = BED_ROOM
        for seed in range(12):
            sp = dict(bed, happen=["dog", "cat"], happen_s=7.0)
            sc = S.Scene(sp, "ancient", seed)
            people_ = [(it["lo"], it["hi"]) for it in S.spans(sc.lay) if it.get("fig") is not None]
            for a in sc.acts:
                self.assertFalse(a.get("behind"), "a far lane indoors is the wall")
                lo, hi = sorted((a["x0"], a["x1"]))
                for p_lo, p_hi in people_:
                    self.assertLessEqual(min(hi, p_hi) - max(lo, p_lo), 0, f"{a['kind']} walks over the sleeper")

    def test_nothing_walks_up_the_wall_or_across_the_water(self):
        for setting in ("house_inside", "seashore"):
            sp = {"setting": setting, "time": "night", "weather": "clear", "shot": "close",
                  "cast": [{"who": "woman", "pose": "sit", "action": "warm_hands"},
                           {"who": "man", "pose": "walk", "action": "idle"}],
                  "props": ["campfire" if setting == "seashore" else "oil_lamp"]}
            if S.validate(sp, "ancient"):
                continue
            lay = S.layout(sp, 3)
            for w in lay["walkers"]:
                self.assertTrue(w.get("near"), f"a walker on the far lane in {setting}")
            self.assertFalse(HP.fits("passer", sp))

    def test_a_lamp_goes_out_only_where_something_else_still_moves(self):
        # the Greek film with happenings, blocked at 3:50 before the watch:
        # a candle blown out in a wide room where it was the only thing
        # alive, then 61 identical frames
        one = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "wide",
               "cast": [{"who": "elder", "pose": "sit_on", "action": "idle"},
                        {"who": "woman", "pose": "stand", "action": "idle"},
                        {"who": "child", "pose": "sit_on", "action": "idle"}], "props": ["oil_lamp"]}
        self.assertEqual(S.validate(one, "ancient"), [])
        sc = S.Scene(dict(one, happen=["snuff"], happen_s=7.0), "ancient", 4)
        self.assertEqual(sc.acts, [], "the room's only living light was put out")
        # where it is planned, what is left still moves: measured after it
        two = dict(LAMP_ROOM, time="night", happen=["snuff"], happen_s=7.0)
        sc = S.Scene(two, "ancient", 4)
        self.assertEqual([a["kind"] for a in sc.acts], ["snuff"])
        t0 = sc.acts[0]["lamp"]["t"] + 1.0
        fr = [_px(sc, t0 + i / 30) for i in range(70)]
        run = best = 0
        for a, b in zip(fr, fr[1:]):
            run = run + 1 if np.abs(a - b).max() < 6 else 0
            best = max(best, run)
        self.assertLess(best, 45, "frozen after the lamp went out")

    def test_whoever_comes_or_goes_is_whole_in_the_frame_and_crosses_nobody(self):
        # the 79 film's judge, three times: "clipped at the right edge",
        # "a second figure merges into her" — people caught walking in across
        # the frame's edge, and through a seated figure
        for seed in range(8):
            for kind in ("arrive", "serve", "child", "light"):
                sp = dict(FIRE_ROOM if kind != "light" else LAMP_ROOM, happen=[kind], happen_s=7.0)
                sc = S.Scene(sp, "ancient", seed)
                for a in sc.acts:
                    x0, *_ = HP._state(a, a["keys"][0][0])
                    self.assertGreaterEqual(x0, 1.2 * a["R"], f"{kind} started outside the frame")
                    self.assertLessEqual(x0, S.W - 1.2 * a["R"], f"{kind} started outside the frame")
                    lo, hi = sorted((x0, a["keys"][-1][1]))
                    for p_lo, p_hi in HP._blocking(sc.lay):
                        self.assertLessEqual(min(hi, p_hi) - max(lo, p_lo), 0.3 * a["R"] + 1,
                                             f"{kind} walked through somebody")
        # whoever leaves stops whole at the edge
        sp = dict(FIRE_ROOM, cast=FIRE_ROOM["cast"] + [{"who": "man", "pose": "stand", "action": "talk"}],
                  happen=["leave"], happen_s=7.0)
        sc = S.Scene(sp, "ancient", 11)
        for a in sc.acts:
            x_end = a["keys"][-1][1]
            self.assertTrue(1.2 * a["R"] <= x_end <= S.W - 1.2 * a["R"], x_end)

    def test_no_second_child_where_a_child_already_sleeps(self):
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "child", "pose": "lie", "action": "sleep"},
                       {"who": "old_woman", "pose": "sit_on", "action": "hold"}],
              "props": ["bed", "oil_lamp"], "happen": ["child"], "happen_s": 7.0}
        self.assertEqual(S.Scene(sp, "ancient", 3).acts, [])

    def test_a_newcomer_keeps_their_head_under_a_framed_window(self):
        # a close-up framed low on a crouching child: a standing arrival's
        # head would be above the window ("the old person's head is cut off
        # by the top-left frame edge")
        from data_learning import ori_sleep as OS
        sp = {"setting": "house_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "child", "pose": "crouch", "action": "warm_hands"}], "props": ["brazier", "oil_lamp"]}
        opts = OS.coverage(sp, "ancient", 5, 7.0)
        ins = opts["insert"][0]
        self.assertIn("frame", ins)
        sc = S.Scene(dict(ins, happen=["arrive", "serve", "light"], happen_s=7.0), "ancient", opts["insert"][1])
        for a in sc.acts:
            self.assertTrue(HP._head_fits(ins, a["y"], a["R"]), a["kind"])

    def test_nobody_walks_in_on_a_sleeping_house(self):
        sp = BED_ROOM
        for k in ("arrive", "serve", "child", "leave", "feed"):
            self.assertFalse(HP.fits(k, sp), k)


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class EveryShotHasSomethingHappen(unittest.TestCase):

    def test_the_greek_film_has_two_or_more_happenings_in_every_shot(self):
        from data_learning import ori_sleep as OS
        ep = OS.load("ancient-greeks-after-dark")
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
        sh = [x for x in OS.shots(ep, beats) if not x.get("painting")]
        counts = [len((x["scene"] or {}).get("happen") or []) for x in sh]
        # a room already full to the frame (a crouching cook, a table, a pot
        # and a brazier) can take only a mouse or a moth, and not two shots
        # running — so nearly every shot, not every one
        self.assertLessEqual(sum(1 for c in counts if c == 0) / len(counts), 0.02, "shots where nothing happens")
        self.assertGreaterEqual(sum(1 for c in counts if c >= 2) / len(counts), 0.85, "shots with one happening")
        # and what the planner promised is what the picture does
        for x in sh[::23]:
            sc = S.Scene(x["scene"], "ancient", x["seed"])
            self.assertEqual([a["kind"] for a in sc.acts], x["scene"]["happen"])
        # a person coming, going or tending something in most of them, not
        # only a moth
        with_people = sum(1 for x in sh if any(k in HP.PEOPLE_KINDS for k in x["scene"].get("happen") or []))
        self.assertGreater(with_people / len(sh), 0.6)

    def test_the_words_decide_first(self):
        from data_learning import ori_sleep as OS
        sp = dict(FIRE_ROOM, cast=FIRE_ROOM["cast"] + [{"who": "man", "pose": "sit", "action": "talk"}])
        got = OS.happenings(sp, "ancient", 5, "He adds another log to the fire, and the dog settles.", 7.0)
        self.assertEqual(got[:2], ["feed", "dog"])
        lamp = dict(LAMP_ROOM)
        got = OS.happenings(lamp, "ancient", 5, "She lights the lamp as the light goes.", 7.0)
        self.assertEqual(got[0], "light")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE, "the doodle kit needs cairo and numpy")
class SomebodyAlreadyHereGetsUp(unittest.TestCase):
    """A room too full for anyone new to walk in still has something happen:
    whoever sits gets up, stands a moment, and sits back down."""

    def test_the_lone_sitter_stretches_and_sits_back(self):
        sp = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "woman", "pose": "sit", "action": "sew"}], "props": ["oil_lamp", "table", "brazier"]}
        self.assertTrue(HP.fits("stretch", sp))
        lay = S.layout(sp, 3)
        acts = HP.plan(["stretch"], sp, lay, 3, 7.0)
        self.assertEqual([a["kind"] for a in acts], ["stretch"])
        a = acts[0]
        self.assertEqual(a["owns"], 0)
        seat = lay["people"][0]["pose"]          # the layout seats a sewer at the table on a bench
        poses = [HP._state(a, t)[1] for t in (0.0, a["keys"][2][0] + 0.5, 7.0)]
        self.assertEqual(poses, [seat, "stand", seat], poses)
        self.assertTrue(all(abs(k[1] - lay["people"][0]["x"]) < 1 for k in a["keys"]), "a stretch is on the spot")

