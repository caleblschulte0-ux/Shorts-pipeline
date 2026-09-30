"""The third channel has THREE judges, and the fallback one can see.

2026-09-27 and 2026-09-29 posted ZERO. Claude was at its weekly limit, the
Groq fallback answered `413 Payload Too Large` (the director's scene reports
were bigger than Groq will accept) and then `429`, and the third channel had
no third rung at all — third.yml never even passed GEMINI_API_KEY. The
blind-slate and unjudged gates in run_third.py did exactly their job and
held the slate. The fix is more judges, never softer gates:

  * the text chain is Claude -> Groq -> Gemini,
  * Gemini gets the contact sheet as inline image data, so a vision verdict
    survives the CLI being out (saw_frames stays True, honestly),
  * the Groq prompt is bounded so a 413 cannot recur,
  * a Gemini 429 stops Gemini for the run instead of stampeding it,
  * the CLI's "You've hit your weekly limit" arms the Claude breaker.

    python -m pytest -q tests/test_third_has_three_judges.py
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from third_capture import author  # noqa: E402


class _Resp:
    def __init__(self, status: int, body=None, text: str = ""):
        self.status_code = status
        self._body = body or {}
        self.text = text or json.dumps(self._body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Client Error")


def _gemini_ok(obj: dict) -> _Resp:
    return _Resp(200, {"candidates": [{"content": {"parts": [
        {"text": json.dumps(obj)}]}, "finishReason": "STOP"}]})


def _groq_ok(obj: dict) -> _Resp:
    return _Resp(200, {"choices": [{"message": {"content": json.dumps(obj)}}]})


class _Isolated(unittest.TestCase):
    def setUp(self):
        self._snap = (dict(author._LIMIT_HIT), dict(author._BRAIN),
                      dict(author._GEMINI_LIMIT), dict(author._GROQ_REST))
        author._LIMIT_HIT.update(at="", detail="")
        author._GEMINI_LIMIT.update(at="", detail="")
        author._GROQ_REST.update(until=0.0)
        env = mock.patch.dict(os.environ, {"GROQ_API_KEY": "gk",
                                           "GEMINI_API_KEY": "mk"})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        for d, v in zip((author._LIMIT_HIT, author._BRAIN,
                         author._GEMINI_LIMIT, author._GROQ_REST), self._snap):
            d.clear()
            d.update(v)


class TheChainIsClaudeThenGroqThenGemini(_Isolated):
    def _rank(self, claude, groq, gemini):
        calls = []

        def rec(name, fn):
            def f(*a, **k):
                calls.append(name)
                return fn(*a, **k)
            return f
        with mock.patch.object(author, "_call_claude", rec("claude", claude)), \
                mock.patch.object(author, "_call_groq", rec("groq", groq)), \
                mock.patch.object(author, "_call_gemini", rec("gemini", gemini)):
            out = author.rank_clips([{"channel": "x", "views": 1, "vph": 1.0,
                                      "title": "t", "url": "u"}])
        return out, calls

    def test_order_when_everything_ahead_fails(self):
        def boom(*a, **k):
            raise RuntimeError("413 Client Error: Payload Too Large")
        out, calls = self._rank(
            lambda *a, **k: None, boom,
            lambda *a, **k: {"scores": [{"i": 0, "banger": 0.8, "why": "w"}]})
        self.assertEqual(calls, ["claude", "groq", "gemini"])
        self.assertEqual(out, {"u": (0.8, "w")})

    def test_gemini_is_not_asked_when_groq_answers(self):
        out, calls = self._rank(
            lambda *a, **k: None,
            lambda *a, **k: {"scores": [{"i": 0, "banger": 0.7}]},
            lambda *a, **k: self.fail("gemini asked after groq answered"))
        self.assertEqual(calls, ["claude", "groq"])

    def test_no_call_site_calls_groq_directly(self):
        """Every brain call site goes through the one fallback helper; a
        direct `_call_groq(` elsewhere is a site that has no Gemini rung."""
        for rel in ("third_capture/author.py", "third_capture/scene_analysis.py",
                    "third_capture/story_director.py"):
            src = (_REPO / rel).read_text(encoding="utf-8")
            # (_call_text_fallback holds it by reference, not a call)
            n = len(re.findall(r"(?<!def )\b_call_groq\(", src))
            self.assertEqual(n, 0, f"{rel} calls _call_groq directly")

    def test_author_package_names_the_provider_that_wrote_it(self):
        pkg = {"title": "Streamer Loses It Over A Chess Blunder",
               "hook": "HE DID NOT SEE IT", "hashtags": ["#twitch"],
               "caption": "c", "cta": "", "series": "fail"}
        with mock.patch.object(author, "_call_claude", return_value=None), \
                mock.patch.object(author, "_call_groq", return_value=None), \
                mock.patch.object(author, "_call_gemini", return_value=pkg), \
                mock.patch("builtins.print") as pr:
            meta = author.author_package("streamer", "clip", "he loses it", 10)
        self.assertIsNotNone(meta)
        said = " ".join(str(c.args[0]) for c in pr.call_args_list if c.args)
        self.assertIn("GEMINI FALLBACK authored", said)


class GeminiSeesTheContactSheet(_Isolated):
    def setUp(self):
        super().setUp()
        d = tempfile.mkdtemp()
        self.sheet = os.path.join(d, "clip.scene.jpg")
        self.jpeg = b"\xff\xd8\xff\xe0fake-jpeg-bytes\xff\xd9"
        with open(self.sheet, "wb") as fh:
            fh.write(self.jpeg)

    def test_judge_content_uses_gemini_vision_when_claude_fails(self):
        posted = []

        def post(url, **kw):
            posted.append((url, kw))
            return _gemini_ok({"scores": [{"i": 0, "banger": 0.82,
                                           "why": "visible fail"}]})
        before = dict(author._BRAIN)
        with mock.patch.object(author, "_call_claude",
                               side_effect=RuntimeError("claude exited rc=1")), \
                mock.patch("requests.post", side_effect=post):
            score, why, saw = author.judge_content(
                "streamer", "title", "some words", sheet=self.sheet, views=5)
        self.assertEqual((score, why, saw), (0.82, "visible fail", True))
        self.assertEqual(len(posted), 1, "one vision call, no text fallback")
        url, kw = posted[0]
        self.assertIn("gemini-2.5-flash", url)
        parts = kw["json"]["contents"][0]["parts"]
        inline = [p["inline_data"] for p in parts if "inline_data" in p]
        self.assertEqual(len(inline), 1, "the sheet must be ATTACHED")
        self.assertEqual(inline[0]["mime_type"], "image/jpeg")
        self.assertEqual(base64.b64decode(inline[0]["data"]), self.jpeg)
        self.assertEqual(kw["json"]["generationConfig"]["responseMimeType"],
                         "application/json")
        # one brain task, one honest ok
        self.assertEqual(author._BRAIN["ok"], before["ok"] + 1)
        self.assertEqual(author._BRAIN["fail"], before["fail"])

    def test_a_failed_gemini_vision_still_counts_and_falls_to_text(self):
        def post(url, **kw):
            if "gemini" in url and any("inline_data" in p for p in
                                       kw["json"]["contents"][0]["parts"]):
                return _Resp(500, {"error": "boom"})
            if "groq" in url:
                return _groq_ok({"scores": [{"i": 0, "banger": 0.6}]})
            self.fail("unexpected call " + url)
        before = dict(author._BRAIN)
        with mock.patch.object(author, "_call_claude", return_value=None), \
                mock.patch("requests.post", side_effect=post):
            score, _why, saw = author.judge_content(
                "s", "t", "words", sheet=self.sheet)
        self.assertEqual((score, saw), (0.6, False))
        self.assertEqual(author._BRAIN["fail"], before["fail"] + 1,
                         "the failed vision task is counted")
        self.assertEqual(author._BRAIN["ok"], before["ok"] + 1)

    def test_director_vision_review_accepts_gemini_that_looked(self):
        from third_capture import story_director as sd
        with mock.patch.object(sd, "_call_claude", return_value=None), \
                mock.patch("requests.post",
                           return_value=_gemini_ok({"publish": True})) as p:
            out = sd._brain("review", "sys", read_files=True,
                            require_vision=True, image_path=self.sheet)
        self.assertEqual(out, {"publish": True})
        parts = p.call_args.kwargs["json"]["contents"][0]["parts"]
        self.assertTrue(any("inline_data" in x for x in parts))

    def test_director_still_fails_closed_without_any_eyes(self):
        from third_capture import story_director as sd
        with mock.patch.object(sd, "_call_claude", return_value=None), \
                mock.patch.object(sd, "_call_gemini_vision",
                                  return_value=None), \
                mock.patch.object(sd, "_call_text_fallback",
                                  side_effect=AssertionError(
                                      "text-only judge used for a vision "
                                      "verdict")):
            self.assertIsNone(sd._brain("review", "sys", read_files=True,
                                        require_vision=True,
                                        image_path=self.sheet))


class GroqIsNeverSentMoreThanItAccepts(_Isolated):
    def test_the_groq_prompt_is_bounded(self):
        sent = {}

        def post(url, **kw):
            sent.update(kw["json"])
            return _groq_ok({"ok": 1})
        user = "HEAD " + ("x" * 200_000) + " TAIL-INSTRUCTION"
        with mock.patch("requests.post", side_effect=post):
            author._call_groq(user, system=author._RANK_SYSTEM)
        msgs = sent["messages"]
        total = sum(len(m["content"]) for m in msgs)
        self.assertLessEqual(total, author.GROQ_PROMPT_CHARS)
        self.assertTrue(msgs[1]["content"].startswith("HEAD "))
        self.assertTrue(msgs[1]["content"].endswith("TAIL-INSTRUCTION"))
        self.assertIn("truncated", msgs[1]["content"])

    def test_a_short_prompt_is_untouched(self):
        self.assertEqual(author._groq_bounded("short", "sys"), "short")

    def test_an_oversize_prompt_goes_to_gemini_whole_first(self):
        calls = []
        big = "y" * 50_000
        with mock.patch.object(author, "_call_groq",
                               side_effect=lambda *a, **k: calls.append("g")), \
                mock.patch.object(author, "_call_gemini",
                                  side_effect=lambda u, **k: (
                                      calls.append(("m", len(u))) or {"a": 1})):
            out = author._call_text_fallback(big, system="s")
        self.assertEqual(out, {"a": 1})
        self.assertEqual(calls, [("m", 50_000)])


class TheBreakersHold(_Isolated):
    def test_gemini_429_stops_gemini_for_the_run(self):
        with mock.patch("requests.post",
                        return_value=_Resp(429, {"error": "quota"})) as p:
            self.assertIsNone(author._call_gemini("u", "s"))
            self.assertIsNone(author._call_gemini("u", "s"))
        self.assertEqual(p.call_count, 1, "a 429 must not be retried")
        self.assertTrue(author.gemini_limited()["at"])

    def test_groq_429_rests_groq(self):
        with mock.patch("requests.post",
                        return_value=_Resp(429, {"error": "rate"})) as p:
            with self.assertRaises(Exception):
                author._call_groq("u", "s")
            self.assertIsNone(author._call_groq("u", "s"))
        self.assertEqual(p.call_count, 1)

    def test_the_weekly_limit_message_arms_the_claude_breaker(self):
        msg = "You've hit your weekly limit · resets Sep 30, 12am (UTC)"
        self.assertTrue(author._LIMIT_PAT.search(msg))
        self.assertFalse(author._LIMIT_PAT.search("fatal transport error"))


class TheWorkflowPassesTheKey(unittest.TestCase):
    def test_third_yml_passes_gemini_wherever_it_passes_groq(self):
        src = (_REPO / ".github/workflows/third.yml").read_text(
            encoding="utf-8")
        blocks = re.split(r"\n\s*- name:", src)
        groq = [b for b in blocks if "GROQ_API_KEY:" in b]
        self.assertTrue(groq, "third.yml no longer passes GROQ_API_KEY?")
        for b in groq:
            self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", b,
                          "a step with the Groq judge lacks the Gemini one")


if __name__ == "__main__":
    unittest.main()
