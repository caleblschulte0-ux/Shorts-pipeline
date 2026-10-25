"""WE CAN READ WHAT VIEWERS SAY.

Operator, 2026-10-25: "all of our comments are, oh, this is AI ... what can
we do to stop that?" No session could see one comment: the reply job was
the only reader, and every channel's token lacked youtube.force-ssl, so it
stopped before reading anything. `reply_comments.py --save` reads public
comments with the API key, for each channel's newest uploads, and keeps
the newest in state/comments/<channel>.json. It never replies.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import reply_comments as RC                     # noqa: E402


def _thread(text, when, likes=0):
    return {"snippet": {"totalReplyCount": 1, "topLevelComment": {"snippet": {
        "textOriginal": text, "likeCount": likes, "publishedAt": when}}}}


class WeCanReadWhatViewersSay(unittest.TestCase):

    def test_a_thread_becomes_one_small_row(self):
        rows = RC.comment_rows([_thread("this is  AI\nlol", "2026-10-24T01:00:00Z", 3),
                                _thread("", "2026-10-24T02:00:00Z")],
                               "abcdefghijk", "Olympic Bids")
        self.assertEqual(rows, [{"video_id": "abcdefghijk", "title": "Olympic Bids",
                                 "text": "this is AI lol", "likes": 3, "replies": 1,
                                 "published_at": "2026-10-24T01:00:00Z"}])

    def test_a_long_comment_is_cut(self):
        rows = RC.comment_rows([_thread("x" * 5000, "2026-10-24T01:00:00Z")], "v", "t")
        self.assertEqual(len(rows[0]["text"]), RC.SAVE_TEXT)

    def test_newest_first_no_repeats_and_capped(self):
        rows = [{"video_id": "v", "text": f"c{i}", "published_at": f"2026-10-{i % 28 + 1:02d}"}
                for i in range(RC.SAVE_KEEP + 50)]
        rows.append(dict(rows[0]))
        got = RC.keep_newest(rows)
        self.assertEqual(len(got), RC.SAVE_KEEP)
        self.assertEqual(len({(r["video_id"], r["text"]) for r in got}), len(got))
        stamps = [r["published_at"] for r in got]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_the_file_stays_under_the_state_size_limit(self):
        rows = [{"video_id": "abcdefghijk", "title": "T" * 100, "text": "w" * RC.SAVE_TEXT,
                 "likes": 99999, "replies": 999, "published_at": "2026-10-24T01:00:00Z"}
                for _ in range(RC.SAVE_KEEP)]
        blob = json.dumps({"channel": "explainer", "fetched_at": "x", "comments": rows},
                          ensure_ascii=False, indent=1)
        self.assertLess(len(blob.encode()), 256 * 1024)

    def test_uploads_come_from_the_registry_posted_log_newest_first(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "log.json"
            log.write_text(json.dumps({"posted": [
                {"url": "https://youtube.com/shorts/AAAAAAAAAAA", "title": "old"},
                {"video_url": "https://youtube.com/shorts/BBBBBBBBBBB", "title": "new"}]}))
            reg = {"channels": {"x": {"paths": {"posted_log": str(log)}}}}
            with mock.patch.object(RC, "ROOT", Path("/")):
                got = RC._uploads("x", reg)
        self.assertEqual(got, [("BBBBBBBBBBB", "new"), ("AAAAAAAAAAA", "old")])

    def test_save_never_replies(self):
        import inspect
        src = inspect.getsource(RC.save_channel)
        self.assertNotIn("insert", src)

    def test_the_workflow_saves_and_commits_them(self):
        wf = (ROOT / ".github/workflows/comment_replies.yml").read_text()
        self.assertIn("reply_comments.py --save", wf)
        self.assertIn("state/comments", wf)
        self.assertIn("YOUTUBE_API_KEY", wf)


if __name__ == "__main__":
    unittest.main()
