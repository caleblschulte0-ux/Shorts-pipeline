"""OpenRangeInteractive sleep films — the kit, the renderer, the author and
the publisher, held to what they claim.

Four promises, each a test class:

  * EVERY NAME RESOLVES. A name looked up with a silent default is a
    capability that does not exist (CLAUDE.md). Every setting, prop, pose,
    action, item, mood and person the validator accepts is drawn here, and
    every name it refuses is refused by name.
  * MOTION IS MEASURED, NOT ASSERTED. The validator says a scene moves
    enough to read as alive; this renders scenes it accepts and runs the
    showrunner's OWN cadence probe (`_temporal_evidence`) over them. A scene
    the validator passes and the probe calls frozen is a lie in the kit.
  * THE FILM IS WHOLE. A tiny episode renders end to end (with a stand-in
    voice, so the suite needs no model files): video, audio, captions,
    chapters and a 1920x1080 thumbnail.
  * NOTHING UNFINISHED SHIPS. The author drops an episode rather than
    write a broken one; the publisher's floor and the judge's context are
    what the gate needs.
"""
import json
import random
import subprocess
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


def _scene(**kw):
    base = {"setting": "grassland", "time": "night", "weather": "clear", "props": ["campfire"]}
    base.update(kw)
    return base


@needs_cairo
class EveryNameResolves(unittest.TestCase):
    def setUp(self):
        from data_learning.doodle import people, props, scene, settings
        self.P, self.PR, self.S, self.ST = people, props, scene, settings

    def _draw(self, spec, era, t=1.3):
        sc = self.S.Scene(spec, era, 5)
        sc.frame(t)
        sc.frame(t + 0.5)
        return sc

    def test_every_setting_draws_at_every_time(self):
        for name, st in self.ST.SETTINGS.items():
            for era in st.eras:
                for time in self.ST.TIMES:
                    self._draw(_scene(setting=name, time=time, props=["hearth" if era == "medieval" else "campfire"],
                                      shot="close", weather="clear" if st.interior else "rain"), era)

    def test_every_weather_draws(self):
        for w in self.ST.WEATHER:
            self._draw(_scene(weather=w, props=["campfire"], shot="close"), "stone_age")

    def test_every_prop_draws_in_every_era_it_claims(self):
        for name, pr in self.PR.PROPS.items():
            for era in pr.eras:
                where = pr.settings[0] if pr.settings else "riverbank"
                props = [name] + (["campfire"] if pr.settings else [])   # a wall has no water
                self._draw(_scene(props=props, setting=where), era)

    def test_every_action_draws_in_every_pose_it_allows(self):
        for act, cfg in self.P.ACTIONS.items():
            for pose in cfg["poses"]:
                for who in ("man", "girl"):
                    self._draw(_scene(setting="riverbank", props=[],
                                      cast=[{"who": who, "pose": pose, "action": act}]), "medieval")

    def test_every_item_mood_and_person_draws(self):
        for item in self.P.ITEMS:
            self._draw(_scene(setting="riverbank", props=[],
                              cast=[{"who": "woman", "pose": "stand", "action": "hold", "item": item}]),
                       "stone_age")
        for mood in self.P.MOODS:
            for who in self.P.WHO:
                self._draw(_scene(cast=[{"who": who, "pose": "sit", "action": "talk", "mood": mood}]),
                           "stone_age")

    def test_unknown_names_are_refused_by_name(self):
        v = self.S.validate
        for bad, word in (({"setting": "moon_base"}, "moon_base"), ({"time": "noon"}, "noon"),
                          ({"props": ["laser"]}, "laser"),
                          ({"cast": [{"who": "robot", "pose": "stand", "action": "idle"}]}, "robot"),
                          ({"cast": [{"who": "man", "pose": "fly", "action": "idle"}]}, "fly"),
                          ({"cast": [{"who": "man", "pose": "stand", "action": "juggle"}]}, "juggle"),
                          ({"cast": [{"who": "man", "pose": "stand", "action": "idle", "item": "phone"}]},
                           "phone")):
            errs = v(_scene(**bad), "stone_age")
            self.assertTrue(any(word in e for e in errs), (bad, errs))

    def test_an_action_a_pose_cannot_do_is_refused(self):
        errs = self.S.validate(_scene(cast=[{"who": "man", "pose": "lie", "action": "chop"}]), "stone_age")
        self.assertTrue(any("cannot 'chop'" in e for e in errs), errs)

    def test_another_eras_things_are_refused(self):
        self.assertTrue(self.S.validate(_scene(props=["cottage", "campfire"]), "stone_age"))
        self.assertTrue(self.S.validate(_scene(props=["mammoth", "campfire"]), "medieval"))
        self.assertTrue(self.S.validate(_scene(setting="cave_inside"), "medieval"))

    def test_a_still_scene_is_refused(self):
        errs = self.S.validate({"setting": "grassland", "time": "day", "weather": "clear",
                                "props": ["tree"]}, "stone_age")
        self.assertTrue(any("moves enough" in e for e in errs), errs)
        # a fire at noon is a small orange shape on bright grass: not enough alone
        self.assertTrue(self.S.validate({"setting": "grassland", "time": "day", "props": ["campfire"]},
                                        "stone_age"))

    def test_the_vocabulary_an_author_is_shown_only_names_what_draws(self):
        import re
        for era in self.S.ERAS:
            voc = self.S.vocabulary(era)
            sets = re.search(r"setting: one of ([^(]+)\(", voc).group(1)
            for name in [x.strip() for x in sets.split(",") if x.strip()]:
                fire = "hearth" if era == "medieval" else "campfire"
                self.assertEqual(self.S.validate(_scene(setting=name, props=[fire], shot="close"), era),
                                 [], name)
            props = re.search(r"props: 0-\d+ of ([^(]+)\(", voc).group(1)
            for name in [x.strip() for x in props.split(",") if x.strip()]:
                self.assertIn(era, self.PR.PROPS[name].eras)


@needs_cairo
class MotionIsMeasuredWithTheGatesOwnProbe(unittest.TestCase):
    """Renders accepted scenes and asks the showrunner's cadence probe. The
    phase-1 ceilings are 45% held frames and a 45-frame held run; a single
    scene is held to a stricter 45% so a film made of them has margin."""

    @staticmethod
    def _probe(spec, era, seconds=4.0, seed=3):
        import cairo
        import showrunner_review as SR
        from data_learning.doodle import scene as S
        sc = S.Scene(spec, era, seed)
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1920, 1080)
        with tempfile.TemporaryDirectory() as td:
            mp4 = Path(td) / "s.mp4"
            p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr0",
                                  "-s", "1920x1080", "-r", "24", "-i", "-", "-c:v", "libx264", "-preset",
                                  "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(mp4)],
                                 stdin=subprocess.PIPE)
            for i in range(int(seconds * 24)):
                sc.frame(i / 24, surf)
                p.stdin.write(bytes(surf.get_data()))
            p.stdin.close()
            p.wait()
            return SR._temporal_evidence(mp4, Path(td))

    def _assert_alive(self, spec, era):
        ev = self._probe(spec, era)
        self.assertTrue(ev["measured"], ev)
        self.assertLessEqual(ev["duplicate_ratio"], 0.45, (spec, ev))
        self.assertLessEqual(ev["max_dup_run"], 45, (spec, ev))

    def test_the_staple_scenes_are_alive(self):
        for era, spec in (
            ("stone_age", {"setting": "cave_mouth", "time": "night", "cast": [
                {"who": "man", "pose": "sit", "action": "warm_hands"},
                {"who": "woman", "pose": "sit", "action": "stir"}], "props": ["campfire", "pot"]}),
            ("medieval", {"setting": "cottage_inside", "time": "night", "cast": [
                {"who": "old_woman", "pose": "sit_on", "action": "sew"}], "props": ["hearth", "table"]}),
            ("stone_age", {"setting": "riverbank", "time": "night", "shot": "wide", "props": ["canoe"]}),
            ("medieval", {"setting": "field", "time": "day", "weather": "rain", "shot": "wide"}),
            ("stone_age", {"setting": "grassland", "time": "day", "shot": "close",
                           "cast": [{"who": "man", "pose": "stand", "action": "chop"}], "props": ["woodpile"]}),
            ("ancient", {"setting": "forum", "time": "night", "shot": "close",
                         "cast": [{"who": "man", "pose": "stand", "action": "talk"}], "props": ["brazier", "column"]}),
            ("ancient", {"setting": "villa_inside", "time": "night", "shot": "close",
                         "cast": [{"who": "woman", "pose": "sit_on", "action": "eat"}], "props": ["oil_lamp", "table"]}),
            ("victorian", {"setting": "street", "time": "night", "shot": "close",
                           "cast": [{"who": "man", "pose": "walk", "action": "idle"}], "props": ["gas_lamp", "terrace"]}),
            ("victorian", {"setting": "parlour_inside", "time": "night", "shot": "close",
                           "cast": [{"who": "old_woman", "pose": "sit_on", "action": "sew"}], "props": ["stove", "chair"]}),
            ("egypt", {"setting": "nile_bank", "time": "dusk", "shot": "wide", "props": ["reed_boat", "palm"]}),
            ("egypt", {"setting": "mudbrick_inside", "time": "night", "shot": "close",
                       "cast": [{"who": "woman", "pose": "sit_on", "action": "eat"}], "props": ["oil_lamp", "jar"]}),
            ("early_modern", {"setting": "harbour", "time": "night", "shot": "wide", "props": ["crates", "mooring_post"]}),
            ("early_modern", {"setting": "tavern_inside", "time": "night", "shot": "close",
                              "cast": [{"who": "man", "pose": "sit_on", "action": "drink"}], "props": ["hearth", "table"]}),
        ):
            self.assertEqual(__import__("data_learning.doodle.scene", fromlist=["x"]).validate(spec, era), [])
            self._assert_alive(spec, era)

    def test_random_accepted_scenes_are_alive(self):
        from data_learning.doodle import people as P, props as PR, scene as S, settings as ST
        r = random.Random(20260923)
        checked = 0
        while checked < 6:
            era = r.choice(S.ERAS)
            setting = r.choice([k for k, v in ST.SETTINGS.items() if era in v.eras])
            spec = {"setting": setting, "time": r.choice(ST.TIMES),
                    "weather": "clear" if ST.SETTINGS[setting].interior else r.choice(ST.WEATHER),
                    "shot": r.choice(S.SHOTS),
                    "props": r.sample([k for k, v in PR.PROPS.items() if era in v.eras], r.choice([1, 2, 3])),
                    "cast": []}
            for _ in range(r.choice([0, 1, 2])):
                act = r.choice(list(P.ACTIONS))
                spec["cast"].append({"who": r.choice(list(P.WHO)), "pose": r.choice(P.ACTIONS[act]["poses"]),
                                     "action": act})
            if S.validate(spec, era):
                continue
            checked += 1
            self._assert_alive(spec, era)


def _episode(chapters=8, beats=3):
    say = ("The fire has burned low now, and the families gather close to its warmth. "
           "Somebody feeds it one more branch, slowly, and the sparks rise into the dark sky.")
    scenes = [
        {"setting": "cave_mouth", "time": "dusk", "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"}],
         "props": ["campfire"]},
        {"setting": "riverbank", "time": "dusk", "cast": [{"who": "woman", "pose": "sit", "action": "fish"}],
         "props": ["reeds"]},
        {"setting": "cave_inside", "time": "night", "cast": [{"who": "child", "pose": "lie", "action": "sleep"}],
         "props": ["campfire"]},
    ]
    return {"slug": "a-test-night", "title": "What Did Early Humans Do at Night? | Cozy History for Sleep",
            "thumbnail_text": "NO FIRE?", "era": "stone_age", "description": "A calm night.",
            "thumbnail_scene": {"setting": "cave_mouth", "time": "night",
                                "cast": [{"who": "man", "pose": "crouch", "action": "warm_hands",
                                          "mood": "worried"}], "props": ["campfire"]},
            "tags": ["history for sleep"],
            "chapters": [{"title": f"Part {i + 1}", "beats": [{"say": say, "scene": scenes[(i + j) % 3]}
                                                             for j in range(beats)]}
                         for i in range(chapters)]}


class FakeVoice:
    """A quiet tone as long as the sentence would take to say — the render
    path without the Kokoro model files."""
    def say(self, text):
        import numpy as np
        n = int(24000 * max(0.4, len(text) * 0.012))
        return (0.1 * np.sin(np.arange(n) * 2 * np.pi * 220 / 24000)).astype(np.float32)


class TheFilmFitsTheSlot(unittest.TestCase):
    """Run #15 (2026-09-24): the author was asked for 14-16 chapters of
    1,000-1,400 words — up to 2h50 — wrote 19,611 words, and the 149-minute
    film could not be drawn and judged in the 230-minute step. The film is
    sized to the slot before a chapter is written, and the narration is
    spoken in parallel."""

    def test_the_outline_is_sized_to_the_render_slot(self):
        import ori_author as A
        from data_learning import ori_sleep as OS
        for n in range(A.CHAPTERS[0], A.CHAPTERS[1] + 1):
            ask_lo, ask_hi, check_lo, check_hi = A.chapter_words(n)
            self.assertLessEqual(n * check_hi, OS.MAX_WORDS, f"{n} chapters at the cap overflow the film")
            self.assertGreaterEqual(n * ask_lo, OS.MIN_WORDS, f"{n} chapters at the floor are too short")
            self.assertLess(ask_lo, ask_hi); self.assertLessEqual(check_lo, ask_lo); self.assertLessEqual(ask_hi, check_hi)
        self.assertLessEqual(A.CHAPTERS[1] * (A.TARGET_WORDS // A.CHAPTERS[1]), OS.MAX_WORDS)
        o = {"slug": "a-b", "title": "A curious question about a quiet night | " + A.SUFFIX,
             "thumbnail_text": "NO FIRE?", "thumbnail_scene": _scene(setting="grassland", shot="wide",
                                                                      props=["campfire", "torch"]),
             "description": "d", "chapters": [{"title": f"c{i}", "covers": "x"} for i in range(16)]}
        self.assertTrue(any("chapters" in x for x in A._outline_problems(o, "stone_age")),
                        "sixteen chapters were accepted")
        o["chapters"] = o["chapters"][:5]
        self.assertEqual([x for x in A._outline_problems(o, "stone_age") if "chapters" in x], [])
        self.assertIn(f"{A.CHAPTERS[0]}-{A.CHAPTERS[1]} chapters",
                      A.OUTLINE.format(topic="t", era="e", suffix="s", vocab="v",
                                       chapters_lo=A.CHAPTERS[0], chapters_hi=A.CHAPTERS[1]))
        # and the renderer refuses what the slot cannot hold
        ep = _episode(chapters=6)
        for ch in ep["chapters"]:
            for b in ch["beats"]:
                b["say"] = " ".join(["word"] * 150)
        ep["chapters"][0]["beats"] = ep["chapters"][0]["beats"] * 6
        self.assertGreater(sum(len(b["say"].split()) for c in ep["chapters"] for b in c["beats"]), OS.MAX_WORDS)
        self.assertTrue(any("narrated words" in x for x in OS.validate(ep)))

    def test_the_narration_is_spoken_in_parallel_and_written_in_order(self):
        from data_learning import ori_sleep as OS
        ep = _episode(chapters=3)
        with tempfile.TemporaryDirectory() as td:
            one = OS.narrate(ep, Path(td) / "one.wav", voice=FakeVoice())
            many = OS.narrate(ep, Path(td) / "many.wav", workers=2, voice_factory=FakeVoice)
            import soundfile as sf
            a, _ = sf.read(str(Path(td) / "one.wav")); b, _ = sf.read(str(Path(td) / "many.wav"))
        self.assertEqual(len(one), len(many))
        self.assertEqual([(x.start, x.end, x.text) for x in one], [(x.start, x.end, x.text) for x in many])
        self.assertEqual([x.lines for x in one], [x.lines for x in many])
        self.assertEqual(len(a), len(b))


class TheEpisodeContract(unittest.TestCase):
    def test_a_short_script_is_refused_for_length(self):
        from data_learning import ori_sleep as OS
        bad = OS.validate(_episode())
        self.assertTrue(any("narrated words" in b for b in bad), bad)
        self.assertEqual([b for b in bad if "narrated words" not in b], [])

    def test_a_broken_scene_names_its_beat(self):
        from data_learning import ori_sleep as OS
        ep = _episode()
        ep["chapters"][2]["beats"][1]["scene"] = {"setting": "moon", "time": "night"}
        self.assertTrue(any(b.startswith("chapter 3 beat 2 scene") for b in OS.validate(ep)))

    def test_sentences_split_where_a_voice_breathes(self):
        from data_learning import ori_sleep as OS
        self.assertEqual(OS.sentences("One. Two? \"Three!\" four is lower. Five."),
                         ["One.", "Two?", "\"Three!\" four is lower.", "Five."])


@needs_cairo
class TheFilmIsWhole(unittest.TestCase):
    def test_a_short_render_has_every_part(self):
        from PIL import Image
        from data_learning import ori_sleep as OS
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "ori_test.mp4"
            meta = OS.render(_episode(), out, max_seconds=9, workers=2, voice=FakeVoice())
            self.assertTrue(out.exists())
            self.assertGreater(meta["duration"], 9)
            self.assertEqual(meta["chapters"][0]["t"], 0.0)
            self.assertTrue(out.with_suffix(".srt").read_text().startswith("1\n00:00:01,500 --> "))
            with Image.open(out.with_suffix(".jpg")) as im:
                self.assertEqual(im.size, (1920, 1080))
            json.loads(out.with_suffix(".meta.json").read_text())
            streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                                      "-of", "json", str(out)], capture_output=True, text=True).stdout
            kinds = {s["codec_type"] for s in json.loads(streams)["streams"]}
            self.assertEqual(kinds, {"video", "audio"})


class TheAuthorDropsRatherThanShipsBroken(unittest.TestCase):
    def _fake_ask(self, chapter_words=70, broken_chapter=None):
        from data_learning.doodle import scene as S  # noqa: F401
        calls = {"n": 0}
        say = " ".join(["gentle"] * chapter_words)

        def ask(system, user):
            calls["n"] += 1
            if user.startswith("Plan one episode"):
                return json.dumps({
                    "slug": "a-quiet-stone-age-night", "title": "What Did Early Humans Do at Night? | Cozy History for Sleep",
                    "thumbnail_text": "NO FIRE?", "description": "Calm.", "tags": ["history for sleep"],
                    "thumbnail_scene": {"setting": "cave_mouth", "time": "night", "props": ["campfire"]},
                    "chapters": [{"title": f"Part {i}", "covers": "a calm part"} for i in range(5)]})
            n = int(user.split("Chapter ")[1].split(" of")[0])
            # a real chapter is a sequence of DIFFERENT pictures; one picture
            # nine times is what the author refuses
            # a real chapter walks the whole world: no place past a fifth of the film
            places = ("cave_mouth", "grassland", "cave_inside", "riverbank", "forest", "lakeshore",
                      "mountains", "seashore", "snowfield")
            scenes = [{"setting": places[(j + n) % 9], "time": "night", "props": ["campfire"]} for j in range(9)]
            if n == 1:
                scenes[0] = dict(scenes[0], shot="wide", props=["campfire", "torch"])   # the film opens wide
            if broken_chapter == n:
                scenes = [{"setting": "spaceship", "time": "night"}] * 9
            return json.dumps({"beats": [{"say": say, "scene": sc} for sc in scenes]})
        return ask, calls

    def test_a_valid_book_of_chapters_becomes_an_episode(self):
        import ori_author
        ask, calls = self._fake_ask()
        ep = ori_author.author("What did early humans do at night?", "stone_age", ask=ask)
        self.assertIsNotNone(ep)
        self.assertEqual(len(ep["chapters"]), 5)
        self.assertEqual(calls["n"], 6)
        from data_learning import ori_sleep as OS
        self.assertEqual(OS.validate(ep), [])

    def test_a_flawed_chapter_is_mended_in_code_rather_than_sent_back(self):
        # the second fresh-topic run: chapter 2 failed three attempts on a held
        # 'candle' the kit does not draw, a crowded scene, and one place at all
        # the judged moments — every one a deterministic fix. The brain's
        # answer is mended and repaired before it is checked, so a chapter
        # like this costs ONE call, not three and the film
        import ori_author
        calls = {"n": 0}
        say = " ".join(["gentle"] * 70)

        def ask(system, user):
            calls["n"] += 1
            if user.startswith("Plan one episode"):
                return json.dumps({
                    "slug": "a-peasant-night", "title": "What Did Peasants Do After Dark? | Cozy History for Sleep",
                    "thumbnail_text": "NO CANDLES", "description": "Calm.", "tags": ["history for sleep"],
                    "thumbnail_scene": {"setting": "village", "time": "night", "props": ["campfire"]},
                    "chapters": [{"title": f"Part {i}", "covers": "a calm part"} for i in range(5)]})
            n = int(user.split("Chapter ")[1].split(" of")[0])
            scenes = []
            places = ("cottage_inside", "village", "field", "forest", "riverbank")
            for j in range(9):
                # the cottage at every judged moment (beats 3, 6, 8 of nine
                # equal beats), a held candle, and one crowded scene
                setting = "cottage_inside" if j in (2, 5, 7) else places[(j + n) % 5]
                sc = {"setting": setting, "time": "night", "shot": "close",
                      "cast": [{"who": "woman", "pose": "sit", "action": "sew", "item": "candle"}],
                      "props": ["hearth"] if setting == "cottage_inside" else ["campfire"]}
                if j == 1:
                    sc["cast"] = [{"who": "woman", "pose": "sit", "action": "sew"},
                                  {"who": "man", "pose": "sit_on", "action": "eat"},
                                  {"who": "child", "pose": "lie", "action": "sleep"}]
                    sc["props"] = sc["props"] + ["table", "chair", "bookshelf", "bedroll", "woodpile"]
                scenes.append(sc)
            if n == 1:
                scenes[0] = {"setting": "village", "time": "night", "shot": "wide", "props": ["campfire", "torch"]}
            return json.dumps({"beats": [{"say": say, "scene": sc} for sc in scenes]})
        ep = ori_author.author("What did medieval peasants do after dark?", "medieval", ask=ask)
        self.assertIsNotNone(ep, "mending should have carried every chapter")
        from data_learning import ori_sleep as OS
        self.assertEqual(OS.validate(ep), [])
        self.assertEqual(calls["n"], 6, "one call per chapter: the mend did the rest")
        self.assertEqual(ori_author.repair_film(ep, log=lambda *_: None), [], "and the film holds the rules")

    def test_a_chapter_that_stays_broken_sinks_the_episode(self):
        import ori_author
        ask, calls = self._fake_ask(broken_chapter=5)
        self.assertIsNone(ori_author.author("x", "stone_age", ask=ask))
        self.assertEqual(calls["n"], 1 + 4 + 3)     # outline, four good chapters, three tries at the fifth


class ThePublisherGivesTheGateWhatItNeeds(unittest.TestCase):
    def test_the_judge_context_fits_and_says_sleep(self):
        import post_ori
        ep = _episode(chapters=15, beats=12)
        ctx = post_ori.judge_context(ep, {"duration": 7200, "chapters": [{"t": 0, "label": "x"}]})
        self.assertEqual(ctx["format"], "sleep")
        self.assertLess(len(json.dumps(ctx, indent=0)), 3000 + 1500)
        import showrunner_review as SR
        d = SR._format_directive(ctx)
        self.assertIn("SLEEP FILM", d)
        self.assertIn("mascot=4", d)

    def test_the_floor_refuses_a_short_film(self):
        import post_ori
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "x.mp4"
            out.write_bytes(b"0")
            bad = post_ori.technical_floor(out, {"duration": 600, "chapters": []}, {"min_seconds": 4800})
        self.assertTrue(any("sleep-film floor" in b for b in bad))
        self.assertTrue(any("thumbnail" in b for b in bad))

    def test_the_description_says_what_is_true(self):
        import post_ori
        d = post_ori.description(_episode(), {"chapters": [{"t": 0, "label": "a"}, {"t": 600, "label": "b"},
                                                           {"t": 1200, "label": "c"}]})
        self.assertIn("no AI-generated images", d)
        self.assertIn("Kevin MacLeod", d)
        self.assertIn("0:00 a", d)


if __name__ == "__main__":
    unittest.main()


class TheMailboxJudgeCoversTheChannel(unittest.TestCase):
    """When no judge can watch a film on publish night, the render is kept and
    ChatGPT is asked (docs/REVIEW_MAILBOX.md) — the same route the explainer
    and trending have, or a judge outage costs the channel its week."""

    def test_post_ori_files_a_review_request_on_publish_runs(self):
        src = (ROOT / "scripts" / "post_ori.py").read_text()
        self.assertIn('ctx["mailbox"]', src)
        self.assertLess(src.index('ctx["mailbox"]'), src.index("showrunner_gate.run("))
        self.assertIn("if will_upload and", src[src.index('ctx["mailbox"]') - 800:src.index('ctx["mailbox"]')])

    def test_the_claim_step_can_publish_a_sleep_film(self):
        import claim_reviews
        src = (ROOT / "scripts" / "claim_reviews.py").read_text()
        self.assertIn('req.get("channel") == "curiosity"', src)
        self.assertTrue(callable(claim_reviews._publish_curiosity))
        wf = (ROOT / ".github" / "workflows" / "curiosity.yml").read_text()
        self.assertIn("held-renders-${{ github.run_id }}", wf)
        self.assertIn("output/held/*.jpg", wf)
        self.assertIn("publish_review_media.sh", wf)
        cw = (ROOT / ".github" / "workflows" / "claim_reviews.yml").read_text()
        self.assertIn("YOUTUBE_TOKEN_JSON_CURIOSITY", cw)

    def test_the_held_render_keeps_its_thumbnail_and_captions(self):
        src = (ROOT / "shared" / "review_mailbox.py").read_text()
        for side in (".jpg", ".srt", ".meta.json"):
            self.assertIn(f'"{side}"', src)


@needs_cairo
class ThePictureIsReadable(unittest.TestCase):
    """The first film's judge, 2026-09-23: "sleepers are drawn lying in the
    fire with a plank through their heads". Every figure and every prop on
    the ground plane has a real width (a sleeper is five heads long), the
    layout keeps them clear of each other, a crowded shot is drawn smaller
    rather than overlapped, and every scene of every episode on the shelf
    lays out clean."""

    def setUp(self):
        from data_learning.doodle import people, scene
        self.P, self.S = people, scene

    def test_every_pose_has_an_extent(self):
        for pose in self.P.POSES:
            lo, hi = self.S.figure_extent(pose, 40.0)
            self.assertLess(lo, 0)
            self.assertGreater(hi, 0)

    def test_a_sleeper_is_kept_out_of_the_fire(self):
        spec = {"setting": "cave_mouth", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "lie", "action": "sleep"}],
                "props": ["campfire", "wolf", "bedroll", "stones"]}
        lay = self.S.layout(spec, 3)
        self.assertEqual(lay["collisions"], [])
        spans = {s["label"]: s for s in self.S.spans(lay)}
        man, fire = spans["man:lie"], spans["campfire"]
        # the padded spans may touch by the shared margin, never more
        self.assertLessEqual(min(man["hi"], fire["hi"]) - max(man["lo"], fire["lo"]), self.S.MARGIN)
        bed = spans["bedroll"]
        self.assertEqual(bed["under"], 0)
        self.assertLess(abs((bed["lo"] + bed["hi"]) / 2 - (man["lo"] + man["hi"]) / 2), 30)

    def test_a_crowded_heap_is_drawn_smaller_not_overlapped(self):
        spec = {"setting": "cave_inside", "time": "night", "weather": "clear", "shot": "wide",
                "cast": [{"who": w, "pose": "lie", "action": "sleep"} for w in ("man", "woman", "elder", "child")],
                "props": ["campfire", "torch", "bedroll", "woodpile"]}
        lay = self.S.layout(spec, 5)
        self.assertEqual(lay["collisions"], [])
        self.assertLess(lay["scale"], 1.25)
        for s in self.S.spans(lay):
            self.assertGreaterEqual(s["lo"], -60)
            self.assertLessEqual(s["hi"], self.S.W + 60)

    def test_nothing_is_cut_by_the_frame_edge(self):
        # the second film's judge: "figures are cropped by the frame edge ...
        # (the mammoth)" — a back-layer animal placed at the 6% slot
        specs = [
            {"setting": "grassland", "time": "night", "weather": "clear", "shot": "wide",
             "props": ["campfire", "torch", "mammoth", "tent", "tree"]},
            {"setting": "cave_mouth", "time": "night", "weather": "clear", "shot": "close",
             "cast": [{"who": "man", "pose": "lie", "action": "sleep"}, {"who": "woman", "pose": "sit", "action": "sew"}],
             "props": ["campfire", "wolf", "bedroll", "woodpile"]},
        ]
        for spec in specs:
            lay = self.S.layout(spec, 9)
            self.assertEqual(lay["collisions"], [], spec)
            for sp in self.S.spans(lay):
                self.assertGreaterEqual(sp["lo"], self.S.EDGE, sp)
                self.assertLessEqual(sp["hi"], self.S.W - self.S.EDGE, sp)
        cut = {"people": [{"who": "man", "pose": "stand", "x": 30, "s": 2.0, "facing": "right"}], "props": []}
        self.assertTrue(any("cut by the frame edge" in b for b in self.S.collisions(cut)))

    def test_nobody_stands_in_front_of_the_cave_opening(self):
        # the fifth film's judge: dark hair and a beard against the black of
        # the opening left "a floating white mask" — so the opening is ground
        # the setting owns, and no person's HEAD is placed on it (a fire, a
        # curled wolf, an arm or a pot there still reads, so those may be)
        from data_learning.doodle import settings as ST
        spec = {"setting": "cave_mouth", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "stand", "action": "talk"},
                         {"who": "woman", "pose": "sit", "action": "warm_hands"},
                         {"who": "elder", "pose": "sit_on", "action": "idle"}],
                "props": ["campfire", "stones"]}
        for seed in range(12):
            lay = self.S.layout(spec, seed)
            self.assertEqual(lay["collisions"], [], seed)
            _, mx, ow = ST.cave_opening(seed)
            for sp in self.S.spans(lay):
                if sp["fig"] is None:
                    continue
                hlo, hhi = sp["head"]
                over = min(hhi, mx + ow) - max(hlo, mx - ow)
                self.assertLessEqual(over, self.S.MARGIN, (seed, sp["label"], over))
        # a sleeper with a wolf and a bedroll still lays out clean — the
        # opening does not take room from the props — and a cook with her pot
        # keeps her natural size: the fire moves before anyone is drawn smaller
        sleeper = {"setting": "cave_mouth", "time": "night", "weather": "clear", "shot": "close",
                   "cast": [{"who": "man", "pose": "lie", "action": "sleep"}],
                   "props": ["campfire", "wolf", "bedroll"]}
        cook = {"setting": "cave_mouth", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"},
                         {"who": "woman", "pose": "sit", "action": "stir"}],
                "props": ["campfire", "pot"]}
        for seed in range(8):
            self.assertEqual(self.S.layout(sleeper, seed)["collisions"], [], seed)
            lay = self.S.layout(cook, seed)
            self.assertEqual(lay["collisions"], [], seed)
            self.assertGreaterEqual(lay["scale"], 2.05 * 0.84, seed)

    def test_big_scenery_is_placed_before_the_people(self):
        # a mammoth placed after the man and the fire had nowhere to go and
        # was cut by the frame at every size; solid scenery goes first and
        # the people find room around it, at their natural size
        spec = {"setting": "grassland", "time": "dusk", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "stand", "action": "point"}],
                "props": ["campfire", "mammoth"]}
        for seed in range(6):
            lay = self.S.layout(spec, seed)
            self.assertEqual(lay["collisions"], [], seed)
            self.assertGreaterEqual(lay["scale"], 2.05 * 0.84, seed)
            self.assertIn("mammoth", [q["name"] for q in lay["props"]])

    def test_the_world_is_nearer_in_a_close_shot(self):
        # the sixth film's judge: "a man about as tall as the trees", "a woman
        # filling the cave mouth next to a small child". A close shot brings
        # the world nearer too: a wider, taller cave mouth and a tree line
        # about twice a standing figure
        from data_learning.doodle import settings as ST
        _, _, ow_wide = ST.cave_opening(4, "wide")
        _, _, ow_close = ST.cave_opening(4, "close")
        self.assertGreater(ow_close, ow_wide * 1.2)
        self.assertGreater(ST.CLOSE_TREES, 1.5)
        spec = {"setting": "forest", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "stand", "action": "idle"}], "props": ["campfire", "tree"]}
        lay = self.S.layout(spec, 1)
        tree = next(q for q in lay["props"] if q["name"] == "tree")
        man = lay["people"][0]
        figure_h = self.P.R0 * man["s"] * 4.8                     # feet to crown, about
        self.assertGreater(400 * tree["s"], figure_h * 1.4, (tree["s"], figure_h))

    def test_breath_shows_in_the_cold(self):
        # "no visible cold in the cold chapter": in frost or snow a figure
        # breathes out a puff every few seconds; the same figure drawn warm
        # does not, so the two frames differ
        import cairo
        def frame(cold, t):
            surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 600, 600)
            cr = cairo.Context(surf)
            cr.set_source_rgb(0.1, 0.1, 0.2); cr.paint()
            self.P.draw(cr, who="woman", era="stone_age", seed=3, pose="sit", action="hug_self", x=300,
                        ground_y=560, scale=1.5, t=t, cold=cold)
            return bytes(surf.get_data())
        ts = [0.2, 0.9, 1.6, 2.3, 3.0]
        self.assertTrue(any(frame(True, t) != frame(False, t) for t in ts))
        # asleep, nobody puffs
        self.assertEqual(
            *[bytes(self._sleeper(cold)) for cold in (True, False)])

    def _sleeper(self, cold):
        import cairo
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 600, 600)
        cr = cairo.Context(surf)
        self.P.draw(cr, who="man", era="stone_age", seed=3, pose="lie", action="sleep", x=300,
                    ground_y=560, scale=1.5, t=0.3, cold=cold)
        return surf.get_data()

    def test_two_seeds_do_not_stand_the_same_way(self):
        # the seventh film's judge saw one composition in 16 of 42 samples:
        # the standing spots are tried in a seed-chosen order, and two of the
        # sets put everyone on one side of the fire
        spec = {"setting": "grassland", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"},
                         {"who": "woman", "pose": "sit", "action": "talk"}], "props": ["campfire"]}
        sides = set()
        for seed in range(12):
            lay = self.S.layout(spec, seed)
            self.assertEqual(lay["collisions"], [])
            fire = next(q["x"] for q in lay["props"] if q["name"] == "campfire")
            sides.add(tuple(sorted(f["x"] < fire for f in lay["people"])))
        self.assertIn((True, True), sides | {(False, False)} if (False, False) in sides else sides,
                      "no seed put both people on one side")
        self.assertIn((False, True), sides, "no seed put one on each side")

    def test_looking_up_reads_from_across_the_room(self):
        # the fifth film's judge could not see "looking up" in two dots moved
        # a finger's width; every raised arm since read as a hand at the cheek
        # or "an antenna". What says it now: the head tipped up and back, the
        # face at the crown, and — lying down — the figure on its back with
        # its face to the sky and an arm raised at it
        import cairo
        R = 40.0
        sk = self.P.skeleton("stand", R, 0.0)
        hx, hy = sk["head"]
        ux, uy = self.P.head_of(sk, R, "look_up")
        self.assertLess(uy, hy - 0.15 * R)             # the head goes up
        self.assertGreater(ux, hx + 0.2 * R)           # and back-tilted, so forward
        self.assertEqual(self.P.head_of(sk, R, "idle"), (hx, hy))
        front, _ = self.P.hand_targets("look_up", sk, R, 0.0, 0.0)
        self.assertGreater(front[1], sk["neck"][1])    # and no arm rises past the head
        def frame(action):
            surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 700, 500)
            cr = cairo.Context(surf)
            cr.set_source_rgb(0.1, 0.1, 0.2); cr.paint()
            self.P.draw(cr, who="girl", era="stone_age", seed=3, pose="lie", action=action, x=350,
                        ground_y=460, scale=1.4, t=0.3)
            return bytes(surf.get_data())
        self.assertNotEqual(frame("look_up"), frame("sleep"), "lying and looking up is its own picture")

    def test_a_painting_needs_a_wall(self):
        # the third film's judge: "cave-painting animals float in the open night sky"
        spec = _scene(setting="cave_mouth", props=["campfire", "cave_painting"])
        bad = self.S.validate(spec, "stone_age")
        self.assertTrue(any("cave_painting" in b and "cave_inside" in b for b in bad), bad)
        self.assertEqual(self.S.validate(_scene(setting="cave_inside", props=["campfire", "cave_painting"]),
                                         "stone_age"), [])

    def test_what_a_figure_holds_or_reaches_for_takes_room(self):
        # "the torch-bearer's outstretched arm crosses the seated elder's head"
        R = 40.0
        _, idle = self.S.figure_extent("stand", R)
        _, pointing = self.S.figure_extent("stand", R, "point")
        _, fishing = self.S.figure_extent("sit", R, "fish")
        _, spear = self.S.figure_extent("stand", R, "hold", "spear")
        _, sitting = self.S.figure_extent("sit", R)
        _, stirring = self.S.figure_extent("sit", R, "stir")
        self.assertGreater(pointing, idle)
        self.assertGreater(fishing, idle + 2 * R)
        self.assertGreater(spear, idle)
        self.assertEqual(stirring, sitting, "a sitter's legs already reach past a stirring hand")
        spec = {"setting": "cave_mouth", "time": "dusk", "weather": "clear", "shot": "wide",
                "cast": [{"who": "elder", "pose": "sit", "action": "idle"},
                         {"who": "girl", "pose": "stand", "action": "wave"},
                         {"who": "woman", "pose": "walk", "action": "carry"}],
                "props": ["campfire", "torch", "hide_rack", "woodpile"]}
        self.assertEqual(self.S.layout(spec, 21)["collisions"], [])

    def test_an_animal_behind_the_fire_is_not_in_the_fire(self):
        # "the mammoth's tusk runs into the campfire"
        spec = {"setting": "grassland", "time": "night", "weather": "clear", "shot": "wide",
                "props": ["campfire", "torch", "mammoth", "tent"]}
        lay = self.S.layout(spec, 22)
        self.assertEqual(lay["collisions"], [])
        labels = {sp["label"] for sp in self.S.spans(lay)}
        self.assertIn("mammoth", labels, "a solid back prop takes room like anything else")
        self.assertIn("tent", labels, "a tent is a structure: a fire in front of it read as a fire in it")
        spec2 = {"setting": "grassland", "time": "night", "weather": "clear", "shot": "wide",
                 "props": ["campfire", "barn"]}
        lay2 = self.S.layout(spec2, 22)
        self.assertNotIn("barn", {sp["label"] for sp in self.S.spans(lay2)}, "scenery does not")

    def test_the_title_sits_on_a_band(self):
        # "a cloud sits behind the title word"
        from data_learning import ori_sleep as OS
        ep = _episode(chapters=8, beats=3)
        caps = OS._captions(ep, [OS.Beat(chapter=0, index=0, text="x", scene={}, start=0.0, end=30.0)])
        self.assertTrue(caps[0].get("band"))
        surf, _ = OS._text_surface("Title", 40, band=True)
        self.assertGreater(surf.get_width(), 0)

    def test_back_props_stand_on_the_far_shore_not_in_the_water(self):
        spec = {"setting": "seashore", "time": "day", "weather": "clear", "shot": "wide",
                "props": ["temple", "villa", "olive"]}
        lay = self.S.layout(spec, 3)
        gy = lay["ground_y"]
        for p in lay["props"]:
            self.assertLess(p["y"], self.S.H * 0.58, p["name"])
        dry = self.S.layout(dict(spec, setting="grassland", props=["tree", "hut"]), 3)
        for p in dry["props"]:
            self.assertGreater(p["y"], gy - 170, p["name"])

    def test_a_lamp_stands_on_the_table(self):
        spec = {"setting": "villa_inside", "time": "night", "weather": "clear", "shot": "close",
                "cast": [{"who": "man", "pose": "sit_on", "action": "eat"}], "props": ["oil_lamp", "table", "amphora"]}
        lay = self.S.layout(spec, 4)
        self.assertEqual(lay["collisions"], [])
        lamp = next(p for p in lay["props"] if p["name"] == "oil_lamp")
        table = next(p for p in lay["props"] if p["name"] == "table")
        self.assertEqual(lamp.get("on"), lay["props"].index(table))
        self.assertLess(lamp["y"], table["y"] - 50)
        self.assertLess(abs(lamp["x"] - table["x"]), 200 * table["s"])

    def test_the_topic_bank_names_only_eras_the_kit_draws(self):
        import json
        cfg = json.loads((ROOT / "data_learning" / "ori.config.json").read_text())
        eras = {t["era"] for t in cfg["topics"]}
        self.assertTrue(eras <= set(self.S.ERAS), eras)
        self.assertEqual(len(eras), len(self.S.ERAS), "every era the kit draws has topics waiting")

    def test_collisions_are_named_when_a_scene_cannot_be_helped(self):
        lay = {"people": [{"who": "man", "pose": "sit", "x": 500, "s": 2.0, "facing": "right"},
                          {"who": "woman", "pose": "sit", "x": 520, "s": 2.0, "facing": "right"}],
               "props": [{"name": "campfire", "x": 560, "s": 2.0, "layer": "mid"}]}
        bad = self.S.collisions(lay)
        self.assertTrue(any("man:sit overlaps woman:sit" in b for b in bad))
        self.assertTrue(any("overlaps campfire" in b for b in bad))

    def test_every_scene_on_the_shelf_lays_out_clean(self):
        from data_learning import ori_sleep as OS
        files = sorted(OS.EPISODES.glob("*.json"))
        if not files:
            # the two-hour scripts left the shelf on 2026-09-24 (the ruling:
            # 20-30 minutes); the author writes the next one in CI
            self.skipTest("no episode on the shelf: the author writes the next one")
        n = 0
        for f in files:
            ep = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(OS.validate(ep), [], f.name)
            for c in ep["chapters"]:
                for b in c["beats"]:
                    lay = self.S.layout(b["scene"], 1000 + n)
                    self.assertEqual(lay["collisions"], [], f"{f.name}: {c['title']}: {b['say'][:60]}")
                    n += 1
            # and the whole film obeys the author's own picture rules
            import ori_author as A
            for i, c in enumerate(ep["chapters"]):
                bad = [x for x in A._chapter_problems(c["beats"], ep["era"], 0, 10 ** 6, before=ep["chapters"][:i])
                       if "picture" in x or "of the film" in x]
                self.assertEqual(bad, [], f"{f.name}: {c['title']}")

    def test_a_crowded_scene_goes_back_to_the_author(self):
        import ori_author as A
        crowd = {"say": "words", "scene": _scene(setting="cave_mouth", shot="close",
                                                  cast=[{"who": "man", "pose": "lie", "action": "sleep"},
                                                        {"who": "woman", "pose": "lie", "action": "sleep"},
                                                        {"who": "elder", "pose": "sit_on", "action": "idle"}],
                                                  props=["campfire", "wolf", "bedroll", "woodpile", "stones"])}
        bad = A._chapter_problems([crowd], "stone_age", 0, 99999)
        self.assertTrue(any("too crowded" in b for b in bad), bad)
        calm = {"say": "words", "scene": _scene(setting="grassland", shot="close",
                                                 cast=[{"who": "man", "pose": "sit", "action": "warm_hands"}],
                                                 props=["campfire"])}
        self.assertEqual([b for b in A._chapter_problems([calm], "stone_age", 0, 99999) if "crowded" in b], [])

    def test_a_chapter_moves(self):
        import ori_author as A
        say = " ".join(["word"] * 40)
        same = [{"say": say, "scene": _scene(setting="cave_mouth", shot=("close" if j % 2 else "wide"))}
                for j in range(6)]
        bad = A._chapter_problems(same, "stone_age", 0, 99999)
        self.assertTrue(any("a chapter moves" in b for b in bad), bad)
        marks = A._mark_beats(same)
        same[marks[1]]["scene"] = _scene(setting="forest", shot="close")
        self.assertEqual([b for b in A._chapter_problems(same, "stone_age", 0, 99999) if "chapter moves" in b], [])

    def test_repair_film_holds_a_script_to_the_rules_without_a_hand(self):
        # "a system that makes good videos, not one good video": the author
        # fixes its own output — a chapter standing in one place at its three
        # judged moments, a crowded scene — and never moves a beat whose
        # words name its place
        import ori_author as A
        say = " ".join(["word"] * 30)
        beats = [{"say": say, "scene": _scene(setting="cave_mouth", shot=("close" if j % 2 else "wide"),
                                              cast=[{"who": "man", "pose": "sit", "action": "warm_hands"}],
                                              props=["campfire", "torch"])} for j in range(6)]
        beats[0]["say"] = "Their home is the mouth of a wide, shallow cave. " + say
        crowd = {"say": say, "scene": _scene(setting="cave_mouth", shot="close",
                                              cast=[{"who": "man", "pose": "lie", "action": "sleep"},
                                                    {"who": "woman", "pose": "lie", "action": "sleep"},
                                                    {"who": "elder", "pose": "sit_on", "action": "idle"}],
                                              props=["campfire", "wolf", "bedroll", "woodpile", "stones"])}
        ep = {"slug": "a-test", "era": "stone_age", "chapters": [{"title": "One", "beats": beats + [crowd]}]}
        before = [x for x in A._chapter_problems(ep["chapters"][0]["beats"], "stone_age", 0, 10 ** 6)
                  if "moves" in x or "crowded" in x]
        self.assertTrue(before)
        notes = A.repair_film(ep, log=lambda *_: None)
        self.assertTrue(notes, "nothing was repaired")
        after = [x for x in A._chapter_problems(ep["chapters"][0]["beats"], "stone_age", 0, 10 ** 6)
                 if "moves" in x or "crowded" in x]
        self.assertLess(len(after), len(before))
        self.assertEqual(ep["chapters"][0]["beats"][0]["scene"]["setting"], "cave_mouth",
                         "the beat whose words say 'cave' stayed in the cave")
        # the shelf's script needs nothing: the rules already hold there
        from data_learning import ori_sleep as OS
        for f in sorted(OS.EPISODES.glob("*.json")):
            shelf = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(A.repair_film(shelf, log=lambda *_: None), [], f.name)

    def test_a_crowd_of_people_and_a_pinned_pair_are_repaired_without_touching_the_words(self):
        # the third fresh-topic run (medieval, chapter 3) died with four wide
        # shots "drawn at 60% size" and two same-picture pairs, every one
        # logged as "the words pin those beats" — but no prop drop, person
        # drop or shot change touches the words. The rule itself says "drop
        # a prop or a person, or widen the shot" and "change the setting or
        # the shot": the author now does all three
        import ori_author as A
        who = ["man", "woman", "child", "elder"]
        four = [{"who": w, "pose": "stand", "action": "talk"} for w in who]
        sc = {"setting": "farmyard", "time": "night", "weather": "clear", "shot": "wide",
              "cast": json.loads(json.dumps(four)), "props": ["campfire", "torch", "barn", "cart", "cow", "sheep"]}
        did = A.uncrowd_scene(sc, "medieval", seeds=(1000,))
        self.assertTrue(did, "a wide farmyard at 76% was left crowded")
        self.assertEqual(self.S.validate(sc, "medieval"), [])
        # a close shot holding two houses and a cow: no single drop fixes
        # the collision, so fewer collisions has to count as progress
        sc2 = {"setting": "field", "time": "night", "weather": "clear", "shot": "close",
               "cast": json.loads(json.dumps(four)),
               "props": ["campfire", "timber_house", "cottage", "woodpile", "cow"]}
        self.assertTrue(A.uncrowd_scene(sc2, "medieval", seeds=(1005,)))
        self.assertFalse(self.S.layout(sc2, 1005)["collisions"])
        self.assertIn("campfire", sc2["props"])
        # two neighbours whose words both name the farm, same shot: the
        # setting is pinned, so the shot changes
        say = "Out in the farmyard the family gathers by the barn. " + " ".join(["word"] * 30)
        beats = [{"say": say, "scene": {"setting": "farmyard", "time": "night", "weather": "clear",
                                        "shot": "close", "cast": [dict(four[0])], "props": ["campfire"]}}
                 for _ in range(2)]
        ep = {"slug": "a-test", "era": "medieval", "chapters": [{"title": "One", "beats": beats}]}
        notes = A.repair_film(ep, log=lambda *_: None)
        self.assertTrue(any("shot" in n for n in notes), notes)
        self.assertEqual({b["scene"]["setting"] for b in beats}, {"farmyard"}, "the words pin the place")
        self.assertNotEqual(self.S.shot_of(beats[0]["scene"]), self.S.shot_of(beats[1]["scene"]))
        self.assertEqual([x for x in A._chapter_problems(beats, "medieval", 0, 10 ** 6) if "back to back" in x], [])

    def test_the_idle_the_daylight_and_the_pinned_opening_are_mended_in_code(self):
        # the fourth fresh-topic run (13 of 14 chapters, then the clock):
        # two brain calls lost to "everyone idle", one to a daylight scene
        # no fire could light, one to a chapter opening where the last
        # closed with words that pin it
        import ori_author as A
        # idle: the words say what they do; a fire says warm_hands; two say talk
        def beat(say, cast, props=("campfire",), setting="grassland"):
            return {"say": say, "scene": {"setting": setting, "time": "night", "weather": "clear", "shot": "close",
                                          "cast": cast, "props": list(props)}}
        idle = lambda who="man", pose="stand": {"who": who, "pose": pose, "action": "idle"}
        beats = [beat("She sits and sews by the light.", [idle("woman", "sit")]),
                 beat("They eat their supper of pottage.", [idle(), idle("woman")]),
                 beat("The children play in the yard.", [idle("child")]),
                 beat("A quiet moment.", [idle()]),
                 beat("Two neighbours, and a long evening.", [idle(), idle("elder")], props=("cauldron",)),
                 beat("He works.", [{"who": "man", "pose": "stand", "action": "carry"}])]
        n = A.mend_idle(beats, "medieval", log=lambda *_: None)
        self.assertGreaterEqual(n, 3)
        acts = [b["scene"]["cast"][0]["action"] for b in beats]
        self.assertEqual(acts[0], "sew"); self.assertEqual(acts[1], "eat"); self.assertEqual(acts[2], "play")
        for b in beats:
            self.assertEqual(self.S.validate(b["scene"], "medieval"), [], b["say"])
        self.assertEqual([x for x in A._chapter_problems(beats, "medieval", 0, 10 ** 6) if "idle" in x], [])
        self.assertEqual(A.action_for_words("nothing here", beats[4]["scene"]), "talk")
        self.assertEqual(A.action_for_words("nothing here", beats[3]["scene"]), "warm_hands")
        # daylight where no fire counts: dusk, then the lights again
        day = {"setting": "field", "time": "day", "weather": "clear", "shot": "wide",
               "cast": [{"who": "man", "pose": "stand", "action": "hoe"}], "props": ["wheat"]}
        did = A.mend_scene(day, "medieval")
        self.assertTrue(did and "day ->" in did, did)
        self.assertEqual(self.S.validate(day, "medieval"), [])
        # a chapter that opens where the last closed, its own words pinning
        # the village: the previous chapter's last beat moves instead
        say = " ".join(["word"] * 30)
        prev = [beat(say, [idle()], setting="grassland"), beat(say, [idle()], setting="village")]
        cur = [beat("Back in the village square, " + say, [idle()], setting="village"),
               beat(say, [idle()], setting="forest")]
        ep = {"slug": "a-test", "era": "medieval", "chapters": [{"title": "One", "beats": prev}, {"title": "Two", "beats": cur}]}
        notes = A.repair_film(ep, log=lambda *_: None, only_chapter=1)
        self.assertTrue(any("One beat 2" in x for x in notes), notes)
        self.assertEqual(cur[0]["scene"]["setting"], "village")
        self.assertEqual([x for x in A._chapter_problems(cur, "medieval", 0, 10 ** 6, before=[ep["chapters"][0]])
                          if "new place" in x], [])
        # a pinned place the layout cannot move is let go before anything is dropped
        pinned = {"setting": "village", "time": "night", "weather": "clear", "shot": "wide",
                  "cast": [{"who": "man", "pose": "stand", "action": "talk", "at": "center"},
                           {"who": "woman", "pose": "stand", "action": "talk", "at": "center_left"}],
                  "props": ["campfire", "torch", {"name": "cottage", "at": "center"}]}
        did = A.uncrowd_scene(pinned, "medieval", seeds=(1000,))
        self.assertTrue(did, "a pinned crowd was left")
        self.assertFalse(self.S.layout(pinned, 1000)["collisions"])

    def test_run_sixteen_a_walker_is_not_motion_a_hearth_stays_indoors_and_a_tool_clears_the_face(self):
        # run #16 (2026-09-24): the medieval film was BLOCKED by the code gate
        # at 11:36 — 43 s frozen on a daylight close shot the motion table had
        # called alive because a child was "walking". Measured against the
        # gate's own detector: a walker on the spot is 0.75-1.0 duplicate;
        # chop and wave are 0.14 and 0.18. And the storyboard's notes:
        # "hearth stands in an open field" (a repair moved an indoor beat
        # outdoors with its furniture), "axe handle and head cross the face"
        import math
        import ori_author as A
        from data_learning.doodle import people as P
        S = self.S
        day = {"setting": "grassland", "time": "day", "weather": "clear", "shot": "close",
               "cast": [{"who": "woman", "pose": "crouch", "action": "gather", "item": "bundle", "at": "left"},
                        {"who": "child", "pose": "walk", "action": "idle", "at": "right"}],
               "props": ["tree", "bush"]}
        self.assertTrue(any("moves enough" in x for x in S.validate(day, "medieval")),
                        "a walker on the spot still counts as motion")
        chop = dict(day, cast=[{"who": "man", "pose": "stand", "action": "chop"}])
        self.assertEqual(S.validate(chop, "medieval"), [])
        did = A.mend_scene(day, "medieval")
        self.assertTrue(did and "day ->" in did, did)
        self.assertEqual(S.validate(day, "medieval"), [])
        # a beat moved outdoors leaves the hearth behind (a campfire stands in)
        sc = {"setting": "grassland", "time": "night", "weather": "clear", "shot": "close",
              "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"}], "props": ["hearth", "bed", "table"]}
        notes = A.take_outdoors(sc, "medieval")
        self.assertIn("hearth -> campfire", notes)
        self.assertNotIn("hearth", sc["props"]); self.assertNotIn("bed", sc["props"]); self.assertIn("campfire", sc["props"])
        self.assertEqual(A.take_outdoors({"setting": "cottage_inside", "props": ["hearth"]}, "medieval"), [])
        say = " ".join(["word"] * 30)
        beats = [{"say": say, "scene": {"setting": "cottage_inside", "time": "night", "weather": "clear", "shot": "close",
                                        "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"}],
                                        "props": ["hearth", "bed"]}} for _ in range(6)]
        ep = {"slug": "a-test", "era": "medieval", "chapters": [{"title": "One", "beats": beats}]}
        A.repair_film(ep, log=lambda *_: None)
        for b in beats:
            st = S.SETTINGS[b["scene"]["setting"]]
            names = [(q if isinstance(q, str) else q["name"]) for q in b["scene"]["props"]]
            if not st.interior:
                self.assertNotIn("hearth", names, "a hearth went outdoors")
                self.assertNotIn("bed", names)
            self.assertEqual(S.validate(b["scene"], "medieval"), [])
        # the axe and the hoe never cross the face, anywhere in the swing
        R = 80.0
        def gap(p, a, b):
            (px, py), (ax, ay), (bx, by) = p, a, b
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            u = 0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
            return math.hypot(px - (ax + u * dx), py - (ay + u * dy)) - R
        for action, item in (("chop", "axe"), ("hoe", "hoe")):
            worst = 9e9
            for i in range(60):
                t = i * 0.05
                sk = P.skeleton("stand", R, t, 0.0)
                head = P.head_of(sk, R, action)
                (hx, hy), _ = P.hand_targets(action, sk, R, t, 0.0)
                if item == "axe":
                    seg = ((hx - 0.2 * R, hy + 0.5 * R), (hx + 0.35 * R, hy - 1.1 * R))
                    for q in ((hx + 0.25 * R, hy - 1.15 * R), (hx + 0.75 * R, hy - 1.25 * R),
                              (hx + 0.7 * R, hy - 0.8 * R), (hx + 0.35 * R, hy - 0.85 * R)):
                        worst = min(worst, math.hypot(q[0] - head[0], q[1] - head[1]) - R)
                else:
                    seg = ((hx - 0.4 * R, hy - 1.4 * R), (hx + 0.9 * R, hy + 1.7 * R))
                worst = min(worst, gap(head, *seg))
            self.assertGreaterEqual(worst, 0.1 * R, f"the {item} crosses the face ({worst / R:.2f} R)")

    def test_whoever_acts_at_the_fire_is_drawn_beside_it(self):
        # measured before: a woman warming her hands 6-15 heads from the
        # hearth while an idle child stood one head away; the storyboard's
        # commonest note. Whoever feeds, warms or stirs takes the nearest slot
        from data_learning.doodle import people as P
        S = self.S
        for setting, fire in (("cottage_inside", "hearth"), ("grassland", "campfire")):
            for shot in ("close", "wide"):
                for seed in (1000, 1001, 1002, 1005):
                    sp = {"setting": setting, "time": "night", "weather": "clear", "shot": shot,
                          "cast": [{"who": "child", "pose": "stand", "action": "idle"},
                                   {"who": "woman", "pose": "sit", "action": "warm_hands"},
                                   {"who": "man", "pose": "sit", "action": "feed_fire"}],
                          "props": [fire, "torch"] if shot == "wide" and setting == "grassland" else [fire]}
                    lay = S.layout(sp, seed)
                    self.assertEqual(lay["collisions"], [])
                    f = next(q for q in lay["props"] if q["name"] == fire)
                    self.assertEqual([p["who"] for p in lay["people"]], ["child", "woman", "man"], "cast order kept")
                    for p in lay["people"]:
                        if p["action"] in S.FIRE_ACTIONS:
                            R = P.R0 * p["s"] * P.WHO[p["who"]]["size"]
                            g = (abs(p["x"] - f["x"]) - S.PROPS[fire].width * f["s"] / 2) / R
                            self.assertLessEqual(g, 4.0, f"{p['action']} is {g:.1f} heads from the {fire} "
                                                         f"({setting}, {shot}, seed {seed})")

    def test_a_scene_where_nothing_moves_is_mended_before_the_brain_is_asked_again(self):
        # the first fresh-topic run: chapter 1 rejected twice for "nothing in
        # this scene moves enough" and the author gave up. The smallest valid
        # light is added in code; a hearth is never lit outdoors; a prop the
        # kit does not know is dropped
        import ori_author as A
        sc = {"setting": "village", "time": "night", "weather": "clear", "shot": "wide",
              "cast": [{"who": "man", "pose": "stand", "action": "carry"}], "props": ["cart"]}
        did = A.mend_scene(sc, "medieval")
        self.assertTrue(did and "lit" in did, did)
        self.assertEqual(self.S.validate(sc, "medieval"), [])
        self.assertNotIn("hearth", sc["props"])
        sc2 = {"setting": "cottage_inside", "time": "night", "weather": "clear", "shot": "close",
               "cast": [{"who": "woman", "pose": "sit", "action": "sew"}], "props": ["table", "spaceship"]}
        did2 = A.mend_scene(sc2, "medieval")
        self.assertIn("dropped spaceship", did2)
        self.assertEqual(self.S.validate(sc2, "medieval"), [])
        fine = _scene(setting="grassland", shot="close", cast=[{"who": "man", "pose": "sit", "action": "eat"}])
        self.assertIsNone(A.mend_scene(fine, "stone_age"))
        beats = [{"say": "words", "scene": dict(sc, props=["cart"])}, {"say": "words", "scene": fine}]
        self.assertEqual(A.mend_beats(beats, "medieval", log=lambda *_: None), 1)

    def test_a_chapter_opens_on_a_new_place(self):
        import ori_author as A
        _beat = lambda **kw: {"say": "words", "scene": _scene(**kw)}
        prev = {"beats": [_beat(setting="cave_mouth", shot="close")]}
        beats = [_beat(setting="cave_mouth", shot="wide"), _beat(setting="forest", shot="close")]
        bad = A._chapter_problems(beats, "stone_age", 0, 99999, before=[prev])
        self.assertTrue(any("new chapter opens on a new place" in b for b in bad), bad)
        beats[0] = _beat(setting="grassland", shot="wide")
        self.assertEqual([b for b in A._chapter_problems(beats, "stone_age", 0, 99999, before=[prev])
                          if "new place" in b], [])

    def test_the_author_caps_one_picture_across_the_whole_film(self):
        import ori_author as A
        say = " ".join(["the fire burns low and the night goes on"] * 12)
        cave = {"setting": "cave_mouth", "time": "night", "shot": "close", "props": ["campfire"],
                "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"}]}
        other = ["grassland", "riverbank", "forest", "lakeshore"]
        # each chapter alone is fine (three cave beats of ten, none back to back)
        chapter = [{"say": say, "scene": dict(cave, setting=(other[j % 4] if j % 3 else "cave_mouth"))}
                   for j in range(10)]
        self.assertEqual(A._chapter_problems(chapter, "stone_age", 0, 99999), [])
        # a film that is nothing but such chapters crosses three in ten by
        # the fourth one, and the fourth is told how many it may still use
        before = [{"beats": [dict(b, scene=dict(cave)) for b in chapter]} for _ in range(3)]
        bad = A._chapter_problems(chapter, "stone_age", 0, 99999, before=before)
        self.assertTrue(any("of the film" in b for b in bad), bad)
        note = A._tally_note(A._picture_tally(before), 30)
        self.assertIn("cave_mouth (close shot) x30", note)
        self.assertIn("Prefer other settings", note)
        self.assertEqual(A._tally_note({}, 0), "")

    def test_a_topic_finds_its_era_or_is_refused_honestly(self):
        import ori_author as A
        self.assertEqual(A.era_for("What did ordinary Romans do after dark?", ask=None), "ancient")
        self.assertEqual(A.era_for("How medieval peasants slept", ask=None), "medieval")
        self.assertEqual(A.era_for("A night with the first humans in an Ice Age cave", ask=None), "stone_age")
        # no word the table knows: the brain is asked, and only a listed era counts
        self.assertEqual(A.era_for("A night in a lighthouse", ask=lambda sy, u: "ancient\n"), "ancient")
        self.assertIsNone(A.era_for("A night in a lighthouse", ask=lambda sy, u: "space_age"))
        self.assertIsNone(A.era_for("A night on the Apollo 11 launch pad", ask=None))
        # two eras named at once is a question, not a guess
        self.assertIsNone(A.era_for("Romans and medieval knights compared", ask=None))

    def test_the_film_opens_wide(self):
        import ori_author as A
        say = " ".join(["the fire burns low and the night goes on"] * 12)
        places = ["cave_mouth", "grassland", "riverbank", "forest", "cave_inside"]
        beats = [{"say": say, "scene": {"setting": places[j % 5], "time": "night", "shot": "close",
                                        "props": ["campfire"], "cast": [{"who": "man", "pose": "sit", "action": "talk"}]}}
                 for j in range(6)]
        self.assertEqual([b for b in A._chapter_problems(beats, "stone_age", 0, 99999) if "wide" in b], [])
        bad = A._chapter_problems(beats, "stone_age", 0, 99999, opening=True)
        self.assertTrue(any("first picture" in b for b in bad), bad)
        beats[0]["scene"]["shot"] = "wide"
        self.assertEqual([b for b in A._chapter_problems(beats, "stone_age", 0, 99999, opening=True) if "wide" in b], [])
        # the shelf's own film opens wide
        from data_learning import ori_sleep as OS
        for f in sorted(OS.EPISODES.glob("*.json")):
            ep = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(A._chapter_problems(ep["chapters"][0]["beats"], ep["era"], 0, 10 ** 6, opening=True), [], f.name)

    def test_the_author_refuses_a_chapter_where_everyone_only_sits(self):
        import ori_author as A
        say = " ".join(["the fire burns low and the night goes on"] * 12)
        places = ["cave_mouth", "grassland", "riverbank", "forest", "cave_inside"]
        beats = [{"say": say, "scene": {"setting": places[j % 5], "time": "night", "shot": "close",
                                        "props": ["campfire"],
                                        "cast": [{"who": "man", "pose": "sit", "action": "idle"}]}}
                 for j in range(10)]
        bad = A._chapter_problems(beats, "stone_age", 0, 99999)
        self.assertTrue(any("everyone idle" in b for b in bad), bad)
        for j in range(8):
            beats[j]["scene"]["cast"][0]["action"] = ["warm_hands", "talk", "knap", "sew", "eat", "feed_fire",
                                                      "look_up", "hug_self"][j]
        self.assertEqual([b for b in A._chapter_problems(beats, "stone_age", 0, 99999) if "idle" in b], [])

    def test_the_author_refuses_a_chapter_that_is_one_picture(self):
        import ori_author as A
        say = " ".join(["the fire burns low and the night goes on"] * 12)
        cave = {"setting": "cave_mouth", "time": "night", "shot": "close", "props": ["campfire"],
                "cast": [{"who": "man", "pose": "sit", "action": "warm_hands"}]}
        beats = [{"say": say, "scene": dict(cave)} for _ in range(10)]
        bad = A._chapter_problems(beats, "stone_age", 0, 99999)
        self.assertTrue(any("same picture" in b for b in bad), bad)
        for j in range(5):
            beats[j]["scene"] = dict(cave, setting=["grassland", "riverbank", "cave_inside", "grassland", "riverbank"][j])
        # five different pictures then the cave five times running: the share
        # is fine now, the run is not
        bad = A._chapter_problems(beats, "stone_age", 0, 99999)
        self.assertTrue(any("back to back" in b for b in bad), bad)
        for j in range(5, 10):
            beats[j]["scene"] = dict(cave, setting=["cave_mouth", "grassland", "cave_mouth", "riverbank", "cave_mouth"][j - 5])
        self.assertEqual([b for b in A._chapter_problems(beats, "stone_age", 0, 99999) if "same picture" in b or "back to back" in b], [])
