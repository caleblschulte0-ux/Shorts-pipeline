"""A posting run never writes another run's uploads out of the posted log.

2026-10-07 to 2026-10-09: a claim lost its push race, ci_commit_state.sh
union-merged the file on disk with main, and the run then saved the dict it
had loaded at the start over that merged file. The push after it was a clean
fast-forward, so eight live videos left the ledger. The twins story was
uploaded again two days later, and TikTok was sent the first render because
its release had the same title (operator: "isn't that the older art style?").
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

from scripts import post_stories as ps  # noqa: E402
import tiktok_post_release as tt  # noqa: E402


def _entry(url, at):
    return {"url": url, "title": url, "at": at, "state": "posted"}


class TheRunTakesBackWhatThePersistMerged(unittest.TestCase):
    def test_a_lost_race_keeps_the_other_runs_uploads(self):
        mine = {"posted": {"mine": {"claimed_at": "T2", "url": None,
                                    "state": "uploading"}},
                "uploads": [{"slug": "mine", "claimed_at": "T2", "url": None}]}
        # what the file holds after ci_commit_state union-merged it with main
        merged = json.loads(json.dumps(mine))
        merged["posted"]["theirs"] = _entry("https://y/theirs", "T1")
        merged["uploads"].insert(0, {"slug": "theirs", "claimed_at": "T1",
                                     "url": "https://y/theirs"})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "log.json"
            p.write_text(json.dumps(merged))
            self.assertEqual(ps._absorb_persisted(mine, p), 2)
            # the run now records its own upload and saves, as post_stories does
            mine["posted"]["mine"] = _entry("https://y/mine", "T3")
            ps._save_log(mine, p)
            saved = json.loads(p.read_text())
        self.assertIn("theirs", saved["posted"])
        self.assertEqual({u["slug"] for u in saved["uploads"]}, {"mine", "theirs"})
        self.assertEqual(saved["posted"]["mine"]["url"], "https://y/mine",
                         "the run's own fresher entry wins its slug")

    def test_nothing_on_disk_changes_nothing(self):
        log = {"posted": {"a": _entry("u", "t")}, "uploads": []}
        self.assertEqual(ps._absorb_persisted(log, Path("/no/such/log.json")), 0)
        self.assertEqual(list(log["posted"]), ["a"])

    def test_both_persists_are_followed_by_the_absorb(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        main = next(n for n in ast.walk(ast.parse(src))
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        body = ast.get_source_segment(src, main)
        claim = body.index('why="claim upload slot"')
        self.assertLess(claim, body.index("_absorb_persisted(log, args.log)", claim))
        posted = body.index("if _persist_posted_log_now(args.log, slug):")
        self.assertLess(posted, body.index("_absorb_persisted(log, args.log)", posted))


class TheRunDecidesOnMainNotOnItsCheckout(unittest.TestCase):
    """2026-10-09: a 14:00 dispatch waited in the concurrency group until
    15:32, missed the twins upload made at 15:31, and uploaded it again."""

    def test_main_entries_are_added(self):
        from unittest import mock
        main = {"posted": {"twin": _entry("https://y/twin", "T1")},
                "uploads": [{"slug": "twin", "claimed_at": "T1", "url": "https://y/twin"}]}
        log = {"posted": {}, "uploads": []}

        def run(argv, **kw):
            out = json.dumps(main) if argv[:2] == ["git", "show"] else ""
            return mock.Mock(stdout=out, returncode=0)
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch("subprocess.run", side_effect=run):
            self.assertEqual(ps._refresh_from_origin(
                log, ROOT / "state" / "explainer_posted_log.json"), 2)
        self.assertIn("twin", log["posted"])

    def test_off_ci_it_is_a_no_op(self):
        from unittest import mock
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(ps._refresh_from_origin({"posted": {}}, Path("x")), 0)

    def test_refreshed_at_the_start_and_before_every_claim(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        main = next(n for n in ast.walk(ast.parse(src))
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        body = ast.get_source_segment(src, main)
        load = body.index("log = _load_log(args.log)")
        self.assertLess(load, body.index("_refresh_from_origin(log, args.log)", load))
        self.assertLess(body.index("_refresh_from_origin(log, args.log)", load),
                        body.index("for slug in slugs:"))
        claim = body.index("_claim = {")
        before = body[:claim]
        last = before.rindex("_refresh_from_origin(log, args.log)")
        self.assertIn('slug in log["posted"]', before[last:],
                      "the slug is checked again after the refresh")


class TheLedgerHasTheVideosItLost(unittest.TestCase):
    LOST = ["BLn8RBdPucM", "3E-LP1AFvls", "m-228C5VOcw", "xhZHZjV5o9c", "aCtti_E5Nqo",
            "2Krsh_OGfK8", "InVYGU9plr0", "YC6kYj8fXy0", "_GjzcmO4aMA"]

    def test_every_lost_upload_is_back(self):
        log = json.loads((ROOT / "state" / "explainer_posted_log.json").read_text())
        urls = {u.get("url") for u in log["uploads"]}
        for vid in self.LOST:
            self.assertIn(f"https://youtube.com/shorts/{vid}", urls)


class TikTokGetsTheVideoYouTubeHas(unittest.TestCase):
    ENTRY = {"title": "Why Twin Births Nearly Doubled",
             "at": "2026-10-09T15:31:32+00:00",
             "publish_at": "2026-10-09T14:29:32Z"}

    def _rel(self, made):
        return {"assets": [{"name": "tiktok.json", "created_at": made},
                           {"name": "why-twin.mp4", "created_at": made}]}

    def test_an_older_render_with_the_same_title_is_refused(self):
        self.assertFalse(tt.same_render(self._rel("2026-10-07T12:10:38Z"), self.ENTRY))

    def test_the_render_attached_after_the_upload_goes(self):
        self.assertTrue(tt.same_render(self._rel("2026-10-09T15:31:40Z"), self.ENTRY))

    def test_due_checks_it(self):
        src = (ROOT / "scripts" / "tiktok_post_release.py").read_text()
        due = src[src.index("def due("):src.index("def main(")]
        self.assertIn("same_render(rel, entry)", due)


if __name__ == "__main__":
    unittest.main()
