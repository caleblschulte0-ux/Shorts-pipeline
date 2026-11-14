"""The Twitch channel's run goes red on what its own records showed for
days before anyone looked (operator, 2026-11-14: "learn from this and
expand 10 times in every direction on every problem and fix them all"),
and the three things that produced those records are fixed.

    python -m pytest tests/test_twitch_channel_health_check.py -q
"""
from __future__ import annotations

import ast
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.append(str(REPO / "scripts"))

from scripts import third_health as h  # noqa: E402
from shared import channel_health  # noqa: E402
from third_capture import author  # noqa: E402

RUN_THIRD = (REPO / "scripts" / "run_third.py").read_text()


def _run(*clips, **kw):
    return {"ts": "2026-11-15T12:00:00+00:00", "dry_run": False,
            "brain": kw.get("brain", {"ok": 3, "fail": 0}),
            "clips": list(clips)}


FLOOR_SKIP = {"slug": "s", "ok": False, "skipped":
              "quality floor: best banger 0.20 < 0.25 (hard floor) across "
              "8 candidates — nothing worth transcribing"}
POSTED = {"slug": "p", "ok": True, "render_level": "full"}
ALREADY = {"slug": "a", "ok": True, "skipped": "already posted"}


class TheCheck(unittest.TestCase):
    def test_three_days_of_unwatched_skips_is_a_failure(self):
        # 2026-11-08..10, as recorded: every slot skipped on 0.20
        runs = [_run(*[FLOOR_SKIP] * 6) for _ in range(3)]
        got = h.problems(runs)
        self.assertTrue(any("not one video shipped" in p for p in got))
        self.assertTrue(any("before a clip was watched" in p for p in got))

    def test_a_crash_is_a_failure_and_a_gate_is_not(self):
        crash = {"slug": "c", "ok": False,
                 "error": "JSONDecodeError: Extra data: line 1"}
        gate = {"slug": "g", "ok": False, "error":
                "RuntimeError: content gate: transcript-aware score 0.30"}
        self.assertTrue(any("crashed" in p for p in
                            h.problems([_run(crash, POSTED)])))
        self.assertEqual(h.problems([_run(gate, POSTED)]), [])

    def test_a_story_renderer_crash_is_a_failure(self):
        slot = {"slug": "s", "ok": True, "judges": {"story_director": {
            "clusters": [{"cluster": "x", "outcome": "render_failed",
                          "why": "KeyError: 'beats'"}]}}}
        self.assertTrue(any("crashed" in p for p in
                            h.problems([_run(slot, POSTED)])))

    def test_qa_refusing_most_renders_is_a_failure(self):
        bad = {"slug": "b", "ok": False, "render_level": "full",
               "error": "RuntimeError: qa_rejected: vision: The sharp "
                        "picture is a thin strip"}
        got = h.problems([_run(bad, bad, bad, POSTED)])
        self.assertTrue(any("refused by QA" in p for p in got))

    def test_the_same_story_refused_again_and_again_is_a_failure(self):
        slot = {"slug": "s", "ok": True, "judges": {"story_director": {
            "clusters": [{"cluster": "scout:ohnepixel/leopard",
                          "outcome": "duration",
                          "why": "21s outside 25-90s"}]}}}
        got = h.problems([_run(slot, POSTED) for _ in range(3)])
        self.assertTrue(any("nobody remembered" in p for p in got))

    def test_a_healthy_day_passes(self):
        runs = [_run(POSTED, POSTED, FLOOR_SKIP, ALREADY),
                _run(ALREADY, ALREADY, ALREADY),
                _run(POSTED, {"slug": "g", "ok": False, "render_level":
                              "full", "error": "RuntimeError: qa_rejected: "
                              "render_qa: freeze"})]
        self.assertEqual(h.problems(runs), [])

    def test_a_day_with_every_slot_already_posted_is_not_a_dry_day(self):
        self.assertEqual(h.problems([_run(ALREADY) for _ in range(4)]), [])

    def test_dry_runs_and_runs_before_the_floor_do_not_count(self):
        dry = dict(_run(*[FLOOR_SKIP] * 6), dry_run=True)
        self.assertEqual(h.problems([dry, dry, dry]), [])
        old = dict(_run(*[FLOOR_SKIP] * 6), ts="2026-11-09T12:00:00")
        kept = channel_health.window([old] * 3, 3,
                                     today=dt.date(2026, 11, 15))
        self.assertEqual(kept, [])

    def test_it_runs_last_in_the_posting_workflow(self):
        wf = (REPO / ".github" / "workflows" / "third.yml").read_text()
        self.assertIn("python3 scripts/third_health.py", wf)
        self.assertGreater(wf.index("scripts/third_health.py"),
                           wf.index("Commit posted log + analytics"))


class ARankingThatRanksNothing(unittest.TestCase):
    """2026-11-08..10: the fallback judge scored every candidate 0.20."""

    def _rank(self, scores):
        clips = [{"url": f"u{i}", "channel": "x", "title": f"t{i}"}
                 for i in range(len(scores))]
        reply = {"scores": [{"i": i, "banger": b, "why": "no clear event"}
                            for i, b in enumerate(scores)]}
        with mock.patch.object(author, "_call_claude", return_value=None), \
                mock.patch.object(author, "_call_text_fallback",
                                  return_value=reply):
            return author.rank_clips(clips)

    def test_one_score_for_eight_titles_is_no_ranking(self):
        self.assertEqual(self._rank([0.2] * 8), {})

    def test_a_real_ranking_is_kept(self):
        got = self._rank([0.2, 0.2, 0.7, 0.4, 0.2])
        self.assertEqual(got["u2"][0], 0.7)
        self.assertEqual(len(got), 5)

    def test_a_small_slate_may_tie(self):
        self.assertEqual(len(self._rank([0.2, 0.2])), 2)


def _fn(name: str) -> ast.AST:
    tree = ast.parse(RUN_THIRD)
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(node: ast.AST) -> set[str]:
    return {n.func.id for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


class TheSimpleRenderIsNotTheSamePictureAgain(unittest.TestCase):
    """2026-11-11..13: 12 self-heals, 10 rejected again for the thin strip
    the first render was rejected for — the blur fill rendered twice."""

    def test_a_blur_fill_is_not_rendered_again(self):
        import run_third
        self.assertFalse(run_third.self_heal_differs({"reframe": "blur"}))
        self.assertFalse(run_third.self_heal_differs({}))
        self.assertTrue(run_third.self_heal_differs({"reframe": "cameras"}))

    def test_the_slot_loop_asks_before_self_healing(self):
        self.assertIn("self_heal_differs", _calls(_fn("process")))


def _ifs_with_verdict(fn: ast.AST, outcome: str) -> list[ast.If]:
    out = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        for stmt in node.body:
            for c in ast.walk(stmt):
                if (isinstance(c, ast.Call)
                        and isinstance(c.func, ast.Name)
                        and c.func.id == "_story_verdict"
                        and len(c.args) > 1
                        and isinstance(c.args[1], ast.Constant)
                        and c.args[1].value == outcome):
                    out.append(node)
    return out


class ARenderedRefusalIsRemembered(unittest.TestCase):
    def test_a_story_too_short_is_not_rendered_again(self):
        tree = ast.parse(RUN_THIRD)
        hits = [i for i in _ifs_with_verdict(tree, "duration")]
        self.assertTrue(hits)
        for node in hits:
            self.assertIn("_remember_refused",
                          {n.func.id for s in node.body for n in ast.walk(s)
                           if isinstance(n, ast.Call)
                           and isinstance(n.func, ast.Name)})

    def test_a_story_render_crash_is_on_the_record(self):
        tree = ast.parse(RUN_THIRD)

        def _renders(stmt):
            # the statement itself calls render_story (not a nested block)
            return (isinstance(stmt, (ast.Assign, ast.Expr))
                    and any(isinstance(c, ast.Call)
                            and isinstance(c.func, ast.Attribute)
                            and c.func.attr == "render_story"
                            for c in ast.walk(stmt)))
        # the rough cut: a crash there drops the story (`continue`)
        tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)
                 and any(_renders(s) for s in n.body)
                 and any(isinstance(h_.body[-1], ast.Continue)
                         for h_ in n.handlers)]
        self.assertTrue(tries)
        for t in tries:
            outcomes = {c.args[1].value for h_ in t.handlers
                        for c in ast.walk(h_)
                        if isinstance(c, ast.Call)
                        and isinstance(c.func, ast.Name)
                        and c.func.id == "_story_verdict"
                        and isinstance(c.args[1], ast.Constant)}
            self.assertIn("render_failed", outcomes)

if __name__ == "__main__":
    unittest.main()
