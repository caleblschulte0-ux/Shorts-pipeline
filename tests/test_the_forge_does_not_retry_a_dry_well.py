"""THE FORGE DOES NOT RETRY A DRY WELL.

2026-09-07..11-19: the story forge kept no story for ten weeks. With 66
World Bank (WDI) indicators used, the 32 on-doctrine indicators that
remained all failed its series filters — too few points, a flat line, no
spread — and every posting run drew the SAME 32, fetched them again,
printed "forged 0 real-data stories" and exited 0. Nothing remembered that
they had failed; nothing widened the well; nothing said so. The explainer
queue only shrank, and on 11-19 the channel posted nothing (eight runs, 74
holds, every story made to an older standard).

Held here:
  * an indicator whose series proved unusable is REMEMBERED in
    state/forge_used.json and never drawn again;
  * `updated` in that file still means "the last day a story was KEPT" —
    remembering a failure is not a heartbeat (daily_alarm reads it);
  * the catalogue is read from every World Bank database in WB_SOURCES,
    deduplicated, and a non-WDI indicator's data call carries `&source=`;
  * a run that writes nothing says so as a GitHub warning, and an exhausted
    catalogue says THAT, not "network?";
  * the posting workflow persists the story sidecars the scorecard writes.
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

WDI = "SP.DYN.LE00.IN"            # listed by WDI and by HNP — kept once, WDI
HNP = "SH.STA.OBES.ZS"            # only in Health Nutrition and Population
CATALOGUE = {
    2: [{"id": WDI, "name": "Life expectancy at birth (years)"}],
    16: [{"id": WDI, "name": "Life expectancy at birth (years)"},
         {"id": HNP, "name": "Obesity prevalence (% of adults)"}],
    12: [],
    75: [],
}
FLAT = [{"date": str(y), "value": 5.0} for y in range(2000, 2012)]


class ForgeCase(unittest.TestCase):
    """The forge against a fake World Bank: two health indicators, both
    flat at the world level and too thin to rank."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="forge-"))
        self.urls: list[str] = []
        self._saved = {k: getattr(sf, k) for k in
                       ("CACHE", "USED", "CONFIG", "LAST", "DATA_DIR",
                        "POSTED_LOG")}
        sf.CACHE = self.tmp / "cache"
        sf.USED = self.tmp / "state" / "forge_used.json"
        sf.LAST = self.tmp / "state" / "forge_last.json"
        sf.CONFIG = self.tmp / "niche.config.json"
        sf.DATA_DIR = self.tmp / "data"
        sf.POSTED_LOG = self.tmp / "state" / "posted.json"
        sf.CONFIG.write_text(json.dumps({"stories": []}))
        sf.USED.parent.mkdir(parents=True)
        self._patch = mock.patch.object(sf, "_get_json", self._wb)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        for k, v in self._saved.items():
            setattr(sf, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _wb(self, url, **kw):
        self.urls.append(url)
        if "/indicator?source=" in url:
            source = int(url.split("source=")[1].split("&")[0])
            return [{"pages": 1}, CATALOGUE.get(source, [])]
        if "/country?format=json" in url:
            return [{"pages": 1}, [
                {"id": "USA", "name": "United States",
                 "region": {"value": "North America"}},
                {"id": "FRA", "name": "France", "region": {"value": "Europe"}}]]
        if "/country/WLD/indicator/" in url:
            return [{}, FLAT]
        if "/country/all/indicator/" in url:
            return [{}, [{"countryiso3code": "USA", "value": 3.0,
                          "date": "2020"}]]
        raise AssertionError(f"unexpected URL {url}")

    def _used(self):
        return json.loads(sf.USED.read_text())

    def _forge(self, n=1):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            made = sf.forge(n)
        return made, out.getvalue()


class TheWellIsWiderThanWDI(ForgeCase):
    def test_every_database_in_WB_SOURCES_is_read_and_an_id_is_kept_once(self):
        inds = sf.wb_indicators()
        self.assertEqual([i["id"] for i in inds], [WDI, HNP])
        self.assertEqual({i["id"]: i["source"] for i in inds},
                         {WDI: 2, HNP: 16})
        self.assertIn(16, sf.WB_SOURCES, "Health Nutrition and Population")

    def test_a_non_WDI_indicator_asks_its_own_database(self):
        self._forge(1)
        trend = [u for u in self.urls if "/country/WLD/indicator/" in u]
        self.assertTrue(any(f"/{HNP}?" in u and "&source=16" in u
                            for u in trend), trend)
        self.assertTrue(any(f"/{WDI}?" in u and "source=" not in u
                            for u in trend), trend)
        rank = [u for u in self.urls if "/country/all/indicator/" in u]
        self.assertTrue(any(f"/{HNP}?" in u and "&source=16" in u
                            for u in rank), rank)


class ADryIndicatorIsRememberedNotRetried(ForgeCase):
    def test_a_series_that_is_no_story_is_written_down(self):
        sf.USED.write_text(json.dumps({"indicators": [], "updated": "2026-09-07"}))
        made, log = self._forge(1)
        self.assertEqual(made, 0)
        self.assertEqual(self._used()["unusable"], sorted([WDI, HNP]))
        self.assertEqual(self._used()["indicators"], [])

    def test_remembering_a_failure_is_not_a_heartbeat(self):
        sf.USED.write_text(json.dumps({"indicators": [], "updated": "2026-09-07"}))
        self._forge(1)
        self.assertEqual(self._used()["updated"], "2026-09-07",
                         "`updated` is the day a story was KEPT — "
                         "daily_alarm's forge_silent reads it")

    def test_the_next_run_does_not_fetch_them_again(self):
        self._forge(1)
        self.urls.clear()
        made, log = self._forge(1)
        self.assertEqual(made, 0)
        self.assertFalse([u for u in self.urls if "/indicator/" in u],
                         "a remembered indicator is never fetched again")
        self.assertIn("::warning::", log)
        self.assertIn("EXHAUSTED", log)
        self.assertNotIn("network?", log)

    def test_an_old_used_file_without_the_field_still_loads(self):
        sf.USED.write_text(json.dumps({"indicators": ["X"], "updated": "2026-09-07"}))
        self.assertEqual(sf._load_used()["unusable"], [])
        self.assertEqual(sf._load_used()["indicators"], ["X"])
        self.assertEqual(sf._load_used()["updated"], "2026-09-07")


class AnEmptyRunSaysSo(ForgeCase):
    def test_forging_nothing_is_a_github_warning(self):
        made, log = self._forge(1)
        self.assertEqual(made, 0)
        self.assertIn("::warning::[forge] wrote NOTHING", log)
        self.assertIn("2 indicator(s) are now remembered as unusable", log)

    def test_a_dry_run_writes_no_memory(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sf.forge(1, dry_run=True)
        self.assertFalse(sf.USED.exists())


class TheScorecardSidecarSurvivesTheRunner(unittest.TestCase):
    """shared/story_brief.write_sidecar writes state/story_sidecars/<slug>
    .json for every scored story — and until this test the explainer
    workflow's persist step did not name the directory, so every sidecar
    died with the runner while CLAUDE.md promised them."""

    def test_explainer_yml_persists_state_story_sidecars(self):
        yml = (REPO / ".github" / "workflows" / "explainer.yml").read_text()
        persist = [ln for ln in yml.splitlines()
                   if "ci_commit_state.sh" in ln or "state/scene_plans" in ln]
        self.assertTrue(persist)
        self.assertIn("state/story_sidecars", yml)
        self.assertTrue(any("state/story_sidecars" in ln
                            for ln in yml.splitlines()
                            if "state/scene_plans" in ln),
                        "the sidecars are persisted beside the scene plans")

    def test_the_sidecar_lands_where_the_workflow_persists(self):
        from shared import story_brief as sb
        tmp = Path(tempfile.mkdtemp(prefix="sidecar-"))
        try:
            out = sb.write_sidecar({"slug": "x", "segments": []}, root=tmp)
            self.assertEqual(out, tmp / "state" / "story_sidecars" / "x.json")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
