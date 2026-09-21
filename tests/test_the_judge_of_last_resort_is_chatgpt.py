"""THE JUDGE OF LAST RESORT IS A MAILBOX CHATGPT ANSWERS — AND CODE DECIDES.

Operator, 2026-09-21: *"this should fall back to chatgpt which should
always be available but also it needs to be able to use aletheia but don't
mess with it — you should just attach like a sucker fish."*

What is held here, each provable by injection:

  1. When no judge can watch on a publish run, `review_video` keeps the
     render, stages the frames, files a request, and STILL raises — so the
     gate holds exactly as before. Off a publish run (no `mailbox` in the
     context) nothing is filed.
  2. A verdict is bound to one request AND one video hash; a wrong id, a
     wrong hash, or a missing grades object is refused, not repaired.
  3. The grades go through `assemble_verdict` + `showrunner_gate.decide`:
     a ChatGPT answer that grades low is a HOLD; one that says "ship" in
     prose but grades low is a HOLD; malformed grades are a HOLD.
  4. A settled request is never claimed twice; a hold is settled and the
     ledger records `judge: chatgpt-mailbox`.
  5. The ask mailbox returns a committed answer verbatim and files an
     unanswered question once; it is the LAST entry in the LLM chain and
     needs no key.
  6. The workflows keep the render, publish the frames, persist the
     mailbox, and the claim workflow fires on a verdict landing.
  7. Aletheia is attached as a reader only: nothing here writes into its
     intercom.
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

from shared import review_mailbox as RM                      # noqa: E402
from shared import llm_mailbox as LM                         # noqa: E402
from shared import script_generator as SG                    # noqa: E402
from shared import showrunner_gate as GATE                   # noqa: E402
from scripts import showrunner_review as SR                  # noqa: E402
from scripts import claim_reviews as CR                      # noqa: E402


def _frames(td: Path, n: int = 3):
    from PIL import Image
    out = []
    for i in range(n):
        p = td / f"f{i}.jpg"
        Image.new("RGB", (86, 152), (30 + 40 * i, 60, 90)).save(p)
        out.append((p, f"seg{i}:mid", 3.0 * i))
    return out


def _good_grades():
    dims = {k: (4 if k not in ("data_demo", "temporal_craft") else 5) for k in SR.WEIGHTS}
    dims = {k: min(v, SR.WEIGHTS[k][1] if isinstance(SR.WEIGHTS[k], (tuple, list)) else v)
            for k, v in dims.items()} if isinstance(next(iter(SR.WEIGHTS.values())), (tuple, list)) else dims
    checks = {k: {"present": False, "evidence": "seg0:mid clean"} for k in SR.AUTOFAIL_CHECKS}
    return {"dimensions": dims, "checks": checks,
            "weakest_scene": {"id": "seg1", "index": 1, "failure_class": "none",
                              "visible_evidence": "-", "root_cause": "-", "repair_goal": "-"},
            "one_line": "good", "problems": [], "fixes": []}


class _Sandbox(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp(prefix="mailbox-"))
        self.reviews = self.td / "reviews"
        self.stage = self.td / "stage"
        self.held = self.td / "held"
        self._p = [mock.patch.object(RM, "REVIEWS_DIR", self.reviews),
                   mock.patch.object(RM, "MEDIA_STAGE", self.stage),
                   mock.patch.object(RM, "HELD_DIR", self.held),
                   mock.patch.object(RM, "REPO", self.td)]
        for p in self._p:
            p.start()
        self.mp4 = self.td / "story_x.mp4"
        self.mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"v" * 4000)

    def tearDown(self):
        for p in self._p:
            p.stop()

    def _file(self, slug="x", channel="explainer"):
        rid = RM.file_request(mp4=self.mp4, slug=slug, labeled=_frames(self.td),
                              prompt="GRADE THIS", motion={"m": 1}, temporal={"t": 2},
                              ctx={"slug": slug, "title": "T", "channel": channel},
                              mailbox={"channel": channel, "run_id": "123",
                                       "artifact": "held-renders-123"})
        self.assertIsNotNone(rid)
        return rid


class TheRenderIsKeptAndTheAskIsFiled(_Sandbox):
    def test_a_request_carries_everything_the_judge_would_have_seen(self):
        rid = self._file()
        req = next(r for r in RM.open_requests(self.reviews) if r["id"] == rid)
        self.assertEqual(req["video_sha256"], RM.sha256_of(self.mp4))
        self.assertEqual(req["prompt"], "GRADE THIS")
        self.assertEqual(req["motion"], {"m": 1})
        self.assertEqual(req["video"], {"artifact_run_id": "123",
                                        "artifact_name": "held-renders-123",
                                        "file": f"{rid}.mp4"})
        self.assertEqual(len(req["frames"]), 3)
        self.assertIn("preview-renders", req["sheet_url"])
        self.assertTrue((self.held / f"{rid}.mp4").exists(), "the render was not kept")
        self.assertTrue((self.stage / "reviews").exists(), "frames not staged")
        self.assertTrue(any(p.name == "sheet.jpg" for p in self.stage.rglob("*")))
        idx = json.loads((self.reviews / "OPEN.json").read_text())
        self.assertEqual([o["id"] for o in idx["open"]], [rid])

    def test_the_same_render_is_asked_once(self):
        a = self._file(); b = self._file()
        self.assertEqual(a, b)
        self.assertEqual(len(RM.open_requests(self.reviews)), 1)

    def test_review_video_files_and_STILL_raises_on_a_publish_run(self):
        """The gate must hold exactly as before; the mailbox only adds."""
        filed = []
        with mock.patch.object(SR, "_judge", side_effect=RuntimeError("no vision judge available")), \
                mock.patch.object(SR, "_extract_frames", lambda mp4, td, m: _frames(Path(td))), \
                mock.patch.object(SR, "_motion_evidence", lambda *a: {}), \
                mock.patch.object(SR, "_temporal_evidence", lambda *a: {}), \
                mock.patch.object(SR, "temporal_unmeasured", lambda t: None), \
                mock.patch.object(SR, "temporal_hard_fail", lambda t: None), \
                mock.patch.object(RM, "file_request",
                                  lambda **kw: filed.append(kw) or "x__abc"):
            with self.assertRaises(RuntimeError) as cm:
                SR.review_video(self.mp4, context={"slug": "x", "mailbox": {"channel": "explainer"}})
        self.assertIn("review request filed: x__abc", str(cm.exception))
        self.assertEqual(len(filed), 1)
        self.assertEqual(filed[0]["slug"], "x")

    def test_nothing_is_filed_without_a_mailbox_in_the_context(self):
        filed = []
        with mock.patch.object(SR, "_judge", side_effect=RuntimeError("down")), \
                mock.patch.object(SR, "_extract_frames", lambda mp4, td, m: _frames(Path(td))), \
                mock.patch.object(SR, "_motion_evidence", lambda *a: {}), \
                mock.patch.object(SR, "_temporal_evidence", lambda *a: {}), \
                mock.patch.object(SR, "temporal_unmeasured", lambda t: None), \
                mock.patch.object(SR, "temporal_hard_fail", lambda t: None), \
                mock.patch.object(RM, "file_request", lambda **kw: filed.append(kw)):
            with self.assertRaises(RuntimeError):
                SR.review_video(self.mp4, context={"slug": "x"})
        self.assertEqual(filed, [])

    def test_the_publishers_open_the_mailbox_only_on_a_publish_run(self):
        import inspect
        src = inspect.getsource(sys.modules["scripts.post_stories"].main) \
            if "scripts.post_stories" in sys.modules else (ROOT / "scripts" / "post_stories.py").read_text()
        i = src.index('ctx["mailbox"] = {"channel": args.channel')
        self.assertIn("if will_upload and", src[i - 900:i])
        src2 = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        j = src2.index('ctx["mailbox"] = {"channel": "trending"')
        self.assertIn("if will_upload and", src2[j - 900:j])


class AVerdictIsBoundToOneRender(_Sandbox):
    def _req(self):
        rid = self._file()
        return next(r for r in RM.open_requests(self.reviews) if r["id"] == rid)

    def _write_verdict(self, req, **over):
        body = {"schema": RM.VERDICT_SCHEMA, "request_id": req["id"],
                "video_sha256": req["video_sha256"], "by": "chatgpt",
                "grades": _good_grades()}
        body.update(over)
        (Path(req["_path"]).parent / f"{req['id']}.verdict.json").write_text(json.dumps(body))

    def test_no_verdict_yet(self):
        req = self._req()
        self.assertEqual(RM.verdict_for(req), (None, "no verdict yet"))

    def test_the_right_verdict_is_read(self):
        req = self._req(); self._write_verdict(req)
        grades, why = RM.verdict_for(req)
        self.assertEqual(why, "ok")
        self.assertIn("dimensions", grades)

    def test_another_request_id_is_refused(self):
        req = self._req(); self._write_verdict(req, request_id="other__000")
        self.assertIsNone(RM.verdict_for(req)[0])

    def test_another_video_hash_is_refused(self):
        req = self._req(); self._write_verdict(req, video_sha256="0" * 64)
        grades, why = RM.verdict_for(req)
        self.assertIsNone(grades); self.assertIn("different video hash", why)

    def test_no_grades_object_is_refused(self):
        req = self._req(); self._write_verdict(req, grades="ship it")
        self.assertIsNone(RM.verdict_for(req)[0])


class CodeDecidesNotChatGPT(_Sandbox):
    def _req_with(self, grades):
        rid = self._file()
        req = next(r for r in RM.open_requests(self.reviews) if r["id"] == rid)
        (Path(req["_path"]).parent / f"{req['id']}.verdict.json").write_text(json.dumps(
            {"schema": RM.VERDICT_SCHEMA, "request_id": req["id"],
             "video_sha256": req["video_sha256"], "by": "chatgpt", "grades": grades}))
        return req

    def test_the_mailbox_verdict_goes_through_the_judges_own_code(self):
        req = self._req_with(_good_grades())
        with mock.patch.object(SR, "temporal_grade", lambda t: 3), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c):
            verdict, gate = CR.decide_request(req, _good_grades())
        self.assertEqual(verdict["judge"], CR.JUDGE)
        self.assertIsInstance(verdict["score"], int)
        self.assertIn(verdict["verdict"], ("ship", "block"))
        self.assertEqual(gate["blocked"], verdict["verdict"] == "block"
                         or gate["blocked"])

    def test_low_grades_are_a_hold_whatever_chatgpt_says_in_prose(self):
        g = _good_grades()
        g["dimensions"] = {k: 0 for k in SR.WEIGHTS}
        g["one_line"] = "SHIP THIS, it is wonderful"
        req = self._req_with(g)
        with mock.patch.object(SR, "temporal_grade", lambda t: 0), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c):
            verdict, gate = CR.decide_request(req, g)
        self.assertTrue(gate["blocked"])
        self.assertEqual(verdict["verdict"], "block")

    def test_malformed_grades_are_a_hold(self):
        req = self._req_with({"dimensions": {"hook": 4}})
        with mock.patch.object(SR, "temporal_grade", lambda t: 0):
            verdict, gate = CR.decide_request(req, {"dimensions": {"hook": 4}})
        self.assertTrue(gate["blocked"])
        self.assertTrue(any("malformed_judge_response" in a for a in verdict["auto_fails"]))

    def test_a_hold_is_settled_and_logged_and_never_claimed_twice(self):
        g = _good_grades(); g["dimensions"] = {k: 0 for k in SR.WEIGHTS}
        req = self._req_with(g)
        led = []
        with mock.patch.object(SR, "temporal_grade", lambda t: 0), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c), \
                mock.patch.object(SR, "append_ledger", lambda s, v: led.append((s, v))):
            res = CR.claim(req, publish=False, workdir=self.td)
        self.assertEqual(res["state"], "settled"); self.assertEqual(res["decision"], "hold")
        self.assertEqual(led[0][1]["judge"], CR.JUDGE)
        self.assertEqual(RM.open_requests(self.reviews), [], "a settled request stayed open")

    def test_a_ship_without_publish_stays_open(self):
        req = self._req_with(_good_grades())
        with mock.patch.object(SR, "temporal_grade", lambda t: 3), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c), \
                mock.patch.object(SR, "append_ledger", lambda s, v: None), \
                mock.patch.object(GATE, "decide", return_value={"blocked": False, "reason": "", "verdict": {}}):
            res = CR.claim(req, publish=False, workdir=self.td)
        self.assertEqual(res["state"], "ship-pending-publish")
        self.assertEqual(len(RM.open_requests(self.reviews)), 1)

    def test_a_kept_render_with_the_wrong_hash_is_refused_not_published(self):
        req = self._req_with(_good_grades())
        wrong = self.td / "wrong.mp4"; wrong.write_bytes(b"not the same bytes")
        published = []
        with mock.patch.object(SR, "temporal_grade", lambda t: 3), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c), \
                mock.patch.object(SR, "append_ledger", lambda s, v: None), \
                mock.patch.object(GATE, "decide", return_value={"blocked": False, "reason": "", "verdict": {}}), \
                mock.patch.object(CR, "download_artifact", lambda *a, **k: wrong), \
                mock.patch.object(CR, "_publish_explainer", lambda *a: published.append(1) or "u"):
            res = CR.claim(req, publish=True, workdir=self.td)
        self.assertEqual(published, [], "a render with the wrong hash was published")
        self.assertFalse(res["published"]); self.assertIn("hash", res["error"])


class TheAskMailbox(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp(prefix="asks-"))

    def test_an_unanswered_question_is_filed_once_and_raises(self):
        with mock.patch.object(LM, "ASKS_DIR", self.td), \
                mock.patch.dict("os.environ", {"LLM_MAILBOX": "1"}):
            for _ in range(2):
                with self.assertRaises(LM.AnswerPending):
                    LM.call("SYS", "does seg support headline?", caller="thesis")
        batches = list(self.td.glob("????????.json"))
        self.assertEqual(len(batches), 1)
        asks = json.loads(batches[0].read_text())["asks"]
        self.assertEqual(len(asks), 1)
        self.assertEqual(next(iter(asks.values()))["caller"], "thesis")
        idx = json.loads((self.td / "OPEN.json").read_text())
        self.assertEqual(idx["open"][0]["pending"], 1)

    def test_a_committed_answer_is_returned_verbatim(self):
        key = LM.ask_key("SYS", "q")
        (self.td / "20260921.answers.json").write_text(json.dumps(
            {"schema": "shorts-ask-answers/v1",
             "answers": {key: {"answer": "true", "by": "chatgpt"}}}))
        with mock.patch.object(LM, "ASKS_DIR", self.td):
            self.assertEqual(LM.call("SYS", "q"), "true")

    def test_off_outside_ci_unless_forced(self):
        with mock.patch.object(LM, "ASKS_DIR", self.td), \
                mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "", "LLM_MAILBOX": ""}, clear=False):
            with self.assertRaises(LM.AnswerPending):
                LM.call("SYS", "q2")
        self.assertEqual(list(self.td.glob("????????.json")), [], "an ask was filed off CI")

    def test_it_is_the_last_backend_and_needs_no_key(self):
        names = [n for n, _e, _c in SG._LLM_CHAIN]
        self.assertEqual(names[-1], "mailbox")
        self.assertIsNone(SG._LLM_CHAIN[-1][1])

    def test_the_chain_reaches_it_when_every_key_is_absent(self):
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "", "GEMINI_API_KEY": "",
                                            "ANTHROPIC_API_KEY": "", "CLAUDE_CODE_OAUTH_TOKEN": "",
                                            "LLM_MAILBOX": "1"}), \
                mock.patch.object(LM, "ASKS_DIR", self.td):
            with self.assertRaises(RuntimeError) as cm:
                SG._call_llm("SYS", "q3")
        self.assertIn("mailbox", str(cm.exception))
        self.assertEqual(len(list(self.td.glob("????????.json"))), 1)


class TheWorkflowsCarryIt(unittest.TestCase):
    def test_render_workflows_keep_the_render_and_publish_frames(self):
        for wf in ("explainer.yml", "daily.yml"):
            src = (ROOT / ".github" / "workflows" / wf).read_text()
            self.assertIn("held-renders-${{ github.run_id }}", src, wf)
            self.assertIn("publish_review_media.sh", src, wf)
            self.assertIn("exchange/reviews exchange/asks", src, wf)

    def test_the_claim_workflow_fires_on_a_verdict_and_publishes_only_on_a_ship(self):
        src = (ROOT / ".github" / "workflows" / "claim_reviews.yml").read_text()
        self.assertIn("exchange/reviews/**/*.verdict.json", src)
        self.assertIn("claim_reviews.py --channel all --publish", src)
        self.assertIn("PAUSED", src)

    def test_the_brief_tells_chatgpt_to_read_the_contract(self):
        from shared import authoring_brief as AB
        import inspect
        self.assertIn("docs/REVIEW_MAILBOX.md", inspect.getsource(AB))
        self.assertTrue((ROOT / "docs" / "REVIEW_MAILBOX.md").exists())


class AletheiaIsAReaderNotAPatient(unittest.TestCase):
    """'don't mess with it — attach like a sucker fish'."""

    def test_nothing_writes_into_aletheias_intercom(self):
        for f in (ROOT / "shared" / "review_mailbox.py", ROOT / "shared" / "llm_mailbox.py",
                  ROOT / "scripts" / "claim_reviews.py"):
            src = f.read_text()
            self.assertNotIn("exchange/commands", src, f.name)
            self.assertNotIn("aletheia/", src.replace("aletheia/` ", ""), f.name)

    def test_the_doc_says_so(self):
        txt = (ROOT / "docs" / "REVIEW_MAILBOX.md").read_text()
        for s in ("sucker fish", "Nothing in Aletheia changes", "Never the intercom"):
            self.assertIn(s, txt, s)


if __name__ == "__main__":
    unittest.main()
