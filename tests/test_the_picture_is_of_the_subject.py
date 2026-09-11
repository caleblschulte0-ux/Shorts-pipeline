"""A picture is chosen from the SUBJECT — not the medium, not the setting.

2026-09-11, rendering `ozone-hole-recovery` end to end: the first EIGHT
SECONDS — the hook, a quarter of the runtime, the beat that decides whether
anyone watches — was a cartoon ROCKET.

The scene's brain-authored code opens `subject_image('earth from space')`.
`earth` was in no table; `space` was; and nothing said a trailing modifier
may not decide the picture. So the lookup answered 🚀 and the mechanic
dutifully drew the ozone hole on top of it.

Measured over the 384 distinct scene subjects in `niche.config.json`, that
was not one unlucky phrase:

    35 subjects ending in "photo"  ->  CAMERA WITH FLASH
     6 subjects saying "in/from space" -> ROCKET

"bank vault door photo", "cavendish banana photo", "erupting volcano lava
photo" — all of them a camera emoji. This is the third instance of one bug
this week (`VTM GOLD logo.svg` was the first, in `funnel/series_icons`): a
word describing the FILE or the PLACE was allowed to decide the picture.
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import icons                             # noqa: E402

CAMERA, ROCKET, GLOBE = "1f4f8", "1f680", "1f30d"


def _subjects():
    cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
    out = collections.Counter()
    for st in cfg.get("stories", []):
        for seg in st.get("segments", []):
            code = (seg.get("scene") or {}).get("code") or ""
            for m in re.finditer(r"subject_image\(\s*['\"]([^'\"]+)['\"]", code):
                out[m.group(1).strip().lower()] += 1
    return out


class TheMediumIsNotTheSubject(unittest.TestCase):
    def test_a_photo_of_a_thing_is_not_a_camera(self):
        for label in ("bank vault door photo", "cavendish banana photo",
                      "erupting volcano lava photo", "stack of cash bills photo",
                      "lightning bolt photo", "wooden pencil photo"):
            self.assertNotEqual(icons.emoji_codepoint(label), CAMERA, label)

    def test_no_subject_in_the_config_resolves_to_a_camera(self):
        bad = [n for n in _subjects() if icons.emoji_codepoint(n) == CAMERA]
        self.assertEqual(bad, [], f"{len(bad)} subjects still draw a camera")

    def test_the_medium_word_is_stripped_not_matched(self):
        self.assertEqual(icons._subject_tokens("red balloon photo"),
                         ["red", "balloon"])

    def test_the_camera_row_is_gone_entirely(self):
        """Its ONLY key was "photo", so the row existed to say "if the label
        mentions a photograph, draw a camera". A camera is never the subject
        of a data story — there is nothing left for it to win."""
        for keys, cp in icons._MAP:
            self.assertNotEqual(cp, CAMERA, f"camera row is back via {keys}")


class TheSettingIsNotTheSubject(unittest.TestCase):
    def test_earth_from_space_is_not_a_rocket(self):
        for label in ("earth from space", "planet earth from space",
                      "earth planet from space", "earth globe from space",
                      "spinning planet in space"):
            self.assertNotEqual(icons.emoji_codepoint(label), ROCKET, label)

    def test_it_is_the_earth(self):
        """An absent entry is not neutral — it hands the picture to whatever
        else in the phrase happens to be listed."""
        for label in ("earth from space", "planet earth from space",
                      "spinning planet in space", "world globe photo"):
            self.assertEqual(icons.emoji_codepoint(label), GLOBE, label)

    #: A rocket is a fair picture for these. It is not a fair picture for
    #: the EARTH, which is what it was being used for.
    SPACEFLIGHT = ("rocket", "launch", "spacecraft", "probe", "nebula")

    def test_only_spaceflight_subjects_draw_a_rocket(self):
        bad = [n for n in _subjects()
               if icons.emoji_codepoint(n) == ROCKET
               and not any(w in n for w in self.SPACEFLIGHT)]
        self.assertEqual(bad, [], f"{len(bad)} subjects still draw a rocket")

    def test_a_satellite_is_not_a_rocket(self):
        """It shared the rocket's row, so every satellite, space station and
        satellite map in the config launched."""
        for label in ("satellite", "international space station photo",
                      "gulf of mexico coastline satellite map"):
            self.assertNotEqual(icons.emoji_codepoint(label), ROCKET, label)

    def test_a_rocket_is_still_reachable_when_it_IS_the_subject(self):
        self.assertEqual(icons.emoji_codepoint("a rocket launch"), ROCKET)

    def test_the_phrase_is_cut_at_the_setting(self):
        self.assertEqual(icons._subject_tokens("asteroid in space"),
                         ["asteroid"])

    def test_partitive_and_compound_phrases_keep_their_subject(self):
        """`of`, `and` and `with` are NOT setting words — the real subject
        usually follows them."""
        self.assertEqual(icons.emoji_codepoint("stack of dollar bills"),
                         icons.emoji_codepoint("dollar bills"))
        self.assertEqual(icons._subject_tokens("pile of coal"),
                         ["pile", "of", "coal"])

    def test_the_two_words_that_cost_good_matches_are_out(self):
        """`at` and `through` were in the setting list and were the only two
        that removed more signal than noise across the 384 subjects."""
        self.assertNotIn("at", icons._SETTING)
        self.assertNotIn("through", icons._SETTING)
        self.assertIsNotNone(
            icons.emoji_codepoint("staring anxiously at ringing phone"))
        self.assertIsNotNone(
            icons.emoji_codepoint("dirt hiking trail through forest"))


class TheFixRemovesOnlyWRONGAnswers(unittest.TestCase):
    """A narrowing is only right if what it drops was wrong.

    The oracle is FROZEN, not recomputed. It was recomputed from `_MAP` at
    first, and that quietly stopped being an oracle the moment the camera row
    was deleted from `_MAP` — the "old" behaviour it measured was the new
    one. These are the actual subject strings out of `niche.config.json`
    that the old matcher answered with a camera or a rocket.
    """

    #: Every scene subject in the config carrying the word "photo". The old
    #: matcher had a row whose only key was "photo", so all of these drew
    #: CAMERA WITH FLASH.
    WAS_A_CAMERA = ['assorted colorful banana varieties photo collage',
                    'banana shipping crate photo',
                    'bank vault door photo',
                    'blood donor giving blood photo',
                    'blood sample vial tube photo',
                    'blue recycling bin photo',
                    'boomerang nebula deep space photo',
                    'camera photo thumbnail',
                    'cargo ship aerial photo',
                    'cargo ship silhouette photo',
                    'cat sitting photo',
                    'cavendish banana photo',
                    'chess board top down photo',
                    'chess pawn piece photo',
                    'city street light glare photo',
                    'computer chip macro photo',
                    'concrete seawall with ocean waves photo',
                    'dog running photo',
                    'dog sitting photo',
                    'earth from space pacific ocean photo',
                    'earth planet photo from space',
                    'erupting volcano lava photo',
                    'farm crop field aerial photo',
                    'flooded coastal city street photo',
                    'funeral cremation urn photo',
                    'giant beetle macro photo',
                    'house front porch photo',
                    'house key photo',
                    'house with for sale sign photo',
                    'industrial gas cylinder tank photo',
                    'international space station module photo',
                    'international space station photo',
                    'large sand pile mound photo',
                    'left hand raised cutout photo',
                    'lightning bolt photo',
                    'lottery ball machine drum photo',
                    'lottery balls photo',
                    'man silhouette raising left hand photo',
                    'milky way night sky photo',
                    'moving truck photo',
                    'official license document photo',
                    'open leather wallet with cash photo',
                    'orange city light glow horizon photo',
                    'overweight dog side profile photo',
                    'pile of sand mound photo',
                    'plastic waste pile photo',
                    'podcast microphone photo',
                    'polaroid photo stack',
                    'red helium balloon photo',
                    'shipping container photo',
                    'smartphone checkout screen photo',
                    'smartphone incoming call screen photo',
                    'smartphone texting screen photo',
                    'stack of cash bills photo',
                    'stack of white paper application forms photo',
                    'starry night sky photo',
                    'unusual heirloom banana variety photo',
                    'vertical glass thermometer photo',
                    'vintage radio dial photo',
                    'wilting diseased banana plant photo',
                    'woman silhouette raising left hand photo',
                    'wooden dock piling in ocean water photo',
                    'wooden pencil photo',
                    'wooden pier post in ocean water photo',
                    'world globe photo']

    #: Every scene subject matching the old rocket row
    #: ("satellite", "space", "rocket", "launch").
    WAS_A_ROCKET = ['earth from space',
                    'earth globe from space',
                    'earth planet from space',
                    'gulf of mexico coastline satellite map',
                    'large rocky asteroid in space',
                    'planet earth from space',
                    'rocket launching',
                    'rocket launching into sky',
                    'satellite',
                    'satellite orbiting earth',
                    'spinning planet in space',
                    'voyager space probe']

    def test_the_frozen_lists_are_not_empty(self):
        """A guard against an oracle that silently measures nothing."""
        self.assertGreaterEqual(len(self.WAS_A_CAMERA), 30)
        self.assertGreaterEqual(len(self.WAS_A_ROCKET), 8)

    def test_not_one_of_them_draws_a_camera_now(self):
        bad = [n for n in self.WAS_A_CAMERA
               if icons.emoji_codepoint(n) == CAMERA]
        self.assertEqual(bad, [], f"{len(bad)} still draw a camera")

    def test_none_of_them_draws_a_rocket_unless_it_is_about_spaceflight(self):
        bad = [n for n in self.WAS_A_CAMERA + self.WAS_A_ROCKET
               if icons.emoji_codepoint(n) == ROCKET
               and not any(w in n for w in
                           ("rocket", "launch", "spacecraft", "probe",
                            "nebula"))]
        self.assertEqual(bad, [], f"{len(bad)} still draw a rocket")

    def test_the_earth_ones_answer_with_the_earth(self):
        earths = [n for n in self.WAS_A_ROCKET
                  if "earth" in n or "planet" in n or "world" in n]
        self.assertGreaterEqual(len(earths), 4)
        for n in earths:
            self.assertEqual(icons.emoji_codepoint(n), GLOBE, n)

    def test_a_subject_that_was_already_right_is_untouched(self):
        """The narrowing must not cost correct answers — these resolved
        before the change and still do, to the same thing."""
        for label, cp in (("stack of dollar bills", "1f4b5"),
                          ("a dog", "1f415"),
                          ("rocket launching", ROCKET)):
            self.assertEqual(icons.emoji_codepoint(label), cp, label)


class TheChannelCanACTUALLYDrawWhatItAsksFor(unittest.TestCase):
    """A scene whose subject resolves to nothing draws nothing, and the beat
    falls back to a bar chart.

    Operator, 2026-09-11: *"crank it up to 10."* Measured against every
    `subject_image(...)` call in the config, only 169 of 384 distinct
    subjects resolved — so more than half this channel's beats were charts
    because the PICTURE DID NOT EXIST, not because a chart was the right way
    to say it. That is the ceiling on how good the scene beats can look, and
    it is the one that moves with plain table work.
    """

    #: Where coverage stood when the block was added. A floor, not a target:
    #: it may go up, and it must never quietly fall back.
    FLOOR_SUBJECTS = 355
    FLOOR_CALLS = 405

    def _resolved(self):
        subs = _subjects()
        hit = {n: c for n, c in subs.items() if icons.emoji_codepoint(n)}
        return subs, hit

    def test_most_of_what_the_channel_asks_for_can_be_drawn(self):
        subs, hit = self._resolved()
        self.assertGreaterEqual(
            len(hit), self.FLOOR_SUBJECTS,
            f"subject coverage fell to {len(hit)}/{len(subs)}")

    def test_weighted_by_how_often_each_subject_is_used(self):
        subs, hit = self._resolved()
        self.assertGreaterEqual(
            sum(hit.values()), self.FLOOR_CALLS,
            f"call coverage fell to {sum(hit.values())}/{sum(subs.values())}")

    def test_the_commonest_subjects_all_resolve(self):
        """The long tail can miss. The things the channel reaches for over
        and over may not."""
        subs = _subjects()
        for name, _n in subs.most_common(25):
            self.assertIsNotNone(icons.emoji_codepoint(name),
                                 f"{name!r} draws nothing")

    def test_specific_beats_general_inside_the_new_block(self):
        """Three rows got this wrong on the first pass and every one showed
        up as a wrong picture."""
        for label, wrong in (("elderly person silhouette", "1f9cd"),
                             ("apartment door with number", "1f3e2"),
                             ("lottery ball machine drum photo", "1f6e2")):
            self.assertNotEqual(icons.emoji_codepoint(label), wrong, label)

    def test_drum_is_not_a_key(self):
        """An oil drum, a lottery drum and a snare are three different
        pictures and the word picks none of them."""
        for keys, _cp in icons._MAP:
            self.assertNotIn("drum", keys)

    def test_the_generic_money_row_still_closes_the_table(self):
        """The file's own rule — "last resort so specific subjects win
        first". The new block goes BEFORE it, not after."""
        self.assertIn("dollar", icons._MAP[-1][0])
        self.assertEqual(icons.emoji_codepoint("gold coin"), "1fa99")


if __name__ == "__main__":
    unittest.main()
