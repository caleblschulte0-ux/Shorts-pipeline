"""A QUEUE OF HELD STORIES IS NOT A FULL QUEUE.

2026-09-07..11-20: `data_learning/niche.config.json` held 73 un-posted
explainer stories and the posting run held every one of them — 34 on
non-official data, the rest on premise, currency or repetition. The story
forge's twice-daily top-up compared that 73 to a target of 10, printed
"queue already full — nothing to forge" and exited green; the authoring
brief did the same arithmetic. The channel posted nothing for want of
stories while two tools agreed it had too many.

Held here:
  * `shared/queue_supply.postable` is the one measure of supply: un-posted
    stories MINUS the ones the most recent real posting run held, read from
    `state/explainer_runs.json`;
  * the forge's `--top-up` forges against THAT number, and says its
    arithmetic out loud;
  * the authoring brief's top-up reads the same measure;
  * a story the last run never saw is supply (it has not failed); a dry
    run's holds do not count; no record at all discounts nothing;
  * the posted log is read, never written.
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

from shared import queue_supply as qs                       # noqa: E402
from scripts import story_forge as sf                       # noqa: E402

HELD = ["helium-supply-squeeze", "measles-ninety-five-rule",
        "volcano-country-ranking", "usps-mail-volume-collapse",
        "ocean-floor-vs-mars-mapped"]
FRESH = "brand-new-story-nobody-judged"


def _cfg(slugs):
    return {"stories": [{"slug": s, "segments": []} for s in slugs]}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="supply-"))
        self.posted = self.tmp / "posted.json"
        self.runs = self.tmp / "runs.json"
        self.posted.write_text(json.dumps(
            {"posted": {"already-posted": {"at": "2026-11-01T00:00:00Z"}}}))
        self.runs.write_text(json.dumps({"runs": [
            {"ts": "2026-11-20T10:00:00+00:00", "dry_run": False,
             "posted": [], "held": {"editorial_hold": HELD[:3],
                                    "not_current": [HELD[3]],
                                    "duplicate_hold": [HELD[4]]}},
        ]}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def supply(self, cfg):
        return qs.postable(cfg, posted_log=self.posted, runs_path=self.runs)


class TheMeasureIsSupply(Fixture):
    def test_every_held_story_is_discounted(self):
        got = self.supply(_cfg(HELD + ["already-posted"]))
        self.assertEqual(got["unposted"], 5)
        self.assertEqual(got["held"], 5)
        self.assertEqual(got["postable"], [])

    def test_a_story_the_last_run_never_saw_is_supply(self):
        got = self.supply(_cfg(HELD + [FRESH]))
        self.assertEqual(got["postable"], [FRESH])
        self.assertEqual(got["held"], 5)

    def test_a_posted_story_is_neither_stock_nor_supply(self):
        got = self.supply(_cfg(["already-posted"]))
        self.assertEqual(got, {"unposted": 0, "held": 0, "postable": []})

    def test_the_last_REAL_run_is_read_not_a_rehearsal(self):
        runs = json.loads(self.runs.read_text())
        runs["runs"].append({"ts": "2026-11-20T11:00:00+00:00",
                             "dry_run": True, "posted": [], "held": {}})
        self.runs.write_text(json.dumps(runs))
        self.assertEqual(qs.held_by_last_run(self.runs), set(HELD))

    def test_only_the_most_recent_run_counts(self):
        runs = json.loads(self.runs.read_text())
        runs["runs"].append({"ts": "2026-11-20T12:00:00+00:00",
                             "dry_run": False, "posted": [HELD[0]],
                             "held": {"editorial_hold": HELD[1:]}})
        self.runs.write_text(json.dumps(runs))
        self.assertEqual(qs.held_by_last_run(self.runs), set(HELD[1:]))

    def test_no_record_discounts_nothing(self):
        self.runs.unlink()
        got = self.supply(_cfg(HELD))
        self.assertEqual(len(got["postable"]), 5)
        self.assertEqual(got["held"], 0)

    def test_a_malformed_record_discounts_nothing(self):
        self.runs.write_text("not json")
        self.assertEqual(qs.held_by_last_run(self.runs), set())
        self.runs.write_text(json.dumps({"runs": [{"dry_run": False,
                                                   "held": None}]}))
        self.assertEqual(qs.held_by_last_run(self.runs), set())

    def test_the_arithmetic_is_said_out_loud(self):
        line = qs.describe(self.supply(_cfg(HELD + [FRESH])), 10)
        self.assertIn("un-posted queue: 6", line)
        self.assertIn("5 held by the last posting run", line)
        self.assertIn("postable 1", line)
        self.assertIn("target 10", line)

    def test_the_posted_log_is_never_written(self):
        before = self.posted.read_text()
        self.supply(_cfg(HELD))
        qs.held_by_last_run(self.runs)
        self.assertEqual(self.posted.read_text(), before)


class TheForgeTopsUpAgainstSupply(Fixture):
    """The exact 2026-11-20 shape: every un-posted story held, target 10.
    The old `--top-up` forged 0 here."""

    def setUp(self):
        super().setUp()
        self.cfg = self.tmp / "niche.config.json"
        self.cfg.write_text(json.dumps(_cfg(HELD + ["already-posted"])))
        self._saved = {k: getattr(sf, k) for k in
                       ("CONFIG", "POSTED_LOG", "RUNS")}
        sf.CONFIG, sf.POSTED_LOG, sf.RUNS = self.cfg, self.posted, self.runs

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(sf, k, v)
        super().tearDown()

    def _main(self, *argv):
        calls = []
        out = io.StringIO()
        with mock.patch.object(sf, "forge",
                               lambda n, dry_run=False: calls.append(n) or n), \
                mock.patch.object(sys, "argv", ["story_forge.py", *argv]), \
                contextlib.redirect_stdout(out):
            rc = sf.main()
        return rc, calls, out.getvalue()

    def test_a_queue_the_posting_run_holds_is_topped_up(self):
        rc, calls, log = self._main("--top-up", "10")
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [10], "five un-posted stories, all held, "
                         "are no supply: the forge owes the full target")
        self.assertIn("5 held by the last posting run", log)
        self.assertIn("postable 0", log)
        self.assertNotIn("already full", log)

    def test_a_fresh_story_counts_toward_the_target(self):
        cfg = json.loads(self.cfg.read_text())
        cfg["stories"].append({"slug": FRESH, "segments": []})
        self.cfg.write_text(json.dumps(cfg))
        rc, calls, log = self._main("--top-up", "3")
        self.assertEqual(calls, [2])
        self.assertIn("postable 1", log)

    def test_a_queue_of_postable_stories_is_full(self):
        self.runs.write_text(json.dumps({"runs": [
            {"ts": "x", "dry_run": False, "posted": [], "held": {}}]}))
        rc, calls, log = self._main("--top-up", "3")
        self.assertEqual(calls, [])
        self.assertIn("already full of POSTABLE stories", log)

    def test_count_still_forges_exactly_n(self):
        rc, calls, log = self._main("--count", "4")
        self.assertEqual(calls, [4])


class TheBriefReadsTheSameMeasure(unittest.TestCase):
    def test_author_stories_tops_up_against_postable(self):
        src = (REPO / "scripts" / "author_stories.py").read_text()
        self.assertIn("_postable_count", src)
        self.assertIn("queue_supply.postable", src)
        i = src.index("if args.top_up is not None:")
        self.assertIn("_postable_count(cfg)", src[i:i + 400],
                      "the brief's top-up compares POSTABLE, not raw un-posted")

    def test_the_forge_workflow_still_tops_up(self):
        wf = (REPO / ".github" / "workflows" / "story_forge.yml").read_text()
        self.assertIn("story_forge.py --top-up", wf)

    def test_the_alarm_names_the_cause(self):
        src = (REPO / "scripts" / "daily_alarm.py").read_text()
        self.assertIn("queue already full", src)
        self.assertIn("queue_supply", src)


if __name__ == "__main__":
    unittest.main()
