"""An upload must be recorded durably BEFORE the next render starts.

An upload is irreversible and external: the video is on YouTube the instant the
API returns. Until 2026-09-04 the record of it was not equally durable —
`_save_log` wrote the RUNNER'S LOCAL DISK, and the git push lived in a final
workflow step. GitHub reclaimed a runner mid-job that morning ("the runner has
received a shutdown signal"), which takes the disk with it. Had that happened a
few minutes later, videos already live on the channel would have vanished from
the dedupe log and the next run would have posted them a second time.

CLAUDE.md: "Posted logs are sacred append-only dedupe state — losing an entry
means a duplicate upload."

So the log is now pushed after EVERY upload, and the exposure window is one
upload rather than the rest of the run.

Runs with pytest OR standalone:
    python3 tests/test_posted_log_durability.py
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_spec = importlib.util.spec_from_file_location(
    "post_stories_durability", _REPO / "scripts" / "post_stories.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

_SRC = (_REPO / "scripts" / "post_stories.py").read_text()


class PostedLogDurability(unittest.TestCase):
    def test_the_upload_site_persists_immediately(self):
        """The call has to sit with the upload, not at the end of the run.
        Checked in the source because the alternative is mocking the whole
        YouTube path to prove one line still exists."""
        after_upload = _SRC[_SRC.index('results.append({"slug": slug, "ok": True, "url": url})') - 700:
                            _SRC.index('results.append({"slug": slug, "ok": True, "url": url})')]
        self.assertIn("_save_log(log, args.log)", after_upload)
        self.assertIn("_persist_posted_log_now(args.log, slug)", after_upload,
                      "an upload is no longer persisted immediately — a "
                      "reclaimed runner would cost a duplicate upload")

    def test_it_pushes_the_log_when_running_in_ci(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch("subprocess.run", fake_run):
            ps._persist_posted_log_now(Path("state/explainer_posted_log.json"),
                                       "some-slug")
        self.assertEqual(len(calls), 1, "expected exactly one persist call")
        cmd = calls[0]
        self.assertIn("ci_commit_state.sh", " ".join(cmd))
        self.assertIn("state/explainer_posted_log.json", " ".join(cmd))
        self.assertTrue(any("some-slug" in c for c in cmd),
                        "the commit message should name the slug just posted")

    def test_it_is_a_no_op_outside_ci(self):
        """Running post_stories locally must not try to push to the repo."""
        calls = []
        with mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch("subprocess.run", lambda *a, **k: calls.append(a)):
            ps._persist_posted_log_now(Path("state/explainer_posted_log.json"),
                                       "x")
        self.assertEqual(calls, [])

    def test_a_failing_push_never_breaks_the_run(self):
        """The video is already public. Bookkeeping trouble is a warning, not
        an exception that aborts the remaining stories."""
        def boom(*a, **k):
            raise OSError("git exploded")

        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch("subprocess.run", boom):
            ps._persist_posted_log_now(Path("state/x.json"), "y")  # must not raise

        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch("subprocess.run",
                           lambda *a, **k: mock.Mock(returncode=1, stdout="",
                                                     stderr="push rejected")):
            ps._persist_posted_log_now(Path("state/x.json"), "y")  # must not raise

    def test_the_brain_step_is_capped_to_the_runs_own_slate(self):
        """The 09:32 run handed the director 74 slugs for a 4-video run. That
        is 70 stories of stale direction inside the window a reclaimed runner
        can kill."""
        wf = (_REPO / ".github" / "workflows" / "explainer.yml").read_text()
        self.assertRegex(
            wf, r'BRAIN_CAP="\$\{BRAIN_CAP:-\d+\}"',
            "the brain step no longer caps its slug list")
        self.assertIn('head -n "$BRAIN_CAP"', wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
