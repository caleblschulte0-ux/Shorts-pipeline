"""An upload is irreversible. The record of it must be written FIRST.

On 2026-09-07 two copies of the same video went out on the data channel and
the posted log recorded one. Both halves of that are the bug:

  * THE RECORD CAME AFTER THE UPLOAD. The video is live the moment the API
    accepts it, so a read timeout, a connection reset, a client-side retry or
    a reclaimed runner in the window between `upload()` and the log write
    leaves a video on the channel that nothing recorded. The next run sees an
    un-posted slug and uploads it again. The previous fix closed the window
    between one upload and the NEXT RENDER — never the window around the
    upload itself, which is the only one that can duplicate.
  * THE LOG COULD NOT REPRESENT IT. `posted` is keyed by slug, so a second
    upload of the same slug overwrites the first. The duplicate was not just
    unprevented, it was invisible: the log said one upload while two were
    live, so nothing downstream could ever notice.

The fix is the pattern `run_third.py` has used since 2026-08: claim the slot,
persist the claim, then upload, then confirm. An orphan — a claim with no URL
— is strictly better than a duplicate, because it names the slug to check.

Runs standalone:  python3 tests/test_no_duplicate_upload_ever.py
"""
from __future__ import annotations


import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

POSTER = _REPO / "scripts" / "post_stories.py"


class TheClaimComesBeforeTheUpload(unittest.TestCase):
    def setUp(self):
        self.src = POSTER.read_text(encoding="utf-8")

    def test_the_slot_is_claimed_and_PERSISTED_before_the_api_call(self):
        claim = self.src.index('"state": "uploading"')
        persist = self.src.index('why="claim upload slot"')
        upload = self.src.index("res = uploader.upload(")
        self.assertLess(claim, upload, "the claim is written after the upload")
        self.assertLess(persist, upload,
                        "the claim is pushed after the upload — a reclaimed "
                        "runner in that window is a duplicate")

    def test_a_claim_with_no_url_HOLDS_the_slug(self):
        self.assertIn("unconfirmed_upload_hold", self.src)
        self.assertIn('_rec.get("state") == "uploading"', self.src)

    def test_only_errors_that_CANNOT_have_posted_release_the_claim(self):
        """A timeout may well have put the video up. Releasing on it is how a
        retry becomes a duplicate."""
        self.assertIn("_certain = (", self.src)
        for safe in ("uploadLimitExceeded", "401", "403"):
            self.assertIn(safe, self.src)
        block = self.src[self.src.index("_certain = ("):
                         self.src.index("results.append({\"slug\": slug, "
                                        "\"ok\": False, \"error\": msg})")]
        for unsafe in ("Timeout", "timed out", "reset"):
            self.assertNotIn(unsafe, block,
                             f"{unsafe!r} releases a claim that may be live")

    def test_every_upload_is_recorded_append_only(self):
        """`posted` is keyed by slug and cannot hold two uploads of one story.
        `uploads` can, which is what makes a duplicate detectable at all."""
        self.assertIn('log.setdefault("uploads", []).append', self.src)


class TheUnionMergeKeepsEveryUploadEvent(unittest.TestCase):
    def test_uploads_is_unioned_not_overwritten(self):
        from scripts import merge_posted_log as m
        theirs = {"posted": {"a": {"url": "u1"}},
                  "uploads": [{"slug": "a", "claimed_at": "T1", "url": "u1"}]}
        ours = {"posted": {"b": {"url": "u2"}},
                "uploads": [{"slug": "b", "claimed_at": "T2", "url": "u2"}]}
        out = m.merge(theirs, ours)
        self.assertEqual(len(out["uploads"]), 2,
                         "a side's upload events were dropped by the merge")

    def test_two_uploads_of_ONE_slug_both_survive(self):
        """The whole point. Identity keyed on slug alone would collapse them
        and hide the duplicate again."""
        from scripts import merge_posted_log as m
        theirs = {"uploads": [{"slug": "a", "claimed_at": "T1", "url": "u1"}]}
        ours = {"uploads": [{"slug": "a", "claimed_at": "T2", "url": "u2"}]}
        out = m.merge(theirs, ours)
        self.assertEqual(len(out["uploads"]), 2)

    def test_the_same_event_twice_is_still_one(self):
        from scripts import merge_posted_log as m
        e = {"slug": "a", "claimed_at": "T1", "url": "u1"}
        out = m.merge({"uploads": [e]}, {"uploads": [dict(e)]})
        self.assertEqual(len(out["uploads"]), 1)

    def test_posted_is_still_unioned_too(self):
        from scripts import merge_posted_log as m
        out = m.merge({"posted": {"a": {"url": "u1"}}},
                      {"posted": {"b": {"url": "u2"}}})
        self.assertEqual(sorted(out["posted"]), ["a", "b"])


class TheLogCanBeAUDITEDForDuplicates(unittest.TestCase):
    def test_a_duplicate_is_detectable_from_the_uploads_list(self):
        import collections
        uploads = [{"slug": "a", "claimed_at": "T1", "url": "u1"},
                   {"slug": "a", "claimed_at": "T2", "url": "u2"}]
        by_slug = collections.Counter(u["slug"] for u in uploads
                                      if u.get("url"))
        dupes = [s for s, n in by_slug.items() if n > 1]
        self.assertEqual(dupes, ["a"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
