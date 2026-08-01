"""Tests for the takeover across EVERY channel, not just trending.

The operator's rule: the exchange IS the signal. If Claude worked, no
channel appears in `authoring_requests`; if a channel appears, Claude left
it nothing and ChatGPT is that channel's brain today.

Each channel's ask is a different shape, and each has a different way to be
dangerous:

  trending    author whole packages   -> structural gate (test_authoring_takeover)
  explainer   rewrite WORDS only      -> the numbers are World Bank data and
                                         MUST NOT MOVE; punchup_guard enforces
  curiosity   stock the queue         -> no duplicate slugs, required fields
  third       nothing to ask for      -> its package is a capture recipe for a
                                         clip that does not exist yet

    python -m unittest tests.test_multichannel_takeover -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from shared import authoring_brief as brief          # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
import ingest_authored as ing                        # noqa: E402


# --------------------------------------------------------------------------
# These tests are about MECHANISM, not about today's operator ruling. They run
# against a fixture registry carrying the mix they were written for, so a
# future mix change in config/channel_registry.json breaks only the tests that
# are ABOUT the ruling (tests/test_channel_registry.py) instead of these.
# --------------------------------------------------------------------------
from tests.registry_fixture import LEGACY_MIX, registry   # noqa: E402

_FIXTURE = None


def setUpModule():
    global _FIXTURE
    _FIXTURE = registry(LEGACY_MIX)
    _FIXTURE.__enter__()


def tearDownModule():
    if _FIXTURE is not None:
        _FIXTURE.__exit__(None, None, None)


def story(slug="debt-trap", words_by="deterministic", says=None) -> dict:
    return {
        "slug": slug, "words_by": words_by,
        "title": f"{slug.title()} Beats Everyone On Some Metric",
        "hook": "A number goes up.", "closing": "The numbers were public.",
        "question": "Which surprised you?",
        "segments": [{"say": s} for s in (says or [
            "Kenya spent 34 percent of revenue on debt in 2023.",
            "That is up from 12 percent in 2010."])],
    }


class ChannelTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mc-"))
        # Redirect through the module's test seam rather than rebinding
        # module constants — the paths themselves now come from the registry.
        self._saved = xb.BUNDLE_ROOT
        brief.PATH_OVERRIDES.update({
            ("explainer", "config"): self.tmp / "niche.config.json",
            ("curiosity", "config"): self.tmp / "curiosity.config.json",
            ("explainer", "posted_log"): self.tmp / "explainer_posted_log.json",
            ("curiosity", "posted_log"): self.tmp / "curiosity_posted_log.json",
        })
        xb.BUNDLE_ROOT = self.tmp / "bundles"
        xb.bundle_dir("20260801").mkdir(parents=True)

    def tearDown(self):
        brief.PATH_OVERRIDES.clear()
        xb.BUNDLE_ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_niche(self, stories):
        brief._cfg_path("explainer").write_text(json.dumps({"stories": stories}))

    def write_curiosity(self, stories):
        brief._cfg_path("curiosity").write_text(json.dumps({"stories": stories}))

    def respond(self, **body):
        (xb.bundle_dir("20260801") / "response.json").write_text(
            json.dumps(body))


class TestTheSignal(ChannelTestCase):
    """Claude working = no channel in the bundle. That IS the detection."""

    def test_healthy_channels_ask_for_nothing(self):
        self.write_niche([story(words_by="brain")])
        self.write_curiosity([story(f"c{i}") for i in range(5)])
        self.assertEqual(brief.all_requests("20260801"), {})

    def test_a_channel_appears_only_when_claude_left_it_nothing(self):
        self.write_niche([story(words_by="deterministic")])
        self.write_curiosity([story(f"c{i}") for i in range(5)])
        reqs = brief.all_requests("20260801")
        self.assertEqual(set(reqs), {"explainer"})
        self.assertEqual(reqs["explainer"]["job"], "rewrite_words")

    def test_drained_curiosity_queue_asks_for_stock(self):
        self.write_niche([story(words_by="brain")])
        self.write_curiosity([story("only-one")])
        reqs = brief.all_requests("20260801")
        self.assertEqual(set(reqs), {"curiosity"})
        self.assertEqual(reqs["curiosity"]["write"],
                         brief._queue_min("curiosity") - 1)

    def test_already_posted_stories_do_not_count_as_queue(self):
        self.write_niche([story(words_by="brain")])
        self.write_curiosity([story("posted-one"), story("posted-two")])
        brief.CURIOSITY_LOG.write_text(json.dumps(
            {"posted": [{"slug": "posted-one"}, {"slug": "posted-two"}]}))
        self.assertIn("curiosity", brief.all_requests("20260801"))

    def test_bundle_carries_every_channel_in_one_file(self):
        self.write_niche([story(words_by="deterministic")])
        self.write_curiosity([])
        reqs = brief.all_requests(
            "20260801", brief.build_request("20260801", "trending"))
        b = xb.build_bundle("20260801", [], [], reqs.get("trending"), reqs)
        self.assertEqual(b["mode"], "author")
        self.assertEqual(set(b["authoring_requests"]),
                         {"trending", "explainer", "curiosity"})
        self.assertEqual(b["counts"]["channels_needing_a_brain"], 3)

    def test_third_is_never_asked_for(self):
        """Its package is a capture recipe — the clip it will title does not
        exist until the run happens."""
        self.write_niche([story(words_by="deterministic")])
        self.write_curiosity([])
        self.assertNotIn("third", brief.all_requests("20260801"))


class TestExplainerWords(ChannelTestCase):
    """The numbers are World Bank data. Words may change; numbers may not."""

    def test_clean_rewrite_is_applied(self):
        self.write_niche([story()])
        self.respond(authored_explainer=[{
            "slug": "debt-trap",
            "title": "Kenya Now Spends A Third Of Its Money On Debt",
            "hook": "Kenya hands over 34 percent of every shilling it "
                    "collects before it spends a cent on anything else.",
            "closing": "It was public the whole time.",
            "says": ["Kenya spent 34 percent of revenue on debt in 2023.",
                     "Back in 2010 that figure was just 12 percent."]}])
        rep = ing.ingest_explainer("20260801")
        self.assertEqual(rep["applied"], ["debt-trap"])
        cfg = json.loads(brief.NICHE_CONFIG.read_text())
        s = cfg["stories"][0]
        self.assertEqual(s["words_by"], "chatgpt-takeover")
        self.assertIn("Third Of Its Money", s["title"])

    def test_a_changed_NUMBER_is_rejected_outright(self):
        self.write_niche([story()])
        self.respond(authored_explainer=[{
            "slug": "debt-trap", "title": "T", "hook": "H", "closing": "C",
            "says": ["Kenya spent 84 percent of revenue on debt in 2023.",
                     "That is up from 12 percent in 2010."]}])
        rep = ing.ingest_explainer("20260801")
        self.assertEqual(rep["applied"], [])
        self.assertEqual(rep["rejected"][0]["slug"], "debt-trap")

    def test_a_dropped_entity_is_rejected(self):
        self.write_niche([story()])
        self.respond(authored_explainer=[{
            "slug": "debt-trap", "title": "T", "hook": "H", "closing": "C",
            "says": ["The country spent 34 percent of revenue on debt in 2023.",
                     "That is up from 12 percent in 2010."]}])
        self.assertEqual(ing.ingest_explainer("20260801")["applied"], [])

    def test_wrong_segment_count_is_rejected(self):
        self.write_niche([story()])
        self.respond(authored_explainer=[{
            "slug": "debt-trap", "title": "T", "hook": "H", "closing": "C",
            "says": ["Only one line."]}])
        rep = ing.ingest_explainer("20260801")
        self.assertIn("1 says for 2 segments",
                      " ".join(rep["rejected"][0]["problems"]))

    def test_unknown_slug_is_rejected(self):
        self.write_niche([story()])
        self.respond(authored_explainer=[{"slug": "not-a-story",
                                          "says": [], "title": "T"}])
        self.assertEqual(ing.ingest_explainer("20260801")["applied"], [])

    def test_a_rejected_story_keeps_its_original_words(self):
        """A bad rewrite must not half-apply — the story still ships, just
        with the deterministic words it already had."""
        self.write_niche([story()])
        before = json.loads(brief.NICHE_CONFIG.read_text())["stories"][0]
        self.respond(authored_explainer=[{
            "slug": "debt-trap", "title": "T", "hook": "H", "closing": "C",
            "says": ["Kenya spent 99 percent on debt in 2023.", "x"]}])
        ing.ingest_explainer("20260801")
        after = json.loads(brief.NICHE_CONFIG.read_text())["stories"][0]
        self.assertEqual(before, after)

    def test_nothing_offered_is_a_clean_no_op(self):
        self.write_niche([story()])
        self.respond()
        self.assertEqual(ing.ingest_explainer("20260801")["offered"], 0)


class TestCuriosityQueue(ChannelTestCase):
    def test_clean_story_is_queued(self):
        self.write_curiosity([])
        self.respond(authored_curiosity=[{
            "slug": "why-ice-is-slippery", "title": "T", "hook": "H",
            "closing": "C", "question": "Q", "hashtags": ["#a"],
            "segments": [{"say": "x"}]}])
        rep = ing.ingest_curiosity("20260801")
        self.assertEqual(rep["applied"], ["why-ice-is-slippery"])
        cfg = json.loads(brief.CURIOSITY_CONFIG.read_text())
        self.assertEqual(cfg["stories"][0]["words_by"], "chatgpt-takeover")

    def test_missing_required_field_is_rejected(self):
        self.write_curiosity([])
        self.respond(authored_curiosity=[{"slug": "half-baked",
                                          "title": "T"}])
        rep = ing.ingest_curiosity("20260801")
        self.assertEqual(rep["applied"], [])
        self.assertIn("missing hook", " ".join(rep["rejected"][0]["problems"]))

    def test_duplicate_slug_is_rejected(self):
        self.write_curiosity([{"slug": "already-here"}])
        self.respond(authored_curiosity=[{
            "slug": "already-here", "title": "T", "hook": "H", "closing": "C",
            "segments": [{"say": "x"}]}])
        self.assertEqual(ing.ingest_curiosity("20260801")["applied"], [])

    def test_path_traversal_slug_is_sanitised(self):
        self.write_curiosity([])
        self.respond(authored_curiosity=[{
            "slug": "../../etc/passwd", "title": "T", "hook": "H",
            "closing": "C", "segments": [{"say": "x"}]}])
        ing.ingest_curiosity("20260801")
        cfg = json.loads(brief.CURIOSITY_CONFIG.read_text())
        if cfg["stories"]:
            self.assertNotIn("/", cfg["stories"][0]["slug"])

    def test_dry_run_writes_nothing(self):
        self.write_curiosity([])
        self.respond(authored_curiosity=[{
            "slug": "dry-one", "title": "T", "hook": "H", "closing": "C",
            "segments": [{"say": "x"}]}])
        ing.ingest_curiosity("20260801", dry_run=True)
        self.assertEqual(
            json.loads(brief.CURIOSITY_CONFIG.read_text())["stories"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestGuardStillCatchesRealEntities(unittest.TestCase):
    """Widening _COMMON_CAPS to cover sentence openers must not blind the
    guard to an actual dropped or invented name."""

    def test_sentence_opening_brand_is_still_an_entity(self):
        from shared import punchup_guard as g
        self.assertIn("spacex", g.proper_nouns("SpaceX just caught a booster."))
        self.assertIn("kenya", g.proper_nouns("Kenya spent 34 percent."))

    def test_ordinary_opener_is_not_an_entity(self):
        from shared import punchup_guard as g
        for opener in ("Back in 2010 it was lower.",
                       "Despite that, it grew.",
                       "Nearly half of them left."):
            self.assertEqual(
                g.proper_nouns(opener), set(),
                f"{opener!r} produced a phantom entity")

    def test_dropping_a_real_name_is_still_rejected(self):
        from shared import punchup_guard as g
        ok, why = g.check(
            {"script": "Kenya spent 34 percent of revenue on debt.",
             "shots": []},
            {"script": "The country spent 34 percent of revenue on debt."})
        self.assertFalse(ok)
        self.assertIn("kenya", " ".join(why).lower())

    def test_inventing_a_real_name_is_still_rejected(self):
        from shared import punchup_guard as g
        ok, why = g.check(
            {"script": "The country spent 34 percent.", "shots": []},
            {"script": "Kenya spent 34 percent."})
        self.assertFalse(ok)
