"""Enrichment's work has to survive as far as the judge.

Doctor finding 4e9af949a9c9. `funnel.entity_media` identified an entity,
disambiguated it with context, resolved a URL through Wikipedia/Commons/GDELT
and verified the URL was a live image — and then persisted `shot.image_url`
and nothing else. The production judge path is `judge_package(pkg, None)`
(exchange_phase_a, registry_acceptance and exchange_dry_run all call it that
way), whose fallback deliberately builds `{"url": ...}` — so entity, context,
dimensions, source class and provenance were all gone before scoring.

Measured on the real scorer:

    bare pinned URL                          0.133  weak
    verified, subject confirmed by provider  0.817  strong
    verified only, no subject claim          0.317  weak

A verified encyclopedic photo of the named subject scored 0.133 and was
downgraded to weak, which orders a generated replacement for it.

The line these tests defend is WHOSE claim the evidence is. `_media_for`
refuses to synthesize a candidate title from the shot's own phrase, because
scoring text against itself guarantees ~100% overlap regardless of what the
image shows. `media_evidence` is admissible for the opposite reason: it
records the entity we asked a provider for and the provider answered. A
routine-supplied URL that merely got verified carries no `title` at all — it
earns the resolution and provenance credit it evidenced, and none of the
subject credit it did not.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from funnel import entity_media as em                    # noqa: E402
from funnel import media_judge as mj                     # noqa: E402

URL = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Apple_Park.jpg"
SCRIPT = "Apple Inc unveiled it at Apple Park this morning."


def _score(shot: dict) -> tuple[str, float]:
    r = mj.judge_package({"title": "t", "script": SCRIPT, "shots": [shot]},
                         None)["verdicts"][0]
    return r["verdict"], r["score"]


def _shot(**over) -> dict:
    base = {"phrase": "Apple Inc unveiled it", "query": "apple hq",
            "image_url": URL}
    base.update(over)
    return base


FULL_EV = {"url": URL, "title": "Apple Inc", "query": "tech company",
           "source_class": "open_or_licensed", "provider": "wikimedia",
           "width": 1600, "height": 1200, "resolved_by": "entity_media"}


class TheJudgeCanSeeWhatWasVerified(unittest.TestCase):
    def test_a_bare_pinned_url_is_still_unverified(self):
        """Unchanged, and it must stay unchanged.

        Not asserted against an absolute number: `_media_text` reads the URL
        itself, so a filename that happens to contain the subject already
        scores a little overlap. What matters is that a bare URL stays weak
        and stays well below the same URL WITH evidence."""
        verdict, score = _score(_shot())
        self.assertEqual(verdict, "weak")
        self.assertLess(score, _score(_shot(media_evidence=FULL_EV))[1] - 0.3)

    def test_resolved_and_verified_media_is_judged_on_its_evidence(self):
        verdict, score = _score(_shot(media_evidence=FULL_EV))
        self.assertEqual(verdict, "strong", score)
        self.assertGreater(score, 0.6)

    def test_verification_alone_does_not_buy_subject_relevance(self):
        """A routine URL we confirmed is a live 1600x1200 Wikimedia image.
        That is worth the resolution and provenance credit and nothing
        else — nobody has said it depicts Apple."""
        ev = {k: v for k, v in FULL_EV.items() if k != "title"}
        ev["resolved_by"] = "verify_shot_urls"
        verdict, score = _score(_shot(media_evidence=ev))
        self.assertEqual(verdict, "weak", score)
        self.assertGreater(score, 0.2, "verified provenance earned nothing")
        self.assertLess(score, 0.6, "verification alone certified the subject")


class EvidenceCannotBeForged(unittest.TestCase):
    def test_evidence_for_a_different_url_is_ignored(self):
        ev = dict(FULL_EV, url="https://elsewhere.example/other.jpg")
        self.assertEqual(_score(_shot(media_evidence=ev)),
                         _score(_shot()))

    def test_junk_in_the_field_is_ignored(self):
        for junk in ("a string", 7, [], None):
            with self.subTest(junk=junk):
                self.assertEqual(_score(_shot(media_evidence=junk)),
                                 _score(_shot()))

    def test_no_url_means_no_media_however_much_evidence(self):
        shot = _shot(media_evidence=FULL_EV)
        shot.pop("image_url")
        verdict, _ = _score(shot)
        self.assertEqual(verdict, "missing")

    def test_the_judge_still_refuses_to_read_the_shots_own_phrase(self):
        """The rule `media_evidence` is an exception to, not a repeal of."""
        src = (ROOT / "funnel" / "media_judge.py").read_text()
        self.assertIn("Never synthesize title/query from the shot's own", src)


class EnrichmentWritesItDown(unittest.TestCase):
    def test_enrich_package_persists_the_evidence(self):
        pkg = {"title": "Apple unveils", "script": SCRIPT,
               "shots": [{"phrase": "Apple Inc unveiled it",
                          "query": "apple hq"}]}
        with mock.patch.object(em, "extract_visuals_llm",
                               return_value=[{"entity": "Apple Inc",
                                              "context": "tech company",
                                              "phrase": "Apple Inc unveiled it"}]), \
             mock.patch.object(em, "resolve_entity_evidence",
                               return_value=dict(FULL_EV)), \
             mock.patch.object(em, "verify_shot_urls", return_value=0):
            em.enrich_package(pkg, verbose=False)
        shot = pkg["shots"][0]
        self.assertEqual(shot["image_url"], URL)
        self.assertEqual(shot["media_evidence"]["title"], "Apple Inc")

    def test_end_to_end_enrichment_then_judging(self):
        """The case the finding asked for: from enrich_package straight into
        the production judge call, with no media_by_shot."""
        pkg = {"title": "Apple unveils", "script": SCRIPT,
               "shots": [{"phrase": "Apple Inc unveiled it",
                          "query": "apple hq"}]}
        with mock.patch.object(em, "extract_visuals_llm",
                               return_value=[{"entity": "Apple Inc",
                                              "context": "tech company",
                                              "phrase": "Apple Inc unveiled it"}]), \
             mock.patch.object(em, "resolve_entity_evidence",
                               return_value=dict(FULL_EV)), \
             mock.patch.object(em, "verify_shot_urls", return_value=0):
            em.enrich_package(pkg, verbose=False)
        report = mj.judge_package(pkg, None)
        self.assertEqual(report["verdicts"][0]["verdict"], "strong",
                         report["verdicts"][0]["reasons"])
        self.assertEqual(report["gaps"], [],
                         "a verified entity image was ordered replaced")

    def test_a_dropped_url_takes_its_evidence_with_it(self):
        """Evidence must never outlive the URL it describes."""
        pkg = {"shots": [{"phrase": "p", "image_url": URL,
                          "media_evidence": dict(FULL_EV)}]}
        with mock.patch.object(em, "probe_image",
                               return_value={"ok": False, "content_type": "",
                                             "width": 0, "height": 0,
                                             "verified_at": ""}):
            em.verify_shot_urls(pkg, verbose=False)
        self.assertNotIn("media_evidence", pkg["shots"][0])
        self.assertNotIn("image_url", pkg["shots"][0])

    def test_verification_writes_evidence_without_a_subject_claim(self):
        pkg = {"shots": [{"phrase": "Apple Inc unveiled it",
                          "image_url": URL}]}
        with mock.patch.object(em, "probe_image",
                               return_value={"ok": True,
                                             "content_type": "image/jpeg",
                                             "width": 1600, "height": 1200,
                                             "verified_at": "2026-09-09T00:00:00Z"}):
            em.verify_shot_urls(pkg, verbose=False)
        ev = pkg["shots"][0]["media_evidence"]
        self.assertNotIn("title", ev, "a verified URL certified its own subject")
        self.assertEqual(ev["width"], 1600)
        self.assertEqual(ev["source_class"], "open_or_licensed")


class TheProbeReportsWhatItSaw(unittest.TestCase):
    def test_host_classification_is_conservative(self):
        self.assertEqual(em._classify_host(URL)[0], "open_or_licensed")
        self.assertEqual(
            em._classify_host("https://news.example/og.jpg")[0], "unverified")
        self.assertEqual(em._classify_host("not a url at all")[0], "unverified")

    def test_url_is_image_still_answers_yes_or_no(self):
        """It delegates to probe_image now — one verification path, not two."""
        with mock.patch.object(em, "probe_image",
                               return_value={"ok": True, "content_type": "image/png",
                                             "width": 0, "height": 0,
                                             "verified_at": ""}):
            self.assertTrue(em.url_is_image(URL))
        with mock.patch.object(em, "probe_image",
                               return_value={"ok": False, "content_type": "",
                                             "width": 0, "height": 0,
                                             "verified_at": ""}):
            self.assertFalse(em.url_is_image(URL))

    def test_unparseable_dimensions_stay_zero_not_guessed(self):
        """The judge treats unknown dimensions as unverified rather than as
        big enough, so zero is the honest answer and a guess would be worse
        than none."""
        self.assertEqual(em._dims(b"not an image"), {})


if __name__ == "__main__":
    unittest.main()
