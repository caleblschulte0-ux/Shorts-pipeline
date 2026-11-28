"""A FAILED FETCH IS NOT A DRY WELL.

2026-11-21..28: the story forge kept no story for a week with every run
green. `state/forge_used.json` remembered 96 indicators as UNUSABLE —
among them life expectancy at birth, the total fertility rate and primary
enrollment, world series from 1972 that clear every shape test (fetched
live on 11-28: 58.8 -> 73.5 years, 4.55 -> 2.19 births per woman,
82 -> 102 percent). The on-doctrine pool measured 191 against the live
catalogue; 90 used plus 96 "unusable" left six, and those six had their
dataset key in a story already and were drawn, fetched and dropped by
every run ("themes available: energy(1), population(3), health(1),
work(1) ... 0 usable", runs 357-380).

Three leaks in one loop, all in scripts/story_forge.py:

  * a fetch that FAILED — timeout, refusal, a gateway page that is not
    JSON — came back as the same None an empty series returns, and the
    indicator was banked as unusable for good (one timeout is in run
    44873077455's log; an HTML answer was not even printed);
  * a story the editorial gate HELD on its words had already spent its
    indicators as USED (run 44873077455: four composed, one kept, three
    held by the premise judge, ~12 good series gone);
  * an indicator whose dataset key was already in a story was neither
    used nor unusable, so it was redrawn forever.

Held here: no answer is not a verdict (not used, not unusable, said out
loud, asked again next run); no country list stops the run before it
judges anything; a held story gives its data back with a strike, and
HOLD_STRIKES retire it; data already in a story is used; and the
catalogue filters read the doctrine's own themes (crime, military, the
body) while an index or a score is refused as an analyst's construct.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import story_forge as sf                   # noqa: E402

LE = "SP.DYN.LE00.IN"
OB = "SH.STA.OBES.ZS"
BEDS = "SH.MED.BEDS.ZS"
MEAS = "SH.IMM.MEAS"
HEALTH = [LE, OB, BEDS, MEAS]          # four families: one story of 3-4 beats
CATALOGUE = {
    2: [{"id": LE, "name": "Life expectancy at birth (years)"},
        {"id": OB, "name": "Obesity prevalence (% of adults)"},
        {"id": BEDS, "name": "Hospital beds (per 1,000 people)"},
        {"id": MEAS, "name": "Immunization, measles (% of children ages 12-23 months)"}],
    16: [], 12: [], 75: [],
}
RISING = [{"date": str(y), "value": 10.0 + (y - 2000)} for y in range(2000, 2013)]
FLAT = [{"date": str(y), "value": 5.0} for y in range(2000, 2013)]
COUNTRIES = [{"id": "USA", "name": "United States",
              "region": {"value": "North America"}},
             {"id": "FRA", "name": "France", "region": {"value": "Europe"}}]


def _story(dss):
    return {"slug": "a-story", "title": "A Story", "hook": "h", "closing": "c",
            "hashtags": ["data"], "question": "",
            "segments": [{"key": d["key"], "insight_type": d["insight_type"],
                          "say": "x"} for d in dss],
            "_datasets": dss, "words_by": "test"}


class ForgeCase(unittest.TestCase):
    """The forge against a fake World Bank whose answers this test chooses
    per URL: a JSON body, no bytes at all (`None`), or bytes that are not
    JSON (b"<html>")."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="forge-"))
        self.urls: list[str] = []
        self.answers: dict[str, object] = {}     # substring -> raw bytes/None
        self.series = RISING
        self._saved = {k: getattr(sf, k) for k in
                       ("CACHE", "USED", "CONFIG", "LAST", "DATA_DIR",
                        "POSTED_LOG", "RETRY_PAUSE_S") if hasattr(sf, k)}
        sf.CACHE = self.tmp / "cache"
        sf.USED = self.tmp / "state" / "forge_used.json"
        sf.LAST = self.tmp / "state" / "forge_last.json"
        sf.CONFIG = self.tmp / "niche.config.json"
        sf.DATA_DIR = self.tmp / "data"
        sf.DATA_DIR.mkdir()
        sf.POSTED_LOG = self.tmp / "state" / "posted.json"
        sf.RETRY_PAUSE_S = 0
        sf.CONFIG.write_text(json.dumps({"stories": []}))
        sf.USED.parent.mkdir(parents=True)
        self._patches = [
            mock.patch.object(sf, "_get", self._wb),
            mock.patch.object(sf, "compose", lambda dss, used: _story(dss)),
            mock.patch.object(sf, "_passes_editorial", lambda s: (True, [])),
            mock.patch.object(sf, "_builds", lambda s: True),
            mock.patch.object(sf, "_too_similar", lambda s, c: None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        for k, v in self._saved.items():
            setattr(sf, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _wb(self, url, **kw):
        self.urls.append(url)
        for needle, raw in self.answers.items():
            if needle in url:
                return raw
        if "/indicator?source=" in url:
            source = int(url.split("source=")[1].split("&")[0])
            return json.dumps([{"pages": 1}, CATALOGUE.get(source, [])]).encode()
        if "/country?format=json" in url:
            return json.dumps([{"pages": 1}, COUNTRIES]).encode()
        if "/country/WLD/indicator/" in url:
            return json.dumps([{}, self.series]).encode()
        if "/country/all/indicator/" in url:
            return json.dumps([{}, [{"countryiso3code": "USA", "value": 3.0,
                                     "date": "2020"}]]).encode()
        raise AssertionError(f"unexpected URL {url}")

    def _used(self):
        return json.loads(sf.USED.read_text()) if sf.USED.exists() else {}

    def _forge(self, n=1):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            made = sf.forge(n)
        return made, out.getvalue()

    def _fetched(self, iid):
        return [u for u in self.urls if f"/indicator/{iid}?" in u]


class NoAnswerIsNotAVerdict(ForgeCase):
    def test_a_timeout_banks_nothing_and_is_said_out_loud(self):
        self.answers[f"/indicator/{LE}?"] = None          # no bytes at all
        made, log = self._forge(1)
        self.assertEqual(made, 1, log)
        used = self._used()
        self.assertNotIn(LE, used["unusable"],
                         "a fetch that failed says nothing about the series")
        self.assertNotIn(LE, used["indicators"])
        self.assertIn("NO ANSWER", log)
        self.assertIn("will be drawn again", log)

    def test_a_page_that_is_not_json_is_no_answer_either(self):
        self.answers[f"/indicator/{LE}?"] = b"<html>503 Service Unavailable"
        made, log = self._forge(1)
        self.assertNotIn(LE, self._used()["unusable"])
        self.assertIn("unreadable answer", log)
        self.assertIn("NO ANSWER", log)

    def test_the_next_run_asks_again(self):
        self.answers[f"/indicator/{LE}?"] = None
        self._forge(1)
        self.urls.clear()
        self.answers.clear()
        self._forge(1)
        self.assertTrue(self._fetched(LE), "an unanswered indicator is drawn again")

    def test_a_flat_series_is_still_unusable(self):
        """The right verdict is unchanged: fetched, judged, no story."""
        self.answers[f"/indicator/{LE}?"] = json.dumps([{}, FLAT]).encode()
        self.answers[f"/country/all/indicator/{LE}?"] = json.dumps(
            [{}, [{"countryiso3code": "USA", "value": 3.0, "date": "2020"}]]).encode()
        self._forge(1)
        self.assertIn(LE, self._used()["unusable"])

    def test_no_country_list_stops_the_run_before_it_judges(self):
        self.answers["/country?format=json"] = None
        made, log = self._forge(1)
        self.assertEqual(made, 0)
        self.assertFalse(sf.USED.exists(), "nothing judged, nothing remembered")
        self.assertIn("did not answer", log)
        self.assertFalse([u for u in self.urls if "/indicator/" in u],
                         "no series was fetched on a run with no country list")

    def test_one_retry_before_giving_up(self):
        calls = {"n": 0}
        real = self._wb

        def flaky(url, **kw):
            if f"/indicator/{LE}?" in url and "WLD" in url:
                calls["n"] += 1
                if calls["n"] == 1:
                    return None
            return real(url, **kw)
        with mock.patch.object(sf, "_get", flaky):
            made, log = self._forge(1)
        self.assertEqual(calls["n"], 2)
        self.assertIn(LE, self._used()["indicators"], "the retry answered")
        self.assertNotIn("NO ANSWER", log)


class AHeldStoryGivesItsDataBack(ForgeCase):
    def test_indicators_of_a_held_story_are_not_used(self):
        with mock.patch.object(sf, "_passes_editorial",
                               lambda s: (False, ["premise: flat fun fact"])):
            made, log = self._forge(1)
        self.assertEqual(made, 0)
        used = self._used()
        self.assertEqual(used["indicators"], [], "held on its words, not spent")
        self.assertEqual(used["unusable"], [])
        self.assertEqual(used["held"], {i: 1 for i in HEALTH})
        self.assertIn("HELD by editorial gate", log)

    def test_hold_strikes_retire_the_data(self):
        with mock.patch.object(sf, "_passes_editorial",
                               lambda s: (False, ["premise: no stake"])):
            for _ in range(sf.HOLD_STRIKES):
                self._forge(1)
        self.assertEqual(self._used()["held"][LE], sf.HOLD_STRIKES)
        self.urls.clear()
        made, log = self._forge(1)
        self.assertFalse(self._fetched(LE), "retired after HOLD_STRIKES holds")
        self.assertIn("EXHAUSTED", log)

    def test_a_kept_story_clears_the_strike(self):
        with mock.patch.object(sf, "_passes_editorial",
                               lambda s: (False, ["premise: x"])):
            self._forge(1)
        made, log = self._forge(1)
        self.assertEqual(made, 1)
        used = self._used()
        self.assertEqual(sorted(used["indicators"]), sorted(HEALTH))
        self.assertEqual(used["held"], {})

    def test_a_held_run_moves_the_rotation_on(self):
        """candidates() rotates by what was used; a run that used nothing
        would redraw the same set, so the strikes move it instead."""
        with mock.patch.object(sf, "wb_indicators", lambda: [
                {"id": f"SH.X{i}.A", "name": f"Hospital beds kind {i}", "source": 2}
                for i in range(4)]):
            first = [s["id"] for s in sf.candidates(set())["health"]]
            moved = [s["id"] for s in sf.candidates(set(), offset=2)["health"]]
        self.assertEqual(sorted(first), sorted(moved))
        self.assertNotEqual(first, moved)


class DataAlreadyInAStoryIsUsed(ForgeCase):
    def test_a_key_in_a_story_marks_its_indicator_used(self):
        key = sf._snake(f"{LE}_trend")
        sf.CONFIG.write_text(json.dumps({"stories": [
            {"slug": "old", "segments": [{"key": key}]}]}))
        self._forge(1)
        self.assertIn(LE, self._used()["indicators"])
        self.urls.clear()
        self._forge(1)
        self.assertFalse(self._fetched(LE), "never drawn again")


class TheWellReadsTheDoctrinesThemes(unittest.TestCase):
    CAT = [
        {"id": "VC.IHR.PSRC.P5", "name": "Intentional homicides (per 100,000 people)", "source": 2},
        {"id": "VC.BTL.DETH", "name": "Battle-related deaths (number of people)", "source": 2},
        {"id": "MS.MIL.XPND.GD.ZS", "name": "Military expenditure (% of GDP)", "source": 2},
        {"id": "SH.PRV.SMOK", "name": "Prevalence of current tobacco use (% of adults)", "source": 2},
        {"id": "IP.JRN.ARTC.SC", "name": "Scientific and technical journal articles", "source": 2},
        {"id": "EN.CLC.CDDY.XD", "name": "Cooling Degree Days", "source": 75},
        {"id": "EN.CLC.HEAT.XD", "name": "Heat Index 35", "source": 75},
        {"id": "AG.LND.FRLS.HA", "name": "Tree Cover Loss (hectares)", "source": 75},
        {"id": "IS.SHP.GCNW.XQ", "name": "Liner shipping connectivity index (maximum value in 2004 = 100)", "source": 2},
        {"id": "EN.CLC.DRSK.XQ", "name": "Disaster risk reduction progress score (1-5 scale; 5=best)", "source": 2},
        {"id": "SH.DTH.INJR.ZS", "name": "Cause of death, by injury (% of total)", "source": 2},
    ]

    def _topics(self):
        with mock.patch.object(sf, "wb_indicators", lambda: self.CAT):
            pool = sf.candidates(set())
        return {s["id"]: theme for theme, lst in pool.items() for s in lst}

    def test_crime_military_the_body_and_ideas_are_read(self):
        got = self._topics()
        self.assertEqual(got.get("VC.IHR.PSRC.P5"), "crime")
        self.assertEqual(got.get("VC.BTL.DETH"), "crime")
        self.assertEqual(got.get("MS.MIL.XPND.GD.ZS"), "military")
        self.assertEqual(got.get("SH.PRV.SMOK"), "health")
        self.assertEqual(got.get("IP.JRN.ARTC.SC"), "tech")
        self.assertEqual(got.get("EN.CLC.CDDY.XD"), "climate")
        self.assertEqual(got.get("AG.LND.FRLS.HA"), "nature")

    def test_an_index_or_a_score_is_an_analysts_construct(self):
        got = self._topics()
        self.assertNotIn("IS.SHP.GCNW.XQ", got)
        self.assertNotIn("EN.CLC.DRSK.XQ", got)
        self.assertNotIn("EN.CLC.HEAT.XD", got, "an index, even a hot one")

    def test_a_by_qualifier_keeps_its_comma_and_is_refused(self):
        self.assertEqual(sf._speakable("Cause of death, by injury"),
                         "Cause of death, by injury")
        self.assertNotIn("SH.DTH.INJR.ZS", self._topics())

    def test_the_state_file_carries_no_record_made_by_the_bug(self):
        """The 96 banked under the old None were reset on 2026-11-28; the
        fixed forge rebuilds the list from verdicts it actually reached."""
        rec = json.loads((REPO / "state" / "forge_used.json").read_text())
        self.assertIn("held", rec)
        self.assertIsInstance(rec["held"], dict)
        self.assertEqual(sf._load_used.__defaults__, None)
        self.assertNotIn("SP.DYN.LE00.IN", rec.get("unusable", []),
                         "life expectancy at birth is a story from 1972 on")


if __name__ == "__main__":
    unittest.main()
