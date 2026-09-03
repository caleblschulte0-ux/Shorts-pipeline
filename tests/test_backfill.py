"""A held slot is not a lost slot — but a backfill must never be a bypass.

Operator ruling 2026-08-05: *"if the video doesn't make it past the gates,
they get a new video going — nothing doesn't post."* And, the same day:
*"there shouldn't be a reserve bank. If something doesn't run properly, it
goes through and tries again."*

On 2026-08-05 trending rendered six and shipped one. The showrunner
correctly held five weak videos and the run simply ended. The gate was right
every time; the pipeline's mistake was treating a refusal as the end of the
slot instead of the start of another attempt.

The first fix drew replacements from a pre-stocked reserve bank. That was
retired the same day for a good reason: a shelf covers only as many failures
as somebody remembered to stock it for, and ours held two packages against a
low-water mark of twelve — it would have covered one bad slot and then been
empty for a week, while reading in every report like a safety net. So a
replacement is now AUTHORED FRESH: discovery, ranking, script, render.

The danger in any of this is obvious and it is the thing these tests exist
to prevent: a backfill that ships the video the gate just refused, or that
lowers the bar for the replacement, would be the bypass the doctrine
forbids. So the replacement goes through `run_one` — the exact same
research, render, technical QA, vision QA and showrunner path as the video
it replaces. Nothing here may ever change that.

    python -m unittest tests.test_backfill -v
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import run_trending_daily as rtd                        # noqa: E402


class Args:
    def __init__(self, count=6, dry_run=False, no_schedule=True):
        self.count = count
        self.dry_run = dry_run
        self.no_schedule = no_schedule


def res(ok, fmt="graph_race", blocked=False, quarantined=False):
    return {"ok": ok, "format": fmt, "blocked": blocked,
            "quarantined": quarantined, "error": None if ok else "held"}


class Topic:
    """The shape `discover_all()` yields and `run_one()` consumes."""

    def __init__(self, query):
        self.query = query
        self.angle = None

    def __repr__(self):                                  # nicer failures
        return f"Topic({self.query!r})"


class BackfillCase(unittest.TestCase):
    """Stub discovery and the renderer; assert on what backfill DOES."""

    def setUp(self):
        self.authored = []          # topics it actually tried to author
        self.now = __import__("datetime").datetime(2026, 8, 5)

    def run_backfill(self, results, topics, render_ok=True, count=6,
                     dry_run=False, posted=(), discovery_raises=False):
        def fake_discover():
            if discovery_raises:
                raise RuntimeError("feeds down")
            return [Topic(t) for t in topics]

        def fake_render(topic, publish_at, *, dry_run, no_schedule):
            self.authored.append(topic.query)
            ok = render_ok(topic) if callable(render_ok) else render_ok
            return res(ok, blocked=not ok)

        with mock.patch.object(rtd, "discover_all", fake_discover), \
                mock.patch.object(rtd, "run_one", fake_render), \
                mock.patch.object(rtd.rank_topics, "rank",
                                  lambda raw, top_k=0: list(raw)[:top_k]), \
                mock.patch.object(rtd, "posted_titles",
                                  lambda: {p.casefold() for p in posted}):
            return rtd._backfill(results, Args(count, dry_run), [None] * 8,
                                 self.now, {"posted": []})


class TestItRefillsHeldSlots(BackfillCase):
    def test_five_held_slots_pull_replacements(self):
        results = [res(True)] + [res(False, blocked=True) for _ in range(5)]
        out = self.run_backfill(results, [f"t{i}" for i in range(20)])
        self.assertEqual(len(out), min(5, rtd.MAX_BACKFILL))
        self.assertTrue(all(r["ok"] for r in out))
        self.assertTrue(all(r["backfill"] for r in out))

    def test_a_full_day_backfills_nothing(self):
        results = [res(True) for _ in range(6)]
        self.assertEqual(self.run_backfill(results, ["t0", "t1"]), [])
        self.assertEqual(self.authored, [])

    def test_a_quarantined_slot_counts_as_held(self):
        """The drama gate quarantines a weak chart BEFORE it renders. That
        empties a slot exactly as a showrunner BLOCK does, and it must
        trigger the same retry — this is the path a refused graph_race
        takes."""
        results = [res(False, quarantined=True)] + \
                  [res(True) for _ in range(5)]
        out = self.run_backfill(results, ["fresh"])
        self.assertEqual(len(out), 1)


class TestItIsNeverABypass(BackfillCase):
    """The tests that matter. A backfill that ships a held video, or judges
    the replacement more gently, is the bypass the doctrine forbids."""

    def _backfill_source(self) -> str:
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        return src.split("def _backfill(", 1)[1].split("\ndef ", 1)[0]

    def test_a_replacement_goes_through_the_SAME_render_and_gate_path(self):
        self.assertIn("run_one(", self._backfill_source(),
                      "the replacement must take the same path as any other "
                      "video — research, render, technical QA, vision QA, "
                      "showrunner")

    def test_backfill_never_touches_the_gate(self):
        fn = self._backfill_source()
        for banned in ("SHOWRUNNER", "showrunner_gate", "blocked = False",
                       "will_upload=False"):
            self.assertNotIn(banned, fn,
                             f"_backfill references {banned!r} — it must have "
                             f"no opinion about the gate at all")

    def test_a_held_video_is_never_resurrected(self):
        """The refused package must not be re-run; only NEW topics ship."""
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        self.run_backfill(results, ["fresh"])
        self.assertEqual(self.authored, ["fresh"])

    def test_a_replacement_that_is_ALSO_held_does_not_ship(self):
        results = [res(False, blocked=True) for _ in range(2)] + \
                  [res(True) for _ in range(4)]
        out = self.run_backfill(results, ["a", "b"], render_ok=False)
        self.assertTrue(out)
        self.assertFalse(any(r["ok"] for r in out),
                         "a replacement that lost to the gate must stay lost")

    def test_the_gate_still_decides_each_replacement_independently(self):
        results = [res(False, blocked=True) for _ in range(3)] + \
                  [res(True) for _ in range(3)]
        out = self.run_backfill(results, ["a", "b", "c"],
                                render_ok=lambda t: t.query == "b")
        self.assertEqual(sum(1 for r in out if r["ok"]), 1)


class TestItNeverDuplicatesAnUpload(BackfillCase):
    """Without draw-once, the thing that stops a replacement colliding with
    an existing upload is the posted-title exclusion. It is now load-bearing
    and gets its own tests."""

    def test_an_already_posted_topic_is_skipped(self):
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        out = self.run_backfill(results, ["old news", "brand new"],
                                posted=["old news"])
        self.assertEqual(self.authored, ["brand new"])
        self.assertEqual(len(out), 1)

    def test_the_match_ignores_case_and_padding(self):
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        self.run_backfill(results, ["  OLD News  ", "fresh"],
                          posted=["old news"])
        self.assertEqual(self.authored, ["fresh"])

    def test_nothing_fresh_means_an_HONEST_short_day(self):
        results = [res(False, blocked=True) for _ in range(3)] + \
                  [res(True) for _ in range(3)]
        out = self.run_backfill(results, ["seen"], posted=["seen"])
        self.assertEqual(out, [],
                         "with nothing fresh to author, the day stays short "
                         "— it never re-serves something already posted")


class TestItIsBounded(BackfillCase):
    def test_attempts_are_capped(self):
        results = [res(False, blocked=True) for _ in range(6)]
        out = self.run_backfill(results, [f"t{i}" for i in range(40)])
        self.assertEqual(len(out), rtd.MAX_BACKFILL,
                         "a systematically bad day must not eat the timeout")

    def test_discovery_running_dry_midway_stops_cleanly(self):
        results = [res(False, blocked=True) for _ in range(4)] + \
                  [res(True) for _ in range(2)]
        out = self.run_backfill(results, ["only-one"])
        self.assertEqual(len(out), 1)

    def test_a_dry_run_authors_nothing(self):
        results = [res(False, blocked=True) for _ in range(6)]
        out = self.run_backfill(results, ["a", "b"], dry_run=True)
        self.assertEqual(out, [])
        self.assertEqual(self.authored, [])

    def test_discovery_failing_is_survivable(self):
        """Feeds go down. That must cost the shortfall, not the run."""
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        out = self.run_backfill(results, [], discovery_raises=True)
        self.assertEqual(out, [])

    def test_one_crashing_replacement_does_not_stop_the_others(self):
        boom = ["bad", "good"]

        def render(topic, publish_at, *, dry_run, no_schedule):
            self.authored.append(topic.query)
            if topic.query == "bad":
                raise RuntimeError("render exploded")
            return res(True)

        results = [res(False, blocked=True) for _ in range(2)] + \
                  [res(True) for _ in range(4)]
        with mock.patch.object(rtd, "discover_all",
                               lambda: [Topic(t) for t in boom]), \
                mock.patch.object(rtd, "run_one", render), \
                mock.patch.object(rtd.rank_topics, "rank",
                                  lambda raw, top_k=0: list(raw)[:top_k]), \
                mock.patch.object(rtd, "posted_titles", set):
            out = rtd._backfill(results, Args(6), [None] * 8, self.now,
                                {"posted": []})
        self.assertEqual(self.authored, ["bad", "good"])
        self.assertEqual([r["ok"] for r in out], [True])


class TestThereIsNoReserveBank(unittest.TestCase):
    """The bank is retired, not dormant. A dormant fallback is worse than
    none: it reads like cover in every report while holding two packages."""

    def test_the_bank_module_is_gone(self):
        self.assertFalse((ROOT / "shared" / "package_buffer.py").exists())
        self.assertFalse((ROOT / "scripts" / "package_reserve.py").exists())
        self.assertFalse((ROOT / "state" / "package_buffer").exists())

    def test_backfill_does_not_reach_for_a_shelf(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        fn = src.split("def _backfill(", 1)[1].split("\ndef ", 1)[0]
        for banned in ("package_buffer", "buf.draw", "buf.select"):
            self.assertNotIn(banned, fn)

    def test_the_validator_survived_the_bank(self):
        """`structural_problems` lived in the bank module but was never
        about banking — every producer of a package still needs it."""
        from shared import package_schema as sch
        self.assertTrue(callable(sch.structural_problems))
        self.assertTrue(sch.structural_problems({"slug": "x"}))

    def test_it_is_wired_into_the_run(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        tree = ast.parse(src)
        main = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        calls = [n.func.id for n in ast.walk(main)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn("_backfill", calls,
                      "_backfill exists but main() never calls it")


if __name__ == "__main__":
    unittest.main()
