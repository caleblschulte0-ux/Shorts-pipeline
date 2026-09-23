"""The storyboard review: every scene looked at BEFORE the render, repairs
small and deterministic, the judge's failure never blocking a film, and a
clean stamp that goes stale when the kit changes. The brain is faked here —
the suite pays for no model."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

try:
    import cairo  # noqa: F401
    HAVE_CAIRO = True
except ImportError:                                   # pragma: no cover
    HAVE_CAIRO = False

needs_cairo = unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")


def _ep(n_beats=11):
    say = ("The fire has burned low now, and the families gather close to its warmth. "
           "Somebody feeds it one more branch, slowly, and the sparks rise into the dark sky.")
    places = ["cave_mouth", "grassland", "riverbank", "forest", "cave_inside"]
    beats = []
    for j in range(n_beats):
        setting = places[j % 5]
        beats.append({"say": say, "scene": {"setting": setting, "time": "night", "weather": "clear",
                                            "shot": "close",
                                            "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"}],
                                            "props": ["campfire", "woodpile", "stones"]}})
    return {"slug": "a-test-night", "title": "T | Cozy History for Sleep", "era": "stone_age",
            "chapters": [{"title": "One", "beats": beats}]}


def _judge_flagging(flags: dict, calls: list):
    """A fake brain: flags[frame index on the sheet] = (broken, shows_words)."""
    def judge(prompt, sheet):
        calls.append((prompt, Path(sheet)))
        n = int(prompt.split("sheet of ")[1].split(" storyboard")[0])
        frames = []
        for k in range(n):
            broken, shows = flags.get(k, (False, 2))
            frames.append({"n": k + 1, "broken": broken, "why": "a stone on a foot" if broken else "",
                           "shows_words": shows})
        return {"frames": frames}
    return judge


@needs_cairo
class TheStoryboardIsLookedAtFirst(unittest.TestCase):
    def setUp(self):
        from data_learning import ori_storyboard as SB
        self.SB = SB
        self.td = tempfile.TemporaryDirectory()
        self.work = Path(self.td.name)
        self.ledger = SB.LEDGER
        SB.LEDGER = self.work / "ledger.jsonl"

    def tearDown(self):
        self.SB.LEDGER = self.ledger
        self.td.cleanup()

    def test_sheets_are_nine_numbered_tiles(self):
        ep = _ep(11)
        out = self.SB.sheets(ep, self.SB.flat_beats(ep), self.work / "s")
        self.assertEqual(len(out), 2)
        self.assertEqual(len(out[0][1]), 9)
        self.assertEqual(len(out[1][1]), 2)
        from PIL import Image
        with Image.open(out[0][0]) as im:
            self.assertEqual(im.size, (3 * self.SB.TILE_W, 3 * self.SB.TILE_H))
        with Image.open(out[1][0]) as im:
            self.assertEqual(im.size, (3 * self.SB.TILE_W, self.SB.TILE_H))

    def test_a_flagged_frame_is_repaired_a_little_more_each_round_and_the_rest_untouched(self):
        ep = _ep(4)
        before = json.loads(json.dumps(ep))
        calls = []
        # frame 2 (index 1) is always broken according to this brain
        judge = _judge_flagging({1: (True, 2)}, calls)
        # round 2 and 3 re-review only the flagged beat, which is then frame 1
        state = {"round": 0}

        def judge2(prompt, sheet):
            state["round"] += 1
            n = int(prompt.split("sheet of ")[1].split(" storyboard")[0])
            k = 1 if state["round"] == 1 else 0
            return {"frames": [{"n": i + 1, "broken": (i == k), "why": "x" if i == k else "", "shows_words": 2}
                               for i in range(n)]}
        rep = self.SB.polish(ep, judge=judge2, ask=None, work=self.work / "w", rounds=3)
        self.assertFalse(rep["clean"])
        self.assertEqual(rep["rounds"], 3)
        self.assertEqual(rep["repaired"], 3)
        sc = ep["chapters"][0]["beats"][1]["scene"]
        # round 1: another layout; round 2: a prop fewer; round 3: another place
        self.assertGreaterEqual(int(sc.get("variant", 0)), 1)
        self.assertLess(len(sc["props"]), 3)
        self.assertNotEqual(sc["setting"], "grassland")
        for j in (0, 2, 3):
            self.assertEqual(ep["chapters"][0]["beats"][j]["scene"], before["chapters"][0]["beats"][j]["scene"])
        from data_learning.doodle import scene as S
        for b in ep["chapters"][0]["beats"]:
            self.assertEqual(S.validate(b["scene"], "stone_age"), [])
        self.assertEqual(ep["storyboard"]["kit"], self.SB.kit_sha())
        self.assertFalse(ep["storyboard"]["clean"])
        rows = [json.loads(l) for l in self.SB.LEDGER.read_text().splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["flagged"][0]["index"], 1)

    def test_a_scene_that_does_not_show_its_words_is_respecified_only_if_valid(self):
        ep = _ep(3)
        calls = []
        judge = _judge_flagging({0: (False, 0)}, calls)
        good = {"setting": "riverbank", "time": "dusk", "weather": "clear", "shot": "close",
                "cast": [{"who": "woman", "pose": "sit", "action": "fish"}], "props": ["reeds"]}
        rep = self.SB.polish(ep, judge=judge, ask=lambda sy, u: json.dumps(good), work=self.work / "w", rounds=1)
        self.assertEqual(rep["repaired"], 1)
        self.assertEqual(ep["chapters"][0]["beats"][0]["scene"], good)
        ep2 = _ep(3)
        bad = {"setting": "spaceship", "time": "night"}
        self.SB.polish(ep2, judge=_judge_flagging({0: (False, 0)}, []), ask=lambda sy, u: json.dumps(bad),
                       work=self.work / "w2", rounds=1)
        sc = ep2["chapters"][0]["beats"][0]["scene"]
        self.assertEqual(sc["setting"], "cave_mouth", "an invalid answer must not replace the scene")
        self.assertGreaterEqual(int(sc.get("variant", 0)), 1, "it falls back to the small repair")

    def test_a_clean_board_is_stamped_and_not_reviewed_again_for_the_same_kit(self):
        ep = _ep(3)
        calls = []
        rep = self.SB.polish(ep, judge=_judge_flagging({}, calls), ask=None, work=self.work / "w")
        self.assertTrue(rep["clean"])
        self.assertEqual(len(calls), 1)
        rep2 = self.SB.polish(ep, judge=_judge_flagging({}, calls), ask=None, work=self.work / "w")
        self.assertEqual(len(calls), 1)
        self.assertTrue(rep2["skipped"])
        ep["storyboard"]["kit"] = "stale"
        self.SB.polish(ep, judge=_judge_flagging({}, calls), ask=None, work=self.work / "w")
        self.assertEqual(len(calls), 2)

    def test_a_judge_that_cannot_look_never_blocks_the_film(self):
        ep = _ep(2)
        before = json.loads(json.dumps(ep["chapters"]))

        def judge(prompt, sheet):
            raise RuntimeError("no vision judge available")
        rep = self.SB.polish(ep, judge=judge, ask=None, work=self.work / "w")
        self.assertIn("nobody could look", rep["skipped"])
        self.assertEqual(ep["chapters"], before)

    def test_the_publisher_looks_at_the_board_before_rendering(self):
        src = (ROOT / "scripts" / "post_ori.py").read_text()
        self.assertLess(src.index("SB.polish("), src.index("meta = OS.render(ep, out)"))
