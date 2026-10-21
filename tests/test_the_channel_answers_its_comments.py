"""THE CHANNEL ANSWERS ITS COMMENTS, ONCE, AND NEVER WITH A LINK.

Operator, 2026-10-18: *"Can we have the AI comment on people's comments
... who doesn't like engagement?"*, then *"TikTok and YouTube."*
`scripts/reply_comments.py` replies on YouTube (TikTok's posting app has no
comment scope). Held here, offline, against a fake Data API:

  1. a thread the channel already answered is never answered again, even
     when its reply is past the five YouTube inlines;
  2. the channel's own comments and comments older than `max_age_h` are
     left alone;
  3. code refuses a reply with a link, a handle, or too many words,
     whatever the brain wrote;
  4. a dry run posts nothing, a real run posts exactly what passed;
  5. every channel with a TikTok also has the policy in the registry.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import reply_comments as RC                       # noqa: E402
from shared import channel_registry                            # noqa: E402

ME = "UCme"
NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def _iso(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _thread(tid, author, text, hours_ago, replies=(), total=None):
    return {"id": tid, "snippet": {
        "videoId": "v1", "canReply": True,
        "totalReplyCount": len(replies) if total is None else total,
        "topLevelComment": {"snippet": {
            "videoId": "v1", "authorChannelId": {"value": author},
            "authorDisplayName": author, "textOriginal": text,
            "publishedAt": _iso(hours_ago)}}},
        "replies": {"comments": [
            {"snippet": {"authorChannelId": {"value": a}}} for a in replies]}}


class _Req:
    def __init__(self, resp):
        self.resp = resp

    def execute(self):
        return self.resp


class FakeYT:
    def __init__(self, threads, hidden_replies=None):
        self.threads = threads
        self.hidden = hidden_replies or {}
        self.inserted = []

    def commentThreads(self):
        fake = self

        class T:
            def list(self, **kw):
                return _Req({"items": fake.threads})

            def list_next(self, req, resp):
                return None
        return T()

    def comments(self):
        fake = self

        class C:
            def list(self, parentId, **kw):
                return _Req({"items": [
                    {"snippet": {"authorChannelId": {"value": a}}}
                    for a in fake.hidden.get(parentId, [])]})

            def list_next(self, req, resp):
                return None

            def insert(self, part, body):
                fake.inserted.append(body["snippet"])
                return _Req({"id": "new"})
        return C()

    def videos(self):
        class V:
            def list(self, **kw):
                return _Req({"items": [{"id": "v1",
                                        "snippet": {"title": "Cow burps"}}]})
        return V()


def _threads():
    return [
        _thread("t_new", "UCfan", "this is crazy", 2),
        _thread("t_done", "UCfan2", "wow", 3, replies=["UCme"]),
        # our reply is the 6th, so not among the inlined five
        _thread("t_deep", "UCfan3", "lol", 4,
                replies=["UCa", "UCb", "UCc", "UCd", "UCe"], total=6),
        _thread("t_mine", ME, "pinned note", 5),
        _thread("t_old", "UCfan4", "old one", 100),
    ]


class TheChannelAnswersOnce(unittest.TestCase):
    def test_only_unanswered_fresh_viewer_comments_are_pending(self):
        svc = FakeYT(_threads(), hidden_replies={
            "t_deep": ["UCa", "UCb", "UCc", "UCd", "UCe", ME]})
        got = RC.pending(svc, ME, max_age_h=72, now=NOW)
        self.assertEqual([c["thread_id"] for c in got], ["t_new"])

    def test_a_deep_thread_without_our_reply_is_still_pending(self):
        svc = FakeYT(_threads(), hidden_replies={
            "t_deep": ["UCa", "UCb", "UCc", "UCd", "UCe", "UCf"]})
        got = RC.pending(svc, ME, max_age_h=72, now=NOW)
        self.assertEqual([c["thread_id"] for c in got], ["t_new", "t_deep"])


class CodeRefusesABadReply(unittest.TestCase):
    def test_links_handles_and_essays_are_refused(self):
        self.assertIsNone(RC.check_reply("check https://x.co"))
        self.assertIsNone(RC.check_reply("go to mysite.com"))
        self.assertIsNone(RC.check_reply("ask @someone"))
        self.assertIsNone(RC.check_reply("word " * 60))
        self.assertIsNone(RC.check_reply("   "))

    def test_a_good_reply_posts_as_written(self):
        self.assertEqual(RC.check_reply('  "right?? cows are wild"  '),
                         "right?? cows are wild")
        self.assertEqual(RC.check_reply("email me@x? nah"), "email me@x? nah")


class ARunPostsWhatPassed(unittest.TestCase):
    def _run(self, dry, replies):
        svc = FakeYT(_threads(), hidden_replies={"t_deep": [ME]})
        up = mock.MagicMock()
        up._credentials.return_value = mock.MagicMock(scopes=[RC.FORCE_SSL])
        up.whoami.return_value = {"id": ME}
        real = RC.pending
        # the comments are dated against NOW; the run reads the real
        # clock, so from 2026-10-21 every one was "too old" and nothing
        # was ever answered
        with mock.patch("shared.uploaders.YouTubeUploader", return_value=up), \
             mock.patch.object(RC, "_youtube", return_value=svc), \
             mock.patch.object(RC, "draft", return_value=replies), \
             mock.patch.object(RC, "pending", side_effect=(
                 lambda *a, **k: real(*a, **{**k, "now": NOW}))):
            out = RC.run_channel("explainer", dry_run=dry)
        return svc, out

    def test_dry_run_posts_nothing(self):
        svc, out = self._run(True, {"t_new": "haha right"})
        self.assertEqual(svc.inserted, [])
        self.assertEqual(len(out["replied"]), 1)

    def test_real_run_posts_only_checked_replies(self):
        svc, out = self._run(False, {"t_new": "haha right"})
        self.assertEqual(svc.inserted,
                         [{"parentId": "t_new", "textOriginal": "haha right"}])
        svc, out = self._run(False, {"t_new": "see www.spam.com"})
        self.assertEqual(svc.inserted, [])

    def test_a_token_without_force_ssl_is_reported_not_crashed(self):
        up = mock.MagicMock()
        up._credentials.return_value = mock.MagicMock(
            scopes=["https://www.googleapis.com/auth/youtube.upload"])
        with mock.patch("shared.uploaders.YouTubeUploader", return_value=up):
            out = RC.run_channel("explainer", dry_run=False)
        self.assertIn("force-ssl", out["status"])


class ThePolicyIsInTheRegistry(unittest.TestCase):
    def test_every_tiktok_channel_has_a_comment_voice(self):
        reg = channel_registry.load()
        for cid in channel_registry.channel_ids(reg):
            ch = channel_registry.channel(cid, reg)
            if not ch.get("tiktok"):
                continue
            cfg = RC.settings(cid, reg)
            self.assertIsNotNone(cfg, cid)
            self.assertTrue(cfg.get("voice", "").strip(), cid)

    def test_trending_uses_the_original_token(self):
        self.assertEqual(RC.token_slug("trending"), "")
        self.assertEqual(RC.token_slug("explainer"), "explainer")


if __name__ == "__main__":
    unittest.main()
