"""Aletheia answers the mailbox — and code still decides.

Operator, 2026-09-30, after ChatGPT had answered none of 61 review
requests, 681 rewrites or ~100 asks in nine days: *"yes, obviously let
Alethea answer the mailbox ... I just need Alethea to make sure shit gets
posted"* — and *"We're not posting bad stuff."*

  1. A verdict names its grader and the ledger records THAT grader; an
     Aletheia verdict goes through the identical assemble_verdict + gate,
     so low grades are a hold whoever wrote them.
  2. Rewritten words record who wrote them.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from tests.test_the_judge_of_last_resort_is_chatgpt import (  # noqa: E402
    CR, RM, SR, _Sandbox, _good_grades)
from shared import rewrite_mailbox as RW


class AGraderIsNamedAndTheGateIsTheSame(_Sandbox):
    def _answer(self, req, by, grades):
        (Path(req["_path"]).parent / f"{req['id']}.verdict.json").write_text(json.dumps(
            {"schema": RM.VERDICT_SCHEMA, "request_id": req["id"],
             "video_sha256": req["video_sha256"], "by": by, "grades": grades}))

    def test_grader_names(self):
        self.assertEqual(RM.grader_of("aletheia:local qwen3-vl:4b"), "aletheia-mailbox")
        self.assertEqual(RM.grader_of("Aletheia"), "aletheia-mailbox")
        self.assertEqual(RM.grader_of("chatgpt"), "chatgpt-mailbox")
        self.assertEqual(RM.grader_of(""), "chatgpt-mailbox")

    def test_aletheias_low_grades_are_a_hold_logged_as_hers(self):
        rid = self._file()
        req = next(r for r in RM.open_requests(self.reviews) if r["id"] == rid)
        g = _good_grades(); g["dimensions"] = {k: 0 for k in SR.WEIGHTS}
        g["one_line"] = "ship it"
        self._answer(req, "aletheia:codex", g)
        led = []
        with mock.patch.object(SR, "temporal_grade", lambda t: 0), \
                mock.patch.object(SR, "apply_motion_override", lambda c, m: c), \
                mock.patch.object(SR, "append_ledger", lambda s, v: led.append((s, v))):
            res = CR.claim(req, publish=False, workdir=self.td)
        self.assertEqual(res["decision"], "hold")
        self.assertEqual(res["judge"], "aletheia-mailbox")
        self.assertEqual(led[0][1]["judge"], "aletheia-mailbox")


class RewrittenWordsSayWhoWroteThem(_Sandbox):
    def test_words_by(self):
        self.assertEqual(RW.words_by({"by": "aletheia:claude"}), "aletheia-rewrite")
        self.assertEqual(RW.words_by({"by": "chatgpt"}), "chatgpt-rewrite")
        self.assertEqual(RW.words_by({}), "chatgpt-rewrite")
        cfg = {"stories": [{"slug": "s"}]}
        self.assertTrue(RW.apply(cfg, {"slug": "s"}, "aletheia-rewrite"))
        self.assertEqual(cfg["stories"][0]["words_by"], "aletheia-rewrite")
