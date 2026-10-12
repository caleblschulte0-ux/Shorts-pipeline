"""Baller Bro (registry `trending`) is a SPORTS MOMENTS channel.

Operator, 2026-10-11, of the OG channel (439 graph races and Reddit
stories at ~3 views each): "we'll switch it to sports moments". The
channel is now CAPTURED — scripts/run_sports.py makes and posts it from
real footage — so the package chain (the Routine, Phase A's takeover,
daily.yml) must stand down for it, and the new run owes everything the
old one did: the shared showrunner gate before the upload, the claim on
main before the API call, and never the same post twice.
"""
from __future__ import annotations

import ast
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_sports  # noqa: E402

SRC = (ROOT / "scripts" / "run_sports.py").read_text()


def _code(src: str) -> str:
    """The source with string constants blanked: assert on CODE only."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.unparse(tree)


class TheGateComesBeforeTheUpload(unittest.TestCase):
    def test_it_judges_through_the_shared_gate(self):
        code = _code(SRC)
        self.assertIn("showrunner_gate.run(", code)
        self.assertIn("will_upload=not a.dry_run", code)

    def test_a_block_skips_before_any_upload(self):
        code = _code(SRC)
        block = code.index("if gate['']:")
        self.assertLess(block, code.index("_guarded_upload("))
        self.assertLess(block, code.index("YouTubeUploader("))
        self.assertIn("continue", code[block:block + 120])

    def test_the_upload_is_claimed_on_main(self):
        """The trending posted log's own claim → upload → record, so a
        claim that cannot be pushed refuses the upload."""
        code = _code(SRC)
        self.assertIn("rt._guarded_upload(", code)
        self.assertIn("except rt.ClaimNotDurable", code)

    def test_the_showrunner_knows_the_format(self):
        from scripts.showrunner_review import _format_directive
        text = _format_directive({"format": "sports_moment"})
        self.assertIn("SPORTS MOMENT", text)
        self.assertIn("mark decorative_mascot present", text)
        self.assertIn("junk_imagery", text)
        # operator, 2026-10-12, of a reaction-stream cut: "What the fuck
        # are they even talking about?"
        self.assertIn("restream", text)
        self.assertIn("what they are talking about", text)
        self.assertEqual(run_sports.FORMAT, "sports_moment")


class TheSamePostIsNeverCutTwice(unittest.TestCase):
    def test_a_posted_permalink_is_used(self):
        pool = [{"permalink": "/r/nba/comments/abc/x/", "url": "u1"},
                {"permalink": "/r/nba/comments/def/y/", "url": "u2"}]
        log = {"posted": [{"topic":
                           "https://www.reddit.com/r/nba/comments/abc/x"}]}
        self.assertEqual(run_sports.already_used(pool, log),
                         {"https://www.reddit.com/r/nba/comments/abc/x"})

    def test_an_open_claim_counts_too(self):
        pool = [{"permalink": "/r/nfl/comments/q/z", "url": "u"}]
        log = {"uploads": [{"topic":
                            "https://www.reddit.com/r/nfl/comments/q/z",
                            "state": "uploading"}]}
        self.assertEqual(len(run_sports.already_used(pool, log)), 1)


class EachPostTakesTheNextSlot(unittest.TestCase):
    SLOTS = [(11, 0), (15, 0), (19, 0)]

    def test_slots_follow_one_another(self):
        now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)  # 7 CDT
        a = run_sports.next_slot(self.SLOTS, now=now)
        b = run_sports.next_slot(self.SLOTS, after=a, now=now)
        c = run_sports.next_slot(self.SLOTS, after=b, now=now)
        self.assertEqual([a, b, c], ["2026-10-12T16:00:00Z",
                                     "2026-10-12T20:00:00Z",
                                     "2026-10-13T00:00:00Z"])

    def test_a_slot_already_past_is_never_handed_to_youtube(self):
        now = datetime(2026, 10, 12, 16, 30, tzinfo=timezone.utc)
        self.assertGreater(run_sports.next_slot(self.SLOTS, now=now),
                           "2026-10-12T16:35:00Z")


class ThePackageChainStandsDown(unittest.TestCase):
    def test_phase_a_asks_nobody_to_author_a_captured_channel(self):
        src = (ROOT / "scripts" / "exchange_phase_a.py").read_text()
        code = _code(src)
        cap = code.index("reg.captured(args.channel)")
        self.assertLess(cap, code.index("brief.build_request("))

    def test_the_package_renderer_exits_clean(self):
        """A Phase B hand-off or trigger file reaching daily.yml must not
        read a switched format as a failed day (exit 2 → auto-pause)."""
        import os
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            env = {k: v for k, v in os.environ.items()
                   if k != "GITHUB_ACTIONS"}
            r = subprocess.run(
                [sys.executable, "-c",
                 "import sys; sys.argv=['x','--count','3',"
                 "'--require-manifest','--dry-run'];"
                 "from scripts import run_trending_daily as rt;"
                 "from pathlib import Path;"
                 f"rt.REPORT_PATH=Path({d!r})/'r.md';"
                 f"rt.REPORT_JSON=Path({d!r})/'r.json';"
                 "sys.exit(rt.main())"],
                cwd=ROOT, env=env, capture_output=True, text=True,
                timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("made by capture", r.stdout)

    def test_the_routine_is_told(self):
        text = (ROOT / "CLAUDE_ROUTINE_INSTRUCTIONS.md").read_text()
        self.assertIn("r.captured('trending')", text)


class AFiveSecondPostIsTooShort(unittest.TestCase):
    """Operator, 2026-10-12, of samples that ran 5-14s, each the whole
    post: "the clips are too short"."""

    def test_a_short_post_is_skipped(self):
        from unittest import mock
        from scripts import sports_samples as ss
        with mock.patch.object(ss, "_dur", return_value=5.7):
            self.assertIn("too short", ss.too_short({"path": "x.mp4"}))
        with mock.patch.object(ss, "_dur", return_value=24.0):
            self.assertEqual(ss.too_short({"path": "x.mp4"}), "")
        with mock.patch.object(ss, "_dur", return_value=0.0):
            self.assertEqual(ss.too_short({"path": "x.mp4"}), "")

    def test_the_post_run_checks_before_cutting(self):
        code = _code(SRC)
        self.assertLess(code.index("ss.too_short(info)"),
                        code.index("ss.make(c, info, mp4)"))


class ItReachesTikTok(unittest.TestCase):
    """Operator, 2026-10-12: "Yes do it". A post reaches TikTok through its
    release, so the run must be able to make one."""

    def test_the_run_can_make_the_release(self):
        wf = (ROOT / ".github" / "workflows" / "sports.yml").read_text()
        step = wf[wf.index("Make, judge and post"):]
        step = step[:step.index("- name:")]
        self.assertIn("GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}", step)
        self.assertIn("GITHUB_REPOSITORY:", step)
        self.assertIn("crosspost(CHANNEL", SRC)


if __name__ == "__main__":
    unittest.main()
