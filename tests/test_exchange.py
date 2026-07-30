"""Tests for the ChatGPT one-pass exchange: judge, bundle, punch-up guard.

Fully offline — no network, no ChatGPT, no Drive. The punch-up guard tests are
the important ones: they are what stop an external model inventing facts.

    python -m unittest tests.test_exchange -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from funnel import media_judge                      # noqa: E402
from shared import exchange_bundle as xb            # noqa: E402
from shared import punchup_guard                    # noqa: E402

PKG = {
    "slug": "spacex-catch",
    "title": "SpaceX Caught Starship Again",
    "script": ("SpaceX just caught Starship again. The booster came down at "
               "1,200 mph and stopped dead. That is 40% faster than the last "
               "attempt in 2025."),
    "shots": [
        {"phrase": "SpaceX just caught Starship again",
         "query": "SpaceX Starship rocket launch"},
        {"phrase": "The booster came down at 1,200 mph",
         "query": "rocket booster descent"},
        {"phrase": "That is 40% faster than the last attempt",
         "query": "graph comparison"},
    ],
}


class TestMediaJudge(unittest.TestCase):
    def test_missing_when_no_media(self):
        v = media_judge.judge_shot(PKG["shots"][0], None, script=PKG["script"])
        self.assertEqual(v["verdict"], "missing")
        self.assertIn("ai_prompt", v)
        self.assertTrue(v["ai_prompt"])

    def test_strong_when_on_topic_and_big(self):
        media = {"url": "https://x/starship.jpg",
                 "title": "SpaceX Starship booster catch at Starbase",
                 "width": 1600, "height": 1600,
                 "source_class": "open_or_licensed"}
        v = media_judge.judge_shot(PKG["shots"][0], media, script=PKG["script"])
        self.assertEqual(v["verdict"], "strong", v["reasons"])

    def test_generic_standin_is_weak(self):
        """The line names Starship; a generic rocket stock photo is not it."""
        media = {"url": "https://x/rocket.jpg", "title": "generic rocket sky",
                 "width": 1600, "height": 1600,
                 "source_class": "open_or_licensed"}
        v = media_judge.judge_shot(PKG["shots"][0], media, script=PKG["script"])
        self.assertEqual(v["verdict"], "weak")
        self.assertTrue(any("generic stand-in" in r for r in v["reasons"]))

    def test_low_resolution_penalized(self):
        media = {"url": "https://x/s.jpg",
                 "title": "SpaceX Starship booster catch", "width": 320,
                 "height": 240, "source_class": "open_or_licensed"}
        v = media_judge.judge_shot(PKG["shots"][0], media, script=PKG["script"])
        self.assertTrue(any("low resolution" in r for r in v["reasons"]))

    def test_ai_prompt_forbids_screenshots(self):
        p = media_judge.ai_prompt(PKG["shots"][0])
        for banned in ("no text", "no screenshots", "no user interfaces"):
            self.assertIn(banned, p)

    def test_judge_package_counts_and_gaps(self):
        rep = media_judge.judge_package(PKG, None)
        self.assertEqual(rep["shot_count"], 3)
        self.assertEqual(rep["counts"]["missing"], 3)
        self.assertEqual(len(rep["gaps"]), 3)

    def test_never_raises_on_garbage(self):
        self.assertEqual(media_judge.judge_shot({}, {"url": None})["verdict"],
                         "missing")
        self.assertEqual(media_judge.judge_package({})["shot_count"], 0)


class TestBundle(unittest.TestCase):
    def test_build_bundle_shape(self):
        rep = media_judge.judge_package(PKG, None)
        b = xb.build_bundle("20260730", [PKG], [rep])
        self.assertEqual(b["schema"], xb.SCHEMA)
        self.assertEqual(b["counts"]["packages"], 1)
        self.assertEqual(b["counts"]["requests"], 3)
        self.assertEqual(b["counts"]["animations"], 0)   # budget default 0
        self.assertIn("punchup_rules", b["instructions"])
        self.assertTrue(b["packages"][0]["script"])
        for req in b["requests"]:
            self.assertTrue(req["prompt_verbatim"])
            self.assertIn("screenshots", req["negative"])

    def test_request_key_is_stable_and_content_addressed(self):
        a = xb.request_key("slug", 1, "a prompt")
        b = xb.request_key("slug", 1, "a prompt")
        c = xb.request_key("slug", 1, "another prompt")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_animation_budget_env(self):
        os.environ[xb.ANIM_BUDGET_ENV] = "2"
        try:
            rep = media_judge.judge_package(PKG, None)
            b = xb.build_bundle("20260730", [PKG], [rep])
            self.assertEqual(b["counts"]["animations"], 2)
            anims = [r for r in b["requests"] if r["kind"] == "animation"]
            self.assertEqual(len(anims), 2)
            self.assertIn("frames", anims[0]["animation"])
        finally:
            os.environ.pop(xb.ANIM_BUDGET_ENV, None)

    def test_max_requests_cap(self):
        os.environ[xb.MAX_REQUESTS_ENV] = "2"
        try:
            rep = media_judge.judge_package(PKG, None)
            b = xb.build_bundle("20260730", [PKG], [rep])
            self.assertEqual(b["counts"]["requests"], 2)
        finally:
            os.environ.pop(xb.MAX_REQUESTS_ENV, None)

    def test_done_marker_is_date_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            orig = xb.BUNDLE_ROOT
            xb.BUNDLE_ROOT = Path(td)
            try:
                d = xb.bundle_dir("20260730")
                d.mkdir(parents=True)
                self.assertFalse(xb.is_done("20260730"))
                (d / "DONE").write_text(json.dumps({"date": "20260729"}))
                self.assertFalse(xb.is_done("20260730"))   # stale, wrong day
                (d / "DONE").write_text(json.dumps({"date": "20260730"}))
                self.assertTrue(xb.is_done("20260730"))
            finally:
                xb.BUNDLE_ROOT = orig

    def test_response_index(self):
        idx = xb.response_index({"media": [{"request_id": "r1"}],
                                 "packages": [{"slug": "s1"}]})
        self.assertIn("r1", idx["media"])
        self.assertIn("s1", idx["scripts"])
        self.assertEqual(xb.response_index(None)["media"], {})


class TestPunchupGuard(unittest.TestCase):
    def _rewrite(self, script, **kw):
        r = {"slug": PKG["slug"], "script": script,
             "shots": [dict(s) for s in PKG["shots"]]}
        r.update(kw)
        return r

    def test_wording_change_allowed(self):
        good = self._rewrite(
            "SpaceX caught Starship AGAIN. The booster screamed down at "
            "1,200 mph and stopped dead — 40% faster than its last try in 2025.")
        ok, problems = punchup_guard.check(PKG, good)
        self.assertTrue(ok, problems)
        merged = punchup_guard.apply(PKG, good)
        self.assertIsNotNone(merged)
        self.assertTrue(merged["punched_up"])
        self.assertEqual(len(merged["shots"]), 3)

    def test_invented_number_rejected(self):
        bad = self._rewrite(
            "SpaceX just caught Starship again. The booster came down at "
            "1,200 mph and stopped dead. That is 40% faster than the last "
            "attempt in 2025, saving $90 million per flight.")
        ok, problems = punchup_guard.check(PKG, bad)
        self.assertFalse(ok)
        self.assertTrue(any("INVENTED numeric" in p for p in problems), problems)
        self.assertIsNone(punchup_guard.apply(PKG, bad))

    def test_changed_number_rejected(self):
        bad = self._rewrite(
            "SpaceX just caught Starship again. The booster came down at "
            "2,500 mph and stopped dead. That is 40% faster than the last "
            "attempt in 2025.")
        ok, problems = punchup_guard.check(PKG, bad)
        self.assertFalse(ok)
        joined = " ".join(problems)
        self.assertTrue("INVENTED numeric" in joined or "dropped numeric" in joined)

    def test_invented_entity_rejected(self):
        bad = self._rewrite(
            "SpaceX just caught Starship again, and NASA confirmed it. The "
            "booster came down at 1,200 mph and stopped dead. That is 40% "
            "faster than the last attempt in 2025.")
        ok, problems = punchup_guard.check(PKG, bad)
        self.assertFalse(ok)
        self.assertTrue(any("INVENTED named entity" in p for p in problems),
                        problems)

    def test_shot_count_change_rejected(self):
        bad = self._rewrite(PKG["script"])
        bad["shots"] = bad["shots"][:2]
        ok, problems = punchup_guard.check(PKG, bad)
        self.assertFalse(ok)
        self.assertTrue(any("shot count changed" in p for p in problems))

    def test_shot_subject_change_rejected(self):
        bad = self._rewrite(PKG["script"])
        bad["shots"][0]["query"] = "completely different subject"
        ok, problems = punchup_guard.check(PKG, bad)
        self.assertFalse(ok)
        self.assertTrue(any("subject changed" in p for p in problems))

    def test_wholesale_rewrite_rejected(self):
        ok, problems = punchup_guard.check(PKG, self._rewrite("Too short."))
        self.assertFalse(ok)

    def test_empty_and_garbage_fail_closed(self):
        self.assertFalse(punchup_guard.check(PKG, {})[0])
        self.assertFalse(punchup_guard.check(PKG, {"script": ""})[0])
        self.assertFalse(punchup_guard.check(PKG, None)[0])

    def test_numeric_claim_extraction(self):
        claims = punchup_guard.numeric_claims(
            "It cost $1.2 million in 2024, up 15% from 900 units.")
        self.assertIn("2024", claims)
        self.assertIn("15%", claims)
        self.assertIn("900", claims)
        self.assertTrue(any("1.2" in c for c in claims))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestPunchupEmphasis(unittest.TestCase):
    """Re-casing an existing word for emphasis is a legitimate punch-up move
    and must NOT read as an invented entity (regression: 'caught' -> 'CAUGHT'
    was rejected)."""

    def test_emphasis_caps_allowed(self):
        orig = {"slug": "s", "script": "SpaceX just caught Starship again "
                                       "at 1,200 mph in 2025.",
                "shots": [{"phrase": "a", "query": "q"}]}
        new = {"slug": "s", "script": "SpaceX just CAUGHT Starship again "
                                      "at 1,200 mph in 2025.",
               "shots": [{"phrase": "a", "query": "q"}]}
        ok, problems = punchup_guard.check(orig, new)
        self.assertTrue(ok, problems)

    def test_real_invented_entity_still_caught(self):
        orig = {"slug": "s", "script": "SpaceX just caught Starship again "
                                       "at 1,200 mph in 2025.",
                "shots": [{"phrase": "a", "query": "q"}]}
        new = {"slug": "s", "script": "SpaceX just caught Starship again "
                                      "at 1,200 mph in 2025, per NASA.",
               "shots": [{"phrase": "a", "query": "q"}]}
        ok, problems = punchup_guard.check(orig, new)
        self.assertFalse(ok)
        self.assertTrue(any("INVENTED named entity" in p for p in problems))


class TestSelfFillContracts(unittest.TestCase):
    """The self-fill lanes call real funnel APIs. An earlier version GUESSED
    the signatures (find_images(query, limit=)) and silently filled nothing —
    the fallback looked like it ran and left every gap empty. Pin the real
    contracts so that cannot regress."""

    def test_media_funnel_search_signature(self):
        import inspect
        from funnel import media_funnel
        sig = inspect.signature(media_funnel.search)
        params = list(sig.parameters)
        self.assertEqual(params[0], "story_angle")
        self.assertEqual(params[1], "entities")
        self.assertIn("story_slug", sig.parameters)
        self.assertIn("verbose", sig.parameters)

    def test_topic_media_search_signature(self):
        import inspect
        from funnel import topic_media
        params = list(inspect.signature(topic_media.search).parameters)
        self.assertEqual(params[:2], ["topic", "context"])

    def test_entity_media_resolver_signature(self):
        import inspect
        from funnel import entity_media
        sig = inspect.signature(entity_media.resolve_entity_media)
        self.assertEqual(list(sig.parameters)[0], "entity")
        self.assertIn("context", sig.parameters)

    def test_candidate_exposes_url_and_score(self):
        from funnel.media_funnel import Candidate
        fields = getattr(Candidate, "__dataclass_fields__", {})
        self.assertIn("url", fields)
        self.assertIn("score", fields)

    def test_self_fill_never_raises_on_junk(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from exchange_phase_b import self_fill
        self.assertIsNone(self_fill({"shots": []}, 0))
        self.assertIsNone(self_fill({"shots": [{"query": ""}]}, 0))
        self.assertIsNone(self_fill({}, 5))


class TestPunchupBriefIsActionable(unittest.TestCase):
    """The bundle must tell ChatGPT what TO DO, not only what not to do.

    Regression: the first live run returned every script byte-identical.
    ChatGPT's own report said it played safe because the brief was five
    prohibitions and zero craft direction. A rewrite-nothing run is a failed
    run, so the positive brief is now part of the contract.
    """

    def _instructions(self):
        rep = media_judge.judge_package(PKG, None)
        return xb.build_bundle("20260730", [PKG], [rep])["instructions"]

    def test_mission_present_and_positive(self):
        m = self._instructions().get("punchup_mission")
        self.assertIsNotNone(m, "bundle lost its punch-up mission")
        for key in ("the_ask", "house_voice", "do_this",
                    "the_numbers_are_yours_to_use", "worked_example"):
            self.assertIn(key, m)
        self.assertGreaterEqual(len(m["do_this"]), 5)

    def test_rewrite_is_framed_as_editorial_decision(self):
        """Punch OR keep-with-reason — but never a silent skip. 'Always
        rewrite' was its own failure mode (change for change's sake);
        'no direction' produced zero rewrites. The contract is a stated
        per-package verdict."""
        blob = json.dumps(self._instructions()).lower()
        self.assertIn("unchanged with no stated reason", blob)
        self.assertIn("keeping is a", blob)          # keeping is legitimate
        self.assertIn("kept", blob)                   # the response field
        self.assertIn("editor_note", blob)
        self.assertIn("attitude is mandatory", blob)

    def test_worked_example_survives_its_own_guard(self):
        """If the example we teach would be REJECTED, we are teaching a
        failure. This caught a real guard bug: dropping 'Officials' read as
        removing a named entity, while the writing doctrine explicitly tells
        punch-ups to cut 'officials confirmed' hedging."""
        ex = self._instructions()["punchup_mission"]["worked_example"]
        shots = [{"phrase": "a", "query": "q"}]
        ok, problems = punchup_guard.check(
            {"slug": "x", "script": ex["before"], "shots": shots},
            {"slug": "x", "script": ex["after"], "shots": shots})
        self.assertTrue(ok, f"our own worked example is rejected: {problems}")

    def test_generic_role_nouns_are_not_entities(self):
        for word in ("officials", "authorities", "police", "residents",
                     "investigators", "witnesses", "tuesday"):
            self.assertNotIn(word, punchup_guard.proper_nouns(
                f"{word.capitalize()} said the thing happened."),
                f"{word!r} treated as a named entity")

    def test_real_entities_still_detected(self):
        found = punchup_guard.proper_nouns(
            "Officials in Marshall said NASA and SpaceX responded.")
        for real in ("marshall", "nasa", "spacex"):
            self.assertIn(real, found)
        self.assertNotIn("officials", found)
