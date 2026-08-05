"""A held slot is not a lost slot — but a backfill must never be a bypass.

Operator ruling 2026-08-05: *"if the video doesn't make it past the gates,
they get a new video going — nothing doesn't post."*

On 2026-08-05 trending rendered six and shipped one. The showrunner
correctly held five weak videos and the run simply ended. The gate was right
every time; the pipeline's mistake was treating a refusal as the end of the
slot instead of the start of another attempt.

The danger in fixing that is obvious and it is the thing these tests exist
to prevent: a backfill that ships the video the gate just refused, or that
lowers the bar for the replacement, would be the bypass the doctrine
forbids. So the replacement goes through `run_one_from_package` — the exact
same render, technical QA, vision QA and showrunner path as the video it
replaces. Nothing here may ever change that.

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


def banked(fmt, slug):
    return {"banked_at": "2026-08-01T00:00:00Z", "format": fmt,
            "_file": f"/bank/{slug}.json",
            "package": {"slug": slug, "format": fmt, "title": slug}}


class BackfillCase(unittest.TestCase):
    """Stub the bank and the renderer; assert on what backfill DOES."""

    def setUp(self):
        self.drawn = []
        self.rendered = []
        self.now = __import__("datetime").datetime(2026, 8, 5)

    def run_backfill(self, results, stock, render_ok=True, count=6,
                     dry_run=False):
        import types
        buf = types.ModuleType("shared.package_buffer")
        buf.formats = lambda: ("graph_race", "reddit_story")
        pool = list(stock)

        def select(n, mix=None):
            if not pool:
                return []
            if mix:
                for fmt, want in (mix or {}).items():
                    if want > 0:
                        for e in pool:
                            if e["format"] == fmt:
                                return [e]
            return pool[:n]

        def draw(entries, *, date, reason=""):
            for e in entries:
                pool.remove(e)
                self.drawn.append((e["package"]["slug"], reason))
            return [dict(e["package"]) for e in entries]

        buf.select, buf.draw = select, draw

        def fake_render(pkg, publish_at, *, dry_run, no_schedule):
            self.rendered.append(pkg["slug"])
            ok = render_ok(pkg) if callable(render_ok) else render_ok
            return res(ok, pkg.get("format", "graph_race"),
                       blocked=not ok)

        import shared
        with mock.patch.dict(sys.modules,
                             {"shared.package_buffer": buf}), \
                mock.patch.object(shared, "package_buffer", buf,
                                  create=True), \
                mock.patch.object(rtd, "run_one_from_package", fake_render), \
                mock.patch.object(rtd, "load_log", lambda: {"posted": []}):
            return rtd._backfill(results, Args(count, dry_run), [None] * 8,
                                 self.now, {"posted": []})


class TestItRefillsHeldSlots(BackfillCase):
    def test_five_held_slots_pull_replacements(self):
        results = [res(True)] + [res(False, blocked=True) for _ in range(5)]
        stock = [banked("graph_race", f"g{i}") for i in range(5)]
        out = self.run_backfill(results, stock)
        self.assertEqual(len(out), min(5, rtd.MAX_BACKFILL))
        self.assertTrue(all(r["ok"] for r in out))
        self.assertTrue(all(r["backfill"] for r in out))

    def test_a_full_day_backfills_nothing(self):
        results = [res(True) for _ in range(6)]
        self.assertEqual(self.run_backfill(results, [banked("graph_race",
                                                            "g")]), [])
        self.assertEqual(self.drawn, [])

    def test_it_replaces_like_with_like(self):
        """A run that loses four charts must not come back with four reddit
        stories and silently rewrite the day's mix."""
        results = [res(False, "graph_race", blocked=True) for _ in range(2)]
        results += [res(True, "reddit"), res(True, "reddit"),
                    res(True, "reddit"), res(True, "reddit")]
        stock = [banked("reddit_story", "r1"), banked("graph_race", "g1"),
                 banked("graph_race", "g2")]
        self.run_backfill(results, stock)
        self.assertEqual([s for s, _ in self.drawn], ["g1", "g2"])

    def test_the_result_records_WHY_it_backfilled(self):
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        self.run_backfill(results, [banked("graph_race", "g1")])
        self.assertIn("held by a gate", self.drawn[0][1])


class TestItIsNeverABypass(BackfillCase):
    """The tests that matter. A backfill that ships a held video, or judges
    the replacement more gently, is the bypass the doctrine forbids."""

    def test_a_replacement_goes_through_the_SAME_render_and_gate_path(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        fn = src.split("def _backfill(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("run_one_from_package", fn,
                      "the replacement must take the same path as any other "
                      "video — render, technical QA, vision QA, showrunner")

    def test_backfill_never_touches_the_gate(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        fn = src.split("def _backfill(", 1)[1].split("\ndef ", 1)[0]
        for banned in ("SHOWRUNNER", "showrunner_gate", "blocked = False",
                       "will_upload=False"):
            self.assertNotIn(banned, fn,
                             f"_backfill references {banned!r} — it must have "
                             f"no opinion about the gate at all")

    def test_a_held_video_is_never_resurrected(self):
        """The refused package must not be re-run; only NEW packages ship."""
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        self.run_backfill(results, [banked("graph_race", "fresh")])
        self.assertEqual(self.rendered, ["fresh"])

    def test_a_replacement_that_is_ALSO_held_does_not_ship(self):
        results = [res(False, blocked=True) for _ in range(2)] + \
                  [res(True) for _ in range(4)]
        stock = [banked("graph_race", "g1"), banked("graph_race", "g2")]
        out = self.run_backfill(results, stock, render_ok=False)
        self.assertTrue(out)
        self.assertFalse(any(r["ok"] for r in out),
                         "a replacement that lost to the gate must stay lost")

    def test_the_gate_still_decides_each_replacement_independently(self):
        results = [res(False, blocked=True) for _ in range(3)] + \
                  [res(True) for _ in range(3)]
        stock = [banked("graph_race", f"g{i}") for i in range(3)]
        out = self.run_backfill(results, stock,
                                render_ok=lambda p: p["slug"] == "g1")
        self.assertEqual(sum(1 for r in out if r["ok"]), 1)


class TestItIsBounded(BackfillCase):
    def test_attempts_are_capped(self):
        results = [res(False, blocked=True) for _ in range(6)]
        stock = [banked("graph_race", f"g{i}") for i in range(20)]
        out = self.run_backfill(results, stock)
        self.assertEqual(len(out), rtd.MAX_BACKFILL,
                         "a systematically bad day must not eat the timeout")

    def test_an_empty_bank_leaves_an_HONEST_short_day(self):
        results = [res(False, blocked=True) for _ in range(3)] + \
                  [res(True) for _ in range(3)]
        out = self.run_backfill(results, [])
        self.assertEqual(out, [],
                         "with nothing to draw, the day stays short — it "
                         "never fabricates a video to hit the number")

    def test_a_bank_that_runs_dry_midway_stops_cleanly(self):
        results = [res(False, blocked=True) for _ in range(4)] + \
                  [res(True) for _ in range(2)]
        out = self.run_backfill(results, [banked("graph_race", "g1")])
        self.assertEqual(len(out), 1)

    def test_a_dry_run_backfills_nothing(self):
        results = [res(False, blocked=True) for _ in range(6)]
        out = self.run_backfill(results, [banked("graph_race", "g1")],
                                dry_run=True)
        self.assertEqual(out, [])
        self.assertEqual(self.drawn, [], "a dry run must not consume the bank")

    def test_a_missing_bank_module_is_survivable(self):
        """Patching sys.modules ALONE does not work here — `from shared
        import package_buffer` reads the attribute off the already-imported
        `shared` package, so the stub is ignored and the REAL bank answers.

        That is not a hypothetical: the first version of this test did
        exactly that, drew both genuinely-banked packages, marked them used
        (draw-once is irreversible by design) and started a real render. The
        bank had to be restored from git. Patch the attribute too."""
        import shared
        results = [res(False, blocked=True)] + [res(True) for _ in range(5)]
        real = getattr(shared, "package_buffer", None)
        try:
            if hasattr(shared, "package_buffer"):
                delattr(shared, "package_buffer")
            with mock.patch.dict(sys.modules,
                                 {"shared.package_buffer": None}):
                out = rtd._backfill(results, Args(6), [None] * 8, self.now,
                                    {"posted": []})
        finally:
            if real is not None:
                shared.package_buffer = real
        self.assertEqual(out, [])


class TestTheSuiteCannotBurnTheRealBank(unittest.TestCase):
    """A drawn package is gone FOREVER — `used.json` is append-only and
    draw-once is what stops a reserve package duplicating an upload. So a
    test that reaches the real bank does permanent damage to production
    state, and this suite has already done it once: the first version of
    `test_a_missing_bank_module_is_survivable` patched only `sys.modules`,
    the real bank answered, and both banked packages were consumed and
    marked used. They had to be restored from git.

    These are the tripwires."""

    def test_the_bank_still_has_stock(self):
        """Fails loudly if a test run drained it. Cheap, and it turns an
        invisible state loss into a red check."""
        from shared import package_buffer as buf
        inv = buf.inventory()
        self.assertTrue(sum(len(v) for v in inv.values()) > 0,
                        f"the reserve bank is EMPTY ({inv}) — if a test run "
                        f"drained it, restore with `git checkout -- state/` "
                        f"and patch BOTH sys.modules and the `shared` "
                        f"package attribute when stubbing it")

    def test_no_backfill_test_leaves_the_bank_dirty(self):
        """The whole point: running this file must not modify tracked
        state. Compares against git rather than a snapshot, so it catches
        damage from any test in the process, not just this module's."""
        import subprocess
        out = subprocess.run(
            ["git", "status", "--porcelain", "state/package_buffer"],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(out.stdout.strip(), "",
                         "the reserve bank is dirty after the tests ran — "
                         "something drew from the REAL bank")


class TestDrawOnceStillHolds(unittest.TestCase):
    """The bank's draw-once guarantee is what stops a replacement becoming a
    duplicate upload. Backfill must use `draw`, never read the bank
    directly."""

    def test_backfill_consumes_through_draw(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        fn = src.split("def _backfill(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("buf.draw(", fn)
        self.assertIn("buf.select(", fn)
        self.assertNotIn("entries()", fn,
                         "reading the bank directly would skip the "
                         "draw-once ledger and could duplicate an upload")

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
