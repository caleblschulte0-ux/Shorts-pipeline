"""ONE "is this the same video again?" for every data channel
(shared/near_duplicate.py, 2026-10-02 — "those landline videos").

  * the title guard is the explainer's original, behaviour for behaviour
    (the original kept here verbatim as the oracle);
  * two shared subject nouns is the same story whatever the title says, and
    the real landline packages prove it; distinct stories are left alone;
  * the brain layer names a posted title or NONE, and fails OPEN, saying so;
  * the corpus spans the data channels inside the registry's window, and
    the window lives in the registry alone.
"""
from __future__ import annotations

import difflib
import json
import random
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import near_duplicate as nd  # noqa: E402


# ---- the explainer's guard as it was in scripts/post_stories.py, verbatim
_DUP_SEQ = 0.75
_DUP_JACCARD = 0.60
_DUP_STOP = frozenset(
    "the a an of in on to for is are and or its it how why what when we you "
    "your our new most all than that this has have was were be been at by "
    "with from about into over under more less just now still".split())


def _orig_sig_words(title):
    words = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower()).split()
    return {w for w in words if w not in _DUP_STOP and len(w) > 2}


def _orig_duplicate_of(title, posted_titles):
    if not (title or "").strip():
        return None
    mine = _orig_sig_words(title)
    for other in posted_titles:
        if not (other or "").strip():
            continue
        if difflib.SequenceMatcher(None, title.lower(),
                                   other.lower()).ratio() >= _DUP_SEQ:
            return other
        theirs = _orig_sig_words(other)
        union = mine | theirs
        if union and len(mine & theirs) / len(union) >= _DUP_JACCARD:
            return other
    return None


class TheTitleGuardIsTheOriginal(unittest.TestCase):
    def test_equivalent_on_the_real_posted_log_and_on_noise(self):
        log = json.loads((ROOT / "state/posted_log.json").read_text())["posted"]
        titles = [e.get("title") or "" for e in log][-200:]
        rng = random.Random(7)
        words = sorted({w for t in titles for w in t.split()})
        probes = list(titles[:60])
        for _ in range(200):
            probes.append(" ".join(rng.choice(words) for _ in range(rng.randint(2, 8))))
        probes += ["", "   ", "a of the", "Vinyl Beat CDs. Nobody Saw It Coming."]
        for t in probes:
            self.assertEqual(nd.duplicate_of(t, titles), _orig_duplicate_of(t, titles), t)
            self.assertEqual(nd.sig_words(t), _orig_sig_words(t), t)

    def test_post_stories_uses_it(self):
        src = (ROOT / "scripts/post_stories.py").read_text()
        self.assertIn("from shared.near_duplicate import", src)
        self.assertNotIn("def duplicate_of(", src)


def _pkg(date, name):
    return json.loads((ROOT / "state/trending_packages" / date / name).read_text())


class TwoSubjectNounsIsTheSameStory(unittest.TestCase):
    def test_the_landline_race_is_caught_whatever_it_is_called(self):
        new = _pkg("20260927", "02_graph-mobile-lines-buried-landlines.json")
        # the 09-26 telling: two shared nouns, words alone catch it
        hit = nd.subject_duplicate_of(new, ["Mobile Broadband Left Fixed Lines Behind"],
                                      brain=False)
        self.assertEqual(hit[0], "Mobile Broadband Left Fixed Lines Behind")
        self.assertTrue(hit[1].startswith("subject:"), hit)
        # the 08-03 telling shares ONE noun ("landline") — that is what the
        # brain is for, and it is shown the series, not just the title
        asked = {}

        def brain(system, user):
            asked["user"] = user
            return "Broadband Passed Landlines in 20 Years"
        with mock.patch("shared.script_generator._call_llm", brain):
            hit = nd.subject_duplicate_of(new, ["Broadband Passed Landlines in 20 Years"])
        self.assertEqual(hit, ("Broadband Passed Landlines in 20 Years", "brain"))
        self.assertIn("Mobile cellular vs Fixed telephone", asked["user"])

    def test_the_repeats_the_channel_actually_shipped(self):
        pairs = [("BYD Passed Tesla To Lead The Global EV Race", "BYD Just Passed Tesla in EV Sales"),
                 ("Solar Left Wind Power Behind", "Solar Just Overtook Wind Power Worldwide"),
                 ("Nvidia Overtook Apple In Market Value", "Who's Actually Worth More: Nvidia or Apple?"),
                 ("China Pulled Away In Electric Car Sales", "China vs The World: Electric Car Sales"),
                 ("Vinyl Just Passed CDs In Music Revenue", "Vinyl Is Outselling CDs Again")]
        for new, old in pairs:
            self.assertIsNotNone(nd.subject_duplicate_of(new, [old], brain=False), (new, old))

    def test_different_stories_are_left_alone(self):
        posted = ["Mobile Lines Buried Landlines Worldwide", "BYD Just Passed Tesla in EV Sales",
                  "Vinyl Is Outselling CDs Again", "Sports Betting Just Passed The Box Office"]
        for new in ("Dollar General Quietly Passed McDonald's",
                    "Student Debt Passed Auto Loans In 2010",
                    "Jet Engines Now Fly 20x Longer Between Overhauls",
                    "Butter Beat Margarine. Nobody Announced It."):
            self.assertIsNone(nd.subject_duplicate_of(new, posted, brain=False), new)

    def test_race_words_and_channel_words_are_not_a_subject(self):
        self.assertEqual(nd.same_subject(nd.subject_words("Solar Just Passed Coal Worldwide"),
                                         nd.subject_words("Vinyl Just Passed CDs Worldwide")), set())
        self.assertNotIn("passed", nd.subject_words("Solar Just Passed Coal"))
        self.assertNotIn("didyouknow", nd.subject_words({"title": "x", "hashtags": ["didyouknow"]}))

    def test_a_package_contributes_its_series_not_its_hashtags(self):
        p = {"title": "The Cord Lost", "hook": "", "y_label": "per 100 people",
             "series": [{"name": "Mobile cellular"}, {"name": "Fixed telephone"}],
             "hashtags": ["vinyl", "cds"]}
        w = nd.subject_words(p)
        self.assertIn("mobile", w)
        self.assertIn("telephone", w)
        self.assertNotIn("vinyl", w)


class TheBrainNamesTheStoryOrNone(unittest.TestCase):
    TITLES = ["Mobile Broadband Left Fixed Lines Behind", "Butter Beat Margarine"]

    def test_a_named_title_is_the_hit_and_none_is_none(self):
        with mock.patch("shared.script_generator._call_llm",
                        return_value="Mobile Broadband Left Fixed Lines Behind"):
            self.assertEqual(nd.brain_duplicate_of("The Cord Lost The World", self.TITLES),
                             "Mobile Broadband Left Fixed Lines Behind")
        with mock.patch("shared.script_generator._call_llm", return_value="NONE"):
            self.assertIsNone(nd.brain_duplicate_of("The Cord Lost The World", self.TITLES))

    def test_a_made_up_title_does_not_count(self):
        with mock.patch("shared.script_generator._call_llm", return_value="Some Other Video"):
            self.assertIsNone(nd.brain_duplicate_of("x", self.TITLES))

    def test_no_backend_fails_open_and_says_so(self):
        lines = []
        with mock.patch("shared.script_generator._call_llm", side_effect=RuntimeError("429")):
            self.assertIsNone(nd.brain_duplicate_of("x", self.TITLES, log=lines.append))
        self.assertTrue(any("no brain" in ln for ln in lines), lines)

    def test_the_verdict_runs_words_first_then_the_brain(self):
        with mock.patch("shared.script_generator._call_llm", return_value="Butter Beat Margarine") as llm:
            hit = nd.subject_duplicate_of("Spreads: The Dairy Comeback", self.TITLES)
        self.assertEqual(hit, ("Butter Beat Margarine", "brain"))
        with mock.patch("shared.script_generator._call_llm") as llm:
            nd.subject_duplicate_of("Mobile Lines Buried Landlines", self.TITLES)
            llm.assert_not_called()                 # words already answered


class TheCorpusAndTheWindow(unittest.TestCase):
    def test_the_window_is_the_registrys(self):
        reg = json.loads((ROOT / "config/channel_registry.json").read_text())
        self.assertIn("no_repeat_subject_days", reg["defaults"])   # the live one carries it
        self.assertEqual(nd.window_days("trending"), reg["defaults"]["no_repeat_subject_days"])
        self.assertEqual(nd.window_days("explainer"), nd.window_days("trending"))
        self.assertGreaterEqual(nd.window_days(), 90)

    def test_the_corpus_spans_the_data_channels_inside_the_window(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "state").mkdir()
        (tmp / "state/posted_log.json").write_text(json.dumps({"posted": [
            {"title": "Old Trending", "posted_at": "2026-01-01T00:00:00Z"},
            {"title": "New Trending", "posted_at": "2026-09-27T11:52:29Z"}]}))
        (tmp / "state/explainer_posted_log.json").write_text(json.dumps({"posted": {
            "slug-a": {"title": "New Explainer", "at": "2026-10-01T12:56:45+00:00", "state": "posted"},
            "slug-b": {"title": "Claimed Only", "at": "2026-10-01T12:56:45+00:00", "state": "uploading"}}}))
        now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        titles = nd.corpus_titles(nd.posted_corpus(days=120, root=tmp, now=now))
        self.assertEqual(titles, ["New Trending", "New Explainer"])


if __name__ == "__main__":
    unittest.main()
