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


class APostIsCutWithoutItsSponsorCard(unittest.TestCase):
    """2026-10-13: a Mike Evans post ended on a sponsor logo held two
    seconds; it was cut in and the gate held the render as a freeze. A
    Ruben Dias post had no audio track and died in the render."""

    @classmethod
    def setUpClass(cls):
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("no ffmpeg")
        cls.tmp = Path(tempfile.mkdtemp())

        def make(name, still_s, audio=True):
            out = cls.tmp / name
            vf = "testsrc2=size=320x240:rate=30:duration=16"
            args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", vf]
            if still_s:
                args += ["-f", "lavfi", "-i",
                         f"color=white:size=320x240:rate=30:duration={still_s}"]
            if audio:
                args += ["-f", "lavfi", "-i",
                         f"sine=frequency=440:duration={16 + still_s}"]
            fc = ("[0:v][1:v]concat=n=2:v=1:a=0[v]" if still_s
                  else "[0:v]null[v]")
            args += ["-filter_complex", fc, "-map", "[v]"]
            if audio:
                args += ["-map", f"{2 if still_s else 1}:a", "-shortest"]
            args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
            subprocess.run(args, check=True)
            return out
        cls.card = make("card.mp4", 3)
        cls.moving = make("moving.mp4", 0)
        cls.silent = make("silent.mp4", 0, audio=False)

    def test_the_card_on_the_end_is_cut_off(self):
        from scripts import sports_samples as ss
        info = {"path": str(self.card)}
        self.assertEqual(ss.unfit(info), "")
        self.assertIn("nocard", info["path"])
        self.assertLess(ss._dur(Path(info["path"])), 16.0)
        self.assertGreater(ss._dur(Path(info["path"])), 14.5)

    def test_a_post_that_moves_to_its_end_is_left_alone(self):
        from scripts import sports_samples as ss
        info = {"path": str(self.moving)}
        self.assertEqual(ss.unfit(info), "")
        self.assertEqual(info["path"], str(self.moving))

    def test_a_post_with_no_sound_is_refused(self):
        from scripts import sports_samples as ss
        self.assertIn("no sound", ss.unfit({"path": str(self.silent)}))

    def test_both_runs_check_it_before_cutting(self):
        code = _code(SRC)
        self.assertLess(code.index("ss.unfit(info)"),
                        code.index("ss.too_short(info)"))
        samples = _code((ROOT / "scripts" / "sports_samples.py").read_text())
        self.assertIn("unfit(info) or too_short(info)", samples)


class ARefusedCutIsRepaired(unittest.TestCase):
    """2026-10-14: an Ovechkin cut scored 83 and was held for our line over
    the source's banner and an ending that drifted; the run dropped it."""

    VERDICT = {
        "score": 83, "verdict": "block",
        "one_line": "Warm moment, but our line sits over the banner.",
        "problems": ["hook@0.3: our caption is drawn over the source's "
                     "dark lower-third banner"],
        "fixes": ["End on the stick salute, not him skating away."],
        "weakest_scene": {"failure_class": "text_over_source_graphic"}}

    def _run(self, gates):
        from unittest import mock
        from scripts import run_sports as rs
        c = {"sub": "hockey", "who": "Alex Ovechkin", "why": "",
             "post_title": "Ovechkin's sons introduce him", "upvotes": 0,
             "url": "https://v.redd.it/x",
             "permalink": "/r/hockey/comments/abc/x/"}
        made = []

        def make(c, info, mp4, notes="", line_top=False):
            made.append({"notes": notes, "line_top": line_top})
            mp4.parent.mkdir(parents=True, exist_ok=True)
            mp4.write_bytes(b"x")
            return {"meta": {"title": f"cut {len(made)}", "hook": "h",
                             "edit": {"cut": {"start": 1, "end": 30}}},
                    "hook": "h", "ledger": {}}
        g = iter(gates)
        with mock.patch.object(rs.rt, "_refresh_log_from_origin"), \
                mock.patch.object(rs.rt, "load_log", return_value={}), \
                mock.patch.object(rs.rt, "uploaded_on", return_value=[]), \
                mock.patch.object(rs.ss, "discover", return_value=[c]), \
                mock.patch.object(rs.ss, "pick", return_value=[c]), \
                mock.patch.object(rs.ss, "fetch",
                                  return_value={"path": "x.mp4"}), \
                mock.patch.object(rs.ss, "unfit", return_value=""), \
                mock.patch.object(rs.ss, "too_short", return_value=""), \
                mock.patch.object(rs.ss, "make", side_effect=make), \
                mock.patch.object(rs, "judge",
                                  side_effect=lambda *a, **k: next(g)), \
                mock.patch.object(rs, "REPORT",
                                  Path(self.tmp) / "r.json"), \
                mock.patch.object(rs, "OUT", Path(self.tmp) / "out"), \
                mock.patch.object(sys, "argv",
                                  ["run_sports", "--count", "1",
                                   "--dry-run"]):
            code = rs.main()
        return code, made

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def test_a_near_miss_is_cut_again_from_the_verdict_and_ships(self):
        code, made = self._run([
            {"blocked": True, "reason": "BLOCK", "verdict": self.VERDICT},
            {"blocked": False, "reason": "ship", "verdict": {"score": 88}}])
        self.assertEqual(code, 0)
        self.assertEqual(len(made), 2)
        self.assertIn("stick salute", made[1]["notes"])
        self.assertIn("83", made[1]["notes"])
        self.assertTrue(made[1]["line_top"])

    def test_the_repair_is_judged_by_the_same_gate_and_can_stay_refused(self):
        block = {"blocked": True, "reason": "BLOCK", "verdict": self.VERDICT}
        code, made = self._run([block, block, block])
        self.assertEqual(code, 1)
        from scripts import run_sports as rs
        self.assertEqual(len(made), 1 + rs.REPAIRS)

    def test_a_weak_cut_is_not_worth_repairing(self):
        weak = {"blocked": True, "reason": "BLOCK",
                "verdict": {"score": 40, "problems": ["no moment"]}}
        code, made = self._run([weak])
        self.assertEqual(len(made), 1)

    def test_the_line_only_moves_for_a_graphic(self):
        from scripts import run_sports as rs
        self.assertTrue(rs.over_graphic(self.VERDICT))
        self.assertFalse(rs.over_graphic(
            {"problems": ["the ending drifts"], "weakest_scene": {}}))


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


class WhatWentLiveCanBeWatched(unittest.TestCase):
    def test_every_cut_goes_to_preview_renders(self):
        wf = (ROOT / ".github" / "workflows" / "sports.yml").read_text()
        self.assertIn("sports-live/", wf)
        self.assertIn("for f in output/sports/*.mp4", wf)
        self.assertIn("git push origin preview-renders", wf)


if __name__ == "__main__":
    unittest.main()
