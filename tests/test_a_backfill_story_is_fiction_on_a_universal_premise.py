"""A BACKFILL STORY IS FICTION ON A UNIVERSAL PREMISE - NEVER THE NEWS.

2026-09-22, four trending backfills in one afternoon, four blocks at 18-22:
"a fabricated first-person 'cousin sold missiles' story laid over a real
geopolitical headline", "a fabricated first-person 'cover-up' story about a
real terror attack ... misinformation risk", two ticker topics told as drama
over brand photos. Every one was authored by `shared/script_generator` from
a topic the ranker picked for a NEWS channel, under a prompt that said "use
the topic as loose inspiration for the drama". The registry defines a
reddit_story as an ORIGINAL story on a UNIVERSAL premise; the backfill is
the one author that did not read that definition.

Held here:
  * the writer's prompt IS the registry's reddit_story spec (every rule, the
    subreddit list) - no second copy;
  * a topic about death, violence, war, crime or politics is refused before
    a word is written, and the backfill skips it before a render is spent;
  * a story that names the real news fails validation, is retried with the
    names spelled out, and is refused if it still names them;
  * the writer's own {"unusable": ...} answer is a refusal, not a package;
  * the package that comes back is a reddit_story (subreddit, slug,
    hashtags) so it never falls through to the retired stacked renderer.

    python -m unittest tests.test_a_backfill_story_is_fiction_on_a_universal_premise -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

from shared import authoring_brief                        # noqa: E402
from shared import script_generator as SG                # noqa: E402
import run_trending_daily as rtd                          # noqa: E402

SPEC = authoring_brief.FORMAT_SPECS["reddit_story"]

_SCRIPT = (
    "My manager told me to void every refund that came in after 5 pm, so I "
    "started printing the policy on the receipts. Two weeks in, a woman "
    "came back with a 300 dollar blender and a receipt that said, in my "
    "handwriting, that refunds close at 5. She asked for the manager. He "
    "walked over, read his own rule out loud, and told her the store would "
    "happily make an exception for her. I rang it through. Then I printed "
    "the exception onto the next 40 receipts, word for word, with his name "
    "on it. By Friday there were 40 people at the counter holding his "
    "exception. Head office called at noon. He is now on the register and "
    "I am on the schedule he used to write, and the first thing I did was "
    "put the refund window back to 8 pm.")


def _pkg(**over) -> dict:
    d = {"subreddit": "MaliciousCompliance",
         "title": "My Manager Wrote The Rule That Demoted Him",
         "script": _SCRIPT,
         "hashtags": ["maliciouscompliance", "retail"],
         "shots": [{"phrase": p, "query": "cash register"} for p in
                   ["void every refund", "printing the policy", "a woman came",
                    "read his own rule", "40 people at the counter",
                    "Head office called"]],
         "punches": [{"phrase": "void every refund", "text": "VOID", "color": "#ff3030"},
                     {"phrase": "his own rule", "text": "HIS RULE", "color": "#ffaa30"},
                     {"phrase": "Head office called", "text": "BUSTED", "color": "#50ff80"}],
         "music_vibe": "dark"}
    d.update(over)
    return d


class ThePromptIsTheRegistrysSpec(unittest.TestCase):
    def test_every_registry_rule_is_in_the_system_prompt(self):
        sp = SG.system_prompt()
        for rule in SPEC["rules"]:
            self.assertIn(rule, sp)
        for sub in SPEC["subreddit_options"]:
            self.assertIn(sub, sp)

    def test_the_module_keeps_no_copy_of_the_rules(self):
        src = (ROOT / "shared" / "script_generator.py").read_text()
        self.assertNotIn("NO weddings", src)
        self.assertNotIn("pettyrevenge", src)
        self.assertIn('FORMAT_SPECS["reddit_story"]', src)

    def test_the_user_prompt_says_the_trend_is_a_setting_not_a_story(self):
        up = SG.USER_PROMPT_TEMPLATE
        self.assertIn("THE TREND IS A SETTING, NOT A STORY", up)
        self.assertIn('"unusable"', up)
        self.assertNotIn("loose inspiration", up)
        self.assertNotIn("relationship", up.lower())


class ATragedyIsNotAStorySeed(unittest.TestCase):
    def test_the_refusal_list(self):
        for t in ("Sri Lanka terror verdict", "Iran must stop arming Houthis",
                  "school shooting leaves 3 dead", "hurricane flooding Texas",
                  "senate election results"):
            self.assertIsNotNone(SG.unfit_for_fiction(t), t)
        for t in ("coffee price record", "landlord deposit dispute",
                  "tesla recall", "hardware store paint colours"):
            self.assertIsNone(SG.unfit_for_fiction(t), t)

    def test_generate_refuses_before_calling_any_brain(self):
        with mock.patch.object(SG, "_call_llm") as llm:
            with self.assertRaises(SG.UnfitTopic):
                SG.generate("Sri Lanka terror verdict", ["Court rules on 2019 attack"])
            llm.assert_not_called()

    def test_the_writers_own_unusable_answer_is_a_refusal(self):
        with mock.patch.object(SG, "_call_llm",
                               return_value='{"unusable": "a real hostage crisis"}') as llm:
            with self.assertRaises(SG.UnfitTopic):
                SG.generate("border standoff", ["Talks stall at the border"])
        self.assertEqual(llm.call_count, 1)

    def test_the_backfill_skips_it_before_a_render_is_spent(self):
        authored = []

        class T:
            def __init__(self, q, heads=()):
                self.query, self.headlines, self.angle = q, list(heads), None

        def fake_run_one(topic, publish_at, *, dry_run, no_schedule):
            authored.append(topic.query)
            return {"ok": True, "format": "reddit_story"}

        class A:
            count, dry_run, no_schedule = 6, False, True

        results = [{"ok": True}] * 4 + [{"ok": False, "blocked": True}] * 2
        topics = [T("Sri Lanka terror verdict"), T("coffee price record"),
                  T("quiet town", ["Gunman opens fire at the fair"]),
                  T("hardware store paint colours")]
        with mock.patch.object(rtd, "discover_all", lambda: topics), \
                mock.patch.object(rtd, "run_one", fake_run_one), \
                mock.patch.object(rtd.rank_topics, "rank",
                                  lambda raw, top_k=0: list(raw)[:top_k]), \
                mock.patch.object(rtd, "posted_titles", lambda: set()):
            out = rtd._backfill(results, A(), [None] * 8, None, {})
        self.assertEqual(authored, ["coffee price record",
                                    "hardware store paint colours"])
        self.assertEqual(len(out), 2)

    def test_run_one_reports_a_refusal_without_rendering(self):
        class T:
            query, headlines, snippets, angle = "Sri Lanka terror verdict", [], [], None
        with mock.patch.object(rtd, "_research"), \
                mock.patch.object(rtd, "_render_package") as render:
            r = rtd.run_one(T(), None, dry_run=False, no_schedule=True)
        self.assertFalse(r["ok"])
        self.assertTrue(r["unfit"])
        self.assertIn("unfit_for_fiction", r["error"])
        render.assert_not_called()


class TheStoryNeverNamesTheNews(unittest.TestCase):
    def test_real_entities_are_the_mid_sentence_capitals_of_prose(self):
        names = SG.real_entities(
            "tesla passed toyota",
            ["Tesla passed Toyota in market value, Reuters says"],
            ["The carmaker Tesla overtook Toyota on Monday, a price record "
             "for the sector."])
        self.assertEqual(names, {"tesla", "toyota", "reuters"})

    def test_a_title_case_headline_flags_no_ordinary_word(self):
        names = SG.real_entities(
            "coffee price record", ["Coffee Price Record Hits $8 A Pound"],
            ["Arabica prices hit a record as a pound of beans passed 8 dollars."])
        self.assertEqual(names, set())

    def test_a_lowercase_query_is_the_subject_not_evidence(self):
        names = SG.real_entities(
            "tesla recall", ["Tesla Recalls 2M Cars"],
            ["The recall covers cars built since 2021, Tesla said on Monday."])
        self.assertIn("tesla", names)

    def test_a_story_that_names_the_news_fails_validation(self):
        bad = _pkg(script=_SCRIPT.replace("a woman came back", "a woman from Tesla came back"))
        issues = SG._validate_package(bad, {"tesla", "toyota"})
        self.assertTrue(any("names the real news" in i and "tesla" in i for i in issues))
        self.assertEqual([i for i in SG._validate_package(_pkg(), {"tesla", "toyota"})
                          if "real news" in i], [])

    def test_generate_retries_with_the_names_spelled_out_then_refuses(self):
        bad = _pkg(title="How Tesla Fired My Manager")
        calls = []

        def llm(system, user, **kw):
            calls.append(user)
            return json.dumps(bad)

        with mock.patch.object(SG, "_call_llm", side_effect=llm):
            with self.assertRaises(SG.UnfitTopic):
                SG.generate("tesla recall", ["Tesla Recalls 2M Cars"],
                            ["Tesla said on Monday the recall covers 2 million cars."],
                            max_retries=2)
        self.assertEqual(len(calls), 3)
        self.assertIn("tesla", calls[1])
        self.assertIn("names the real news", calls[1])

    def test_a_clean_story_ships_as_a_reddit_story(self):
        with mock.patch.object(SG, "_call_llm", return_value=json.dumps(_pkg())):
            pkg = SG.generate("tesla recall", ["Tesla Recalls 2M Cars"],
                              ["Tesla said on Monday the recall covers 2 million cars."])
        self.assertEqual(pkg["subreddit"], "MaliciousCompliance")
        self.assertEqual(pkg["topic"], "tesla recall")
        self.assertTrue(pkg["slug"])
        self.assertTrue(pkg["hashtags"])
        self.assertNotIn("format", pkg)


class ThePackageIsAlwaysARedditStory(unittest.TestCase):
    def test_a_missing_subreddit_is_an_issue_and_then_filled_out_loud(self):
        issues = SG._validate_package(_pkg(subreddit=None))
        self.assertTrue(any("subreddit" in i for i in issues))
        no_sub = _pkg(); del no_sub["subreddit"]
        import io, contextlib
        err = io.StringIO()
        with mock.patch.object(SG, "_call_llm", return_value=json.dumps(no_sub)), \
                contextlib.redirect_stderr(err):
            pkg = SG.generate("hardware store paint", [], [], max_retries=0)
        self.assertIn(pkg["subreddit"], SPEC["subreddit_options"])
        self.assertIn("subreddit", err.getvalue())

    def test_the_renderer_routes_a_subreddit_package_to_the_reddit_story(self):
        with mock.patch.dict(sys.modules, {"make_reddit_story": mock.MagicMock()}) as mods:
            rtd._render_package(_pkg(), Path("/tmp/x.mp4"))
            mods["make_reddit_story"].build_reddit_story.assert_called_once()


if __name__ == "__main__":
    unittest.main()
