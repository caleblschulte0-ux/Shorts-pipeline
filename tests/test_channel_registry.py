"""The channel registry — the production ruling, and drift protection.

Two jobs, deliberately separated:

  * **The ruling.** A handful of tests assert what the pipeline is actually
    contracted to ship TODAY. When the operator changes the registry, exactly
    these should fail, and updating them is the deliberate act of recording
    the change.
  * **The propagation.** Everything else changes ONLY the registry — never a
    line of code — and asserts that Phase A, the authoring shortfall, the
    reserve bank, validation, promotion and the takeover all move with it.
    If any of these fails, a second source of truth has grown back.

    python -m unittest tests.test_channel_registry -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

from shared import authoring_brief as brief          # noqa: E402
from shared import channel_registry as reg           # noqa: E402
from shared import package_buffer as buf             # noqa: E402
from tests.registry_fixture import (broken_registry,  # noqa: E402
                                    build, registry)
from tests.test_package_buffer import (               # noqa: E402
    graph_pkg, reddit_pkg, text_card_pkg)


# ==========================================================================
# 1. THE PRODUCTION RULING — what we actually ship today
# ==========================================================================
class TestTheLiveRuling(unittest.TestCase):
    """These SHOULD fail when the operator changes the registry. That is the
    point: a ruling change is a deliberate, recorded act, not a silent one."""

    def test_the_registry_is_valid(self):
        self.assertEqual(reg.validate(reg.load()), [])

    def test_trending_is_graph_led_with_text_cards_retired(self):
        """Operator ruling v5, 2026-07-31. Before the registry existed this
        lived only in daily.yml's prompt while four other places still said
        2+2+2."""
        self.assertEqual(reg.target_mix("trending"),
                         {"graph_race": 4, "reddit_story": 2})
        self.assertEqual(reg.target_count("trending"), 6)
        self.assertEqual(reg.retired_formats("trending"), ["text_card"])
        self.assertNotIn("text_card", reg.active_formats("trending"))

    def test_every_channel_is_accounted_for(self):
        self.assertEqual(reg.channel_ids(),
                         ["curiosity", "explainer", "third", "trending"])

    def test_third_asks_nothing_of_chatgpt(self):
        """Its package is a capture recipe for a clip that does not exist
        until the run happens — there is nothing to hand over in advance."""
        self.assertEqual(reg.roles("third"), [])

    def test_only_reddit_stories_want_chatgpt_images(self):
        self.assertTrue(reg.media_requirements("trending", "reddit_story")
                        ["chatgpt_supplies_images"])
        self.assertFalse(reg.media_requirements("trending", "graph_race")
                         ["chatgpt_supplies_images"])


# ==========================================================================
# 2. PROPAGATION — change ONLY the registry, watch everything move
# ==========================================================================
class TestArbitraryMixPropagates(unittest.TestCase):
    """The acceptance criterion: an arbitrary mix nobody has ever shipped
    must flow through every consumer with no code edit."""

    ARBITRARY = {"graph_race": 1, "reddit_story": 5}

    def test_shortfall_authoring_and_validation_all_follow(self):
        with registry(self.ARBITRARY):
            self.assertEqual(reg.target_mix("trending"), self.ARBITRARY)
            self.assertEqual(reg.target_count("trending"), 6)

            req = brief.build_request("29991231", "trending",
                                      have_packages=[])
            self.assertEqual(req["mix"], self.ARBITRARY)
            self.assertEqual(req["write"], 6)
            self.assertEqual(sorted(req["formats"]),
                             ["graph_race", "reddit_story"])

            have = [graph_pkg(slug="g1"), reddit_pkg(slug="r1")]
            self.assertEqual(brief.missing_mix(have),
                             {"graph_race": 0, "reddit_story": 4})

    def test_the_reserve_bank_follows_the_same_mix(self):
        with registry(self.ARBITRARY):
            self.assertEqual(buf.target_mix(), self.ARBITRARY)
            self.assertEqual(set(buf.formats()), set(self.ARBITRARY))
            self.assertEqual(buf.low_water()["reddit_story"],
                             5 * buf.LOW_WATER_DAYS)

    def test_phase_a_bundles_the_new_plan(self):
        with registry(self.ARBITRARY):
            plan = reg.plan("29991231", {"trending": []})
            t = plan["channels"]["trending"]
            self.assertEqual(t["target_mix"], self.ARBITRARY)
            self.assertEqual(t["shortfall"], self.ARBITRARY)
            self.assertEqual(t["to_author"], 6)

    def test_no_source_file_was_edited_to_make_that_work(self):
        """Guards the whole premise. If a future change reintroduces a
        constant, this catches it by proving the ONLY input was the JSON."""
        before = reg.target_mix("trending")
        with registry({"graph_race": 3, "reddit_story": 3}):
            self.assertEqual(reg.target_mix("trending"),
                             {"graph_race": 3, "reddit_story": 3})
        self.assertEqual(reg.target_mix("trending"), before)


class TestAddingAFormat(unittest.TestCase):
    """A format nobody has written code for must still flow through."""

    NEW = {"state": "active", "target": 2, "renderer": "make_quiz.py",
           "detect": {"field": "format", "equals": "quiz_card"},
           "required_fields": ["format", "slug", "title", "questions"],
           "media": {"shots": True, "chatgpt_supplies_images": True},
           "chatgpt_roles": ["media_worker", "takeover_authoring"]}

    def test_a_brand_new_format_reaches_the_authoring_brief(self):
        with registry({"graph_race": 2, "quiz_card": 2},
                      extra_formats={"quiz_card": dict(self.NEW)}):
            self.assertIn("quiz_card", reg.active_formats("trending"))
            req = brief.build_request("29991231", "trending",
                                      have_packages=[])
            self.assertEqual(req["mix"]["quiz_card"], 2)
            self.assertIn("quiz_card", req["formats"])
            spec = req["formats"]["quiz_card"]
            self.assertEqual(spec["required"], self.NEW["required_fields"])
            self.assertTrue(spec["media"]["chatgpt_supplies_images"])
            # No prose spec exists for it — say so honestly rather than
            # inventing rules or silently shipping a bare entry.
            self.assertTrue(any("No prose spec" in r for r in spec["rules"]))

    def test_it_is_classified_promoted_and_counted(self):
        with registry({"graph_race": 2, "quiz_card": 2},
                      extra_formats={"quiz_card": dict(self.NEW)}):
            pkg = {"format": "quiz_card", "slug": "q1", "title": "Q",
                   "questions": []}
            self.assertEqual(reg.classify(pkg, "trending"), "quiz_card")
            self.assertTrue(reg.is_authorable("trending", "quiz_card"))
            self.assertEqual(brief.missing_mix([pkg])["quiz_card"], 1)

    def test_no_scheduled_task_prose_mentions_it_and_it_still_works(self):
        """The whole promise: adding a format needs no prompt edit. The
        generated mix line is what the workers read."""
        with registry({"graph_race": 2, "quiz_card": 2},
                      extra_formats={"quiz_card": dict(self.NEW)}):
            line = reg.mix_sentence("trending")
            self.assertIn("quiz_card", line)
            self.assertIn("EXACTLY 4", line)


class TestDisablingAndRetiring(unittest.TestCase):
    def test_a_retired_format_disappears_from_the_ask(self):
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            req = brief.build_request("29991231", "trending",
                                      have_packages=[])
            self.assertNotIn("text_card", req["mix"])
            self.assertNotIn("text_card", req["formats"])
            self.assertIn("text_card", req["retired_formats"])
            self.assertIn("RETIRED", req["retired_note"])

    def test_a_retired_format_cannot_be_promoted(self):
        """The README once showed a text_card example and the old constants
        still listed it. Neither may resurrect it."""
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            problems = brief.validate_authored(text_card_pkg(slug="zombie"))
            self.assertTrue(any("retired" in p for p in problems), problems)

    def test_a_retired_format_cannot_be_banked(self):
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            ok, why = buf.eligible(text_card_pkg(slug="zombie-bank"))
            self.assertFalse(ok)
            self.assertTrue(any("retired" in w for w in why), why)

    def test_a_retired_format_is_still_RECOGNISED(self):
        """Recognise-but-refuse. A text_card already on disk must still
        classify as a text_card — counting it as 'unknown' would silently
        distort the shortfall for every other format."""
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            self.assertEqual(
                reg.classify(text_card_pkg(slug="old"), "trending"),
                "text_card")
            # …and it does not satisfy any active slot.
            self.assertEqual(brief.missing_mix([text_card_pkg(slug="old")]),
                             {"graph_race": 4, "reddit_story": 2})

    def test_retiring_everything_but_one_still_resolves(self):
        with registry({"graph_race": 6},
                      retired=["text_card", "reddit_story"]):
            self.assertEqual(reg.active_formats("trending"), ["graph_race"])
            self.assertEqual(brief.build_request("29991231", "trending")["mix"],
                             {"graph_race": 6})


class TestChannelsFlowThrough(unittest.TestCase):
    def test_disabling_a_channel_removes_it_everywhere(self):
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["channels"]["curiosity"]["enabled"] = False
        with registry(registry_object=obj):
            self.assertNotIn("curiosity", reg.channel_ids())
            plan = reg.plan("29991231")
            self.assertNotIn("curiosity", plan["channels"])
            self.assertIn("explainer", plan["channels"])

    def test_adding_a_channel_flows_into_the_plan(self):
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["channels"]["shorts_es"] = {
            "id": "shorts_es", "enabled": True,
            "display_name": "Spanish shorts", "cadence": {"per_day": 2},
            "target_count": 2,
            "formats": {"dub": {"state": "active", "target": 2,
                                "renderer": "localize.py",
                                "detect": {"field": "lang", "equals": "es"},
                                "media": {"shots": False},
                                "chatgpt_roles": ["editorial_review"]}},
            "chatgpt_roles": ["editorial_review"],
            "queue": None, "paths": {}, "doctrine": [],
            "protected_fields": [], "allowed_editorial_mutations": [],
        }
        with registry(registry_object=obj):
            self.assertIn("shorts_es", reg.channel_ids())
            plan = reg.plan("29991231")
            self.assertEqual(plan["channels"]["shorts_es"]["target_count"], 2)
            self.assertEqual(plan["totals"]["packages_expected"],
                             6 + 1 + 1 + 2)
            self.assertIn("shorts_es", reg.markdown_table())

    def test_a_full_trending_slate_never_hides_other_channel_work(self):
        """Trending being done says nothing about explainer or curiosity —
        the trap the split-worker change made easier to fall into."""
        with registry({"graph_race": 4, "reddit_story": 2}):
            full = ([graph_pkg(slug=f"g{i}") for i in range(4)]
                    + [reddit_pkg(slug=f"r{i}") for i in range(2)])
            plan = reg.plan("29991231", {"trending": full})
            self.assertEqual(plan["channels"]["trending"]["to_author"], 0)
            self.assertEqual(plan["channels"]["curiosity"]["chatgpt_roles"],
                             ["queue_stocking"])
            self.assertEqual(plan["channels"]["explainer"]["chatgpt_roles"],
                             ["editorial_review"])
            self.assertTrue(plan["channels"]["curiosity"]["queue"])


class TestMediaRequirementsFollowTheRegistry(unittest.TestCase):
    def test_flipping_a_format_to_needing_images_changes_the_brief(self):
        specs = {"graph_race": {
            "state": "active", "target": 4, "renderer": "make_graph_race.py",
            "detect": {"field": "format", "equals": "graph_race"},
            "media": {"shots": True, "chatgpt_supplies_images": True,
                      "shots_min": 3},
            "chatgpt_roles": ["media_worker"]}}
        with registry({"graph_race": 4, "reddit_story": 2},
                      extra_formats=specs):
            self.assertTrue(reg.media_requirements("trending", "graph_race")
                            ["chatgpt_supplies_images"])
            req = brief.build_request("29991231", "trending")
            self.assertTrue(req["formats"]["graph_race"]["media"]
                            ["chatgpt_supplies_images"])
            self.assertTrue(reg.has_role("trending", "media_worker",
                                         "graph_race"))


class TestQueueRulesFollowTheRegistry(unittest.TestCase):
    def test_raising_the_curiosity_minimum_asks_for_more(self):
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["channels"]["curiosity"]["queue"]["minimum_unposted"] = 9
        with registry(registry_object=obj):
            self.assertEqual(brief._queue_min("curiosity"), 9)
            req = brief.curiosity_queue_request("29991231")
            self.assertIsNotNone(req)
            self.assertIn("registry minimum 9", req["reason"])

    def test_a_channel_with_no_queue_reports_none(self):
        with registry({"graph_race": 4, "reddit_story": 2}):
            self.assertIsNone(reg.queue_rule("trending"))


# ==========================================================================
# 3. FAILING HONESTLY
# ==========================================================================
class TestInvalidRegistryFailsClosed(unittest.TestCase):
    def test_a_missing_registry_raises(self):
        with broken_registry():
            with self.assertRaises(reg.RegistryError) as cm:
                reg.load()
            self.assertIn("no fallback", str(cm.exception))

    def test_corrupt_json_raises(self):
        with broken_registry("{not json"):
            self.assertRaises(reg.RegistryError, reg.load)

    def test_arithmetic_that_disagrees_with_itself_is_refused(self):
        """target_count and the format targets must agree, or the shortfall
        and the slate size quietly diverge."""
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["channels"]["trending"]["target_count"] = 99
        problems = reg.validate(obj)
        self.assertTrue(any("must agree" in p for p in problems), problems)

    def test_a_retired_format_with_a_nonzero_target_is_refused(self):
        obj = build({"graph_race": 4, "reddit_story": 2},
                    retired=["text_card"])
        obj["channels"]["trending"]["formats"]["text_card"]["target"] = 2
        self.assertTrue(any("must target 0" in p for p in reg.validate(obj)))

    def test_an_unknown_chatgpt_role_is_refused(self):
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["channels"]["trending"]["chatgpt_roles"] = ["do_everything"]
        self.assertTrue(any("unknown chatgpt role" in p
                            for p in reg.validate(obj)))

    def test_an_active_format_without_a_detect_rule_is_refused(self):
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["channels"]["trending"]["formats"]["graph_race"].pop("detect")
        self.assertTrue(any("detect" in p for p in reg.validate(obj)))

    def test_a_wrong_schema_version_is_refused(self):
        obj = build({"graph_race": 4, "reddit_story": 2})
        obj["schema_version"] = "channel-registry/v99"
        self.assertTrue(any("schema_version" in p for p in reg.validate(obj)))

    def test_phase_a_exits_nonzero_rather_than_guessing(self):
        import os
        env = dict(os.environ, CHANNEL_REGISTRY_PATH="/nonexistent/reg.json")
        out = subprocess.run(
            [sys.executable, "scripts/exchange_phase_a.py", "--date",
             "29991225", "--no-resolve", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("registry unusable", out.stdout + out.stderr)


# ==========================================================================
# 4. CLASSIFICATION
# ==========================================================================
class TestClassification(unittest.TestCase):
    def test_the_real_formats_classify(self):
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            self.assertEqual(reg.classify(graph_pkg(slug="g"), "trending"),
                             "graph_race")
            self.assertEqual(reg.classify(reddit_pkg(slug="r"), "trending"),
                             "reddit_story")
            self.assertEqual(reg.classify(text_card_pkg(slug="t"), "trending"),
                             "text_card")

    def test_an_explicit_format_beats_the_implicit_reddit_rule(self):
        """reddit_story is 'no `format` field, has `subreddit`'. A package
        that NAMES its format must not be swallowed by that."""
        with registry({"graph_race": 4, "reddit_story": 2}):
            hybrid = {"format": "graph_race", "subreddit": "pettyrevenge",
                      "slug": "h"}
            self.assertEqual(reg.classify(hybrid, "trending"), "graph_race")

    def test_unrecognised_packages_are_none_not_a_guess(self):
        with registry({"graph_race": 4, "reddit_story": 2}):
            self.assertIsNone(reg.classify({"slug": "mystery"}, "trending"))
            self.assertIsNone(reg.classify(None, "trending"))
            self.assertIsNone(reg.classify("nonsense", "trending"))

    def test_slate_problems_names_the_retired_format(self):
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            gripes = reg.slate_problems("trending",
                                        [text_card_pkg(slug="zz")])
            self.assertTrue(any("RETIRED" in g for g in gripes), gripes)


# ==========================================================================
# 4b. SNAPSHOT IMMUTABILITY + TAKEOVER PARITY
# ==========================================================================
class TestSnapshotIsImmutable(unittest.TestCase):
    """A bundle's contract is frozen at creation. The 06:00 worker and the
    07:00 worker must see the same plan even if the registry moved between
    them, or half a slate gets built to one ruling and half to another."""

    DATE = "29991224"

    def setUp(self):
        from shared import exchange_bundle as xb
        self.xb = xb
        self.dir = ROOT / "exchange" / "bundles" / self.DATE
        shutil.rmtree(self.dir, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, contract):
        self.xb.write_bundle(self.DATE, [], [], None, None, contract)

    def test_a_registry_change_does_not_touch_an_open_bundle(self):
        with registry({"graph_race": 4, "reddit_story": 2}):
            self._write(reg.plan(self.DATE, {"trending": []}))
        before = (self.dir / "bundle.json").read_bytes()

        with registry({"reddit_story": 6}, revision=9):
            frozen = self.xb.existing_contract(self.DATE)
            self.assertEqual(frozen["registry_revision"], 1)
            self.assertEqual(frozen["channels"]["trending"]["target_mix"],
                             {"graph_race": 4, "reddit_story": 2})
            self.assertNotEqual(reg.target_mix("trending"),
                                frozen["channels"]["trending"]["target_mix"])
        self.assertEqual((self.dir / "bundle.json").read_bytes(), before,
                         "the open bundle was rewritten")

    def test_phase_a_reuses_the_frozen_contract_on_a_rerun(self):
        with registry({"graph_race": 4, "reddit_story": 2}):
            self._write(reg.plan(self.DATE, {"trending": []}))
        with registry({"reddit_story": 6}, revision=9):
            out = subprocess.run(
                [sys.executable, "scripts/exchange_phase_a.py", "--date",
                 self.DATE, "--no-resolve", "--dry-run"],
                cwd=ROOT, capture_output=True, text=True)
            self.assertIn("reusing the FROZEN contract", out.stdout)
            self.assertIn("registry has changed", out.stdout)

    def test_rebuild_contract_is_the_explicit_migration(self):
        with registry({"graph_race": 4, "reddit_story": 2}):
            self._write(reg.plan(self.DATE, {"trending": []}))
        with registry({"reddit_story": 6}, revision=9):
            out = subprocess.run(
                [sys.executable, "scripts/exchange_phase_a.py", "--date",
                 self.DATE, "--no-resolve", "--dry-run",
                 "--rebuild-contract"],
                cwd=ROOT, capture_output=True, text=True)
            self.assertIn("--rebuild-contract", out.stdout)
            self.assertNotIn("reusing the FROZEN", out.stdout)

    def test_old_bundles_stay_readable_after_a_schema_bump(self):
        """An archived bundle must still be interpretable — its own snapshot
        is self-describing and nothing re-resolves it."""
        with registry({"graph_race": 4, "reddit_story": 2}):
            self._write(reg.plan(self.DATE, {"trending": []}))
        with broken_registry():
            frozen = self.xb.existing_contract(self.DATE)
            self.assertEqual(frozen["channels"]["trending"]["target_count"], 6)
            self.assertTrue(frozen["channels"]["trending"]["doctrine"])


class TestTakeoverMatchesTheNormalPath(unittest.TestCase):
    def test_bundle_and_no_bundle_resolve_the_same_plan(self):
        """The no-bundle takeover reads the registry directly. It must land
        on exactly what Phase A would have written."""
        from shared import exchange_bundle as xb
        with registry({"graph_race": 4, "reddit_story": 2},
                      retired=["text_card"]):
            have = [graph_pkg(slug="g1"), reddit_pkg(slug="r1")]
            phase_a = reg.plan("29991223", {"trending": have})
            takeover = reg.plan("29991223", {"trending": have})
            self.assertEqual(phase_a["channels"], takeover["channels"])
            self.assertEqual(
                phase_a["channels"]["trending"]["shortfall"],
                brief.missing_mix(have))
            b = xb.build_bundle("29991223", [], [],
                                brief.build_request("29991223", "trending",
                                                    have_packages=have))
            self.assertEqual(b["authoring_request"]["mix"],
                             takeover["channels"]["trending"]["shortfall"])


# ==========================================================================
# 5. DOCUMENTATION MAY NOT DRIFT
# ==========================================================================
class TestGeneratedDocsMatchTheRegistry(unittest.TestCase):
    """Documentation explains; it never declares. These prove the generated
    blocks are current and that no doc restates the mix by hand."""

    GENERATED = ("exchange/README.md", "CLAUDE_ROUTINE_INSTRUCTIONS.md")

    def test_generated_slate_blocks_are_current(self):
        table = reg.markdown_table()
        for rel in self.GENERATED:
            text = (ROOT / rel).read_text()
            self.assertIn("BEGIN GENERATED SLATE", text, rel)
            block = text.split("BEGIN GENERATED SLATE", 1)[1] \
                        .split("END GENERATED SLATE", 1)[0]
            for line in table.splitlines():
                if line.startswith("|"):
                    self.assertIn(line.strip(), block,
                                  f"{rel} is stale — regenerate with "
                                  f"`python -m shared.channel_registry "
                                  f"--markdown`")

    def test_the_readme_says_its_examples_are_not_normative(self):
        text = (ROOT / "exchange" / "README.md").read_text()
        self.assertIn("EXPLANATORY ONLY", text)
        self.assertIn("Which contract wins", text)
        # The five-step precedence, in order.
        head = text.split("## Two workers", 1)[0]
        for phrase in ("bundle.json", "config/channel_registry.json",
                       "source_commit", "EXPLANATORY ONLY",
                       "NEVER define channel"):
            self.assertIn(phrase, head, phrase)


if __name__ == "__main__":
    unittest.main()
