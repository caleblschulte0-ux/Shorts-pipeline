"""A HELD RENDER WAITS FOR A JUDGE — IT IS NEVER LOST FOR WANT OF A READER.

Operator, 2026-10-07: *"I thought between ChatGPT and Aletheia, we could
never have the issue of no judge available."* That was the design: a render
no judge could watch is kept and filed, so "no judge" only DELAYS it. But
from 09-21 to 10-07 nobody answered the mailbox, and 29 held renders sat
there after the headless brain's weekly limit had reset.

Held here, each by injection:

  1. `--rejudge` shows an unanswered request to the showrunner's own
     `_judge`, with the request's verbatim prompt and its frames, and writes
     the grades as the request's verdict, `by: showrunner:<backend>`.
  2. The ordinary claim then decides it with the same code as every judge:
     low grades are a HOLD, recorded as `showrunner-rejudge`.
  3. A judge that is still out leaves the request OPEN with no verdict, and
     is not asked again in the same run.
  4. A request that could never publish is withdrawn before any judge is
     spent on it; at most `limit` requests are re-judged, newest first.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest import mock

from tests.test_the_judge_of_last_resort_is_chatgpt import (  # noqa: E402
    CR, RM, SR, _Sandbox, _good_grades)


class _Rejudge(_Sandbox):
    def setUp(self):
        super().setUp()
        # frames are fetched from preview-renders in CI; here, from the stage
        self._f = mock.patch.object(CR, "_fetch", self._local_fetch)
        self._f.start()
        self._u = mock.patch.object(CR, "unpublishable", lambda req: None)
        self._u.start()

    def tearDown(self):
        self._f.stop(); self._u.stop()
        super().tearDown()

    def _local_fetch(self, url, dest):
        rel = url.split("/preview-renders/", 1)[1]
        shutil.copy2(self.stage / rel, dest)
        return dest

    def _req(self, rid):
        return next(r for r in RM.open_requests(self.reviews) if r["id"] == rid)


class TheShowrunnerAnswersWhatNobodyDid(_Rejudge):
    def test_the_verdict_is_the_judges_own_grades_on_the_requests_prompt(self):
        rid = self._file()
        seen = {}

        def judge(prompt, labeled):
            seen["prompt"], seen["n"] = prompt, len(labeled)
            seen["exist"] = all(Path(p).exists() for p, _, _ in labeled)
            return _good_grades(), "headless-claude"

        with mock.patch.object(SR, "_judge", judge):
            CR.rejudge_open(RM.open_requests(self.reviews), self.td)
        self.assertEqual(seen, {"prompt": "GRADE THIS", "n": 3, "exist": True})
        req = self._req(rid)
        v = json.loads((Path(req["_path"]).parent / f"{rid}.verdict.json").read_text())
        self.assertEqual(v["request_id"], rid)
        self.assertEqual(v["video_sha256"], req["video_sha256"])
        self.assertEqual(v["by"], "showrunner:headless-claude")
        self.assertEqual(RM.grader_of(v["by"]), "showrunner-rejudge")
        grades, why = RM.verdict_for(req)
        self.assertEqual(why, "ok")

    def test_low_grades_are_still_a_hold(self):
        rid = self._file()
        g = _good_grades(); g["dimensions"] = {k: 0 for k in SR.WEIGHTS}
        with mock.patch.object(SR, "_judge", lambda p, l: (g, "gemini-fallback")):
            CR.rejudge_open(RM.open_requests(self.reviews), self.td)
        led = []
        with mock.patch.object(SR, "temporal_grade", lambda t: 0), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c), \
                mock.patch.object(SR, "append_ledger", lambda s, v: led.append(v)):
            res = CR.claim(self._req(rid), publish=False, workdir=self.td)
        self.assertEqual(res["decision"], "hold")
        self.assertEqual(res["judge"], "showrunner-rejudge")
        self.assertEqual(led[0]["judge"], "showrunner-rejudge")


class AJudgeThatIsStillOutLeavesItOpen(_Rejudge):
    def test_no_verdict_and_asked_once(self):
        self._file(slug="a")
        self._file(slug="b")
        calls = []

        def out(prompt, labeled):
            calls.append(1)
            raise RuntimeError("no vision judge available. weekly limit")

        with mock.patch.object(SR, "_judge", out):
            left = CR.rejudge_open(RM.open_requests(self.reviews), self.td, limit=5)
        self.assertEqual(len(calls), 1, "an out judge was asked again in the same run")
        self.assertEqual(len(left), 2)
        self.assertFalse(any(RM.has_verdict(r) for r in RM.open_requests(self.reviews)))


class OnlyWhatCanPublishIsJudged(_Rejudge):
    def test_unpublishable_is_withdrawn_without_a_judge(self):
        rid = self._file(slug="gone")
        self._u.stop()
        with mock.patch.object(CR, "unpublishable", lambda req: "already posted"), \
                mock.patch.object(SR, "_judge", side_effect=AssertionError("judged")):
            left = CR.rejudge_open(RM.open_requests(self.reviews), self.td)
        self._u.start()
        self.assertEqual(left, [])
        done = json.loads((self.reviews.glob(f"*/{rid}.done.json").__next__()).read_text())
        self.assertEqual(done["decision"], "withdrawn")
        self.assertIn("already posted", done["reason"])

    def test_the_limit_holds(self):
        for s in ("a", "b", "c"):
            self._file(slug=s)
        with mock.patch.object(SR, "_judge", lambda p, l: (_good_grades(), "headless-claude")):
            CR.rejudge_open(RM.open_requests(self.reviews), self.td, limit=2)
        answered = [r for r in RM.open_requests(self.reviews) if RM.has_verdict(r)]
        self.assertEqual(len(answered), 2)


class TheWorkflowAsksForIt(_Sandbox):
    def test_claim_workflow_rejudges_with_the_brain_token(self):
        wf = (Path(CR.REPO) / ".github" / "workflows" / "claim_reviews.yml").read_text()
        self.assertIn("claim_reviews.py --channel all --publish --rejudge", wf)
        step = wf.split("- name: Decide, then publish only a code-decided ship", 1)[1]
        step = step.split("- name:", 1)[0]
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", step)
        self.assertIn("GEMINI_API_KEY", step)
        self.assertIn("@anthropic-ai/claude-code", wf)
