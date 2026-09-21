"""WHAT THE FIRST LIVE RUN OF THE MAILBOX JUDGE FOUND (2026-09-21, run #445).

  1. THE JUDGE DIED ON ITS OWN JSON, three attempts in a row —
     `Expecting ',' delimiter: line 7 column 1395` — and the render went to
     the mailbox although the brain had graded it. `parse_judge_json` now
     recovers prose-wrapped, fenced, doubled and trailing-junk output, and
     asks the brain to make its own JSON parse before giving up. Nothing
     changes a grade; an unparseable verdict still fails closed.
  2. THE FRAMES NEVER REACHED preview-renders. `publish_review_media.sh`
     switched branches inside the render's dirty checkout, the checkout
     refused, the script fell into its orphan path, pushed a root commit
     against a branch with history, was rejected four times, and printed
     "published". It now publishes from a separate worktree and fails
     loudly when the push fails — proven here against a local bare remote
     with a dirty checkout.
  (3. The library union dropped legacy entries without a `sig`: held in
     `test_ci_persist_merges_the_library.py`.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import showrunner_review as SR                  # noqa: E402

GOOD = {"dimensions": {"hook": 3}, "checks": {}, "one_line": "ok"}


class TheJudgesJsonIsRecoveredNotDiscarded(unittest.TestCase):
    def test_clean_json_parses(self):
        self.assertEqual(SR.parse_judge_json(json.dumps(GOOD)), GOOD)

    def test_prose_around_the_object(self):
        txt = "Here is my grade:\n" + json.dumps(GOOD) + "\nLet me know if you need more."
        self.assertEqual(SR.parse_judge_json(txt), GOOD)

    def test_code_fences(self):
        self.assertEqual(SR.parse_judge_json("```json\n" + json.dumps(GOOD) + "\n```"), GOOD)

    def test_a_second_object_after_the_verdict_does_not_swallow_it(self):
        """The old greedy `\\{.*\\}` spanned both objects and failed."""
        txt = json.dumps(GOOD) + "\n\nNote: {\"aside\": true}"
        self.assertEqual(SR.parse_judge_json(txt), GOOD)

    def test_braces_inside_strings_do_not_confuse_the_balancer(self):
        g = dict(GOOD, one_line="label reads '{82%}' at seg1:mid")
        self.assertEqual(SR.parse_judge_json("x " + json.dumps(g) + " y"), g)

    def test_an_unescaped_quote_goes_to_the_repairer_and_is_verified(self):
        broken = '{"dimensions": {"hook": 3}, "one_line": "the label "82%" is clipped"}'
        seen = []

        def repair(text):
            seen.append(text)
            return json.dumps({"dimensions": {"hook": 3}, "one_line": "the label \"82%\" is clipped"})
        got = SR.parse_judge_json(broken, repair=repair)
        self.assertEqual(seen, [broken])
        self.assertEqual(got["one_line"], 'the label "82%" is clipped')

    def test_a_repair_that_still_does_not_parse_fails_closed(self):
        with self.assertRaises(RuntimeError):
            SR.parse_judge_json('{"a": "b" "c"}', repair=lambda t: '{"still": broken}')

    def test_no_repairer_and_nothing_parses_raises(self):
        with self.assertRaises(RuntimeError):
            SR.parse_judge_json("no json here at all")
        with self.assertRaises(RuntimeError):
            SR.parse_judge_json("")

    def test_both_judges_use_it(self):
        import inspect
        self.assertIn("parse_judge_json(", inspect.getsource(SR._headless_claude_judge))
        self.assertIn("parse_judge_json(", inspect.getsource(SR._gemini_judge))

    def test_the_prompt_asks_for_parseable_json(self):
        self.assertIn("must PARSE as JSON", SR._GRADE_PROMPT)


class TheFramesReachThePreviewBranch(unittest.TestCase):
    """The script against a real (local, bare) remote, from a DIRTY checkout."""

    def _git(self, cwd, *args):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                              cwd=cwd, check=True, capture_output=True, text=True).stdout

    def _setup(self, with_branch: bool):
        td = Path(tempfile.mkdtemp(prefix="pub-"))
        bare = td / "remote.git"
        self._git(td, "init", "-q", "--bare", str(bare))
        work = td / "work"
        self._git(td, "clone", "-q", str(bare), str(work))
        (work / "tracked.txt").write_text("v1\n")
        self._git(work, "add", "."); self._git(work, "commit", "-qm", "main")
        self._git(work, "push", "-q", "origin", "HEAD:refs/heads/main")
        if with_branch:
            # an existing preview-renders branch WITH history, made elsewhere
            other = td / "other"
            self._git(td, "clone", "-q", str(bare), str(other))
            self._git(other, "switch", "-q", "--orphan", "preview-renders")
            (other / "evidence").mkdir(); (other / "evidence" / "old.txt").write_text("keep me\n")
            self._git(other, "add", "-f", "evidence"); self._git(other, "commit", "-qm", "old evidence")
            self._git(other, "push", "-q", "origin", "preview-renders")
        # the render's checkout is DIRTY, exactly as on the runner
        (work / "tracked.txt").write_text("v2 dirty\n")
        stage = work / "output" / "review_media" / "reviews" / "20260921" / "x__abc"
        stage.mkdir(parents=True)
        (stage / "sheet.jpg").write_bytes(b"\xff\xd8jpeg")
        (stage / "f00.jpg").write_bytes(b"\xff\xd8jpeg")
        return td, bare, work

    def _run(self, work):
        return subprocess.run(["bash", str(ROOT / "scripts" / "publish_review_media.sh"),
                               "output/review_media"], cwd=work, capture_output=True, text=True,
                              env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"})

    def _remote_files(self, bare):
        return self._git(bare, "ls-tree", "-r", "--name-only", "preview-renders").split()

    def test_publishes_onto_an_existing_branch_from_a_dirty_checkout(self):
        td, bare, work = self._setup(with_branch=True)
        branch_before = self._git(work, "rev-parse", "--abbrev-ref", "HEAD").strip()
        r = self._run(work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = self._remote_files(bare)
        self.assertIn("reviews/20260921/x__abc/sheet.jpg", files)
        self.assertIn("evidence/old.txt", files, "history on the branch was replaced")
        self.assertIn("published 2 file(s)", r.stdout)
        # the render's checkout is untouched: same branch, still dirty
        self.assertEqual(self._git(work, "rev-parse", "--abbrev-ref", "HEAD").strip(), branch_before)
        self.assertEqual((work / "tracked.txt").read_text(), "v2 dirty\n")

    def test_creates_the_branch_when_there_is_none(self):
        td, bare, work = self._setup(with_branch=False)
        r = self._run(work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("reviews/20260921/x__abc/f00.jpg", self._remote_files(bare))

    def test_nothing_staged_is_a_quiet_no_op(self):
        td, bare, work = self._setup(with_branch=True)
        import shutil
        shutil.rmtree(work / "output")
        r = self._run(work)
        self.assertEqual(r.returncode, 0)
        self.assertIn("nothing staged", r.stdout)

    def test_a_failed_push_is_loud_not_a_false_published(self):
        td, bare, work = self._setup(with_branch=True)
        # make the remote refuse every push (a pre-receive hook that says no)
        hook = bare / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho refused >&2\nexit 1\n")
        os.chmod(hook, 0o755)
        r = self._run(work)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("published", r.stdout)
        self.assertIn("could not push", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()


class TheRepairPlannerSaysWhyItCannotPlan(unittest.TestCase):
    """`max() arg is an empty sequence` (invasive-species-price-tag, 21:48
    UTC) was a scene whose shape had NO repair candidate. Say that."""

    def test_no_candidates_is_a_named_error_not_a_max_crash(self):
        import inspect
        from scripts import scene_repair as R
        src = inspect.getsource(R.propose)
        self.assertIn("no repair candidate for seg", src)
        self.assertLess(src.index("no repair candidate for seg"),
                        src.index("max(survivors, key="),
                        "the empty case must be named before the chooser runs")
