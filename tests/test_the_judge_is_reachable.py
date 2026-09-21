"""A FAIL-CLOSED GATE WITH NO JUDGE HOLDS EVERYTHING.

2026-09-13. The explainer published nothing. Its own log:

    done: 0 posted, 85 held by the gate, 0 faults

Every un-posted story held PRE-render. Reproduced offline: 85 stories, 0
pass. The gate was not wrong — it was right, and had nobody to ask. Both
configured backends were down at the same moment:

    [llm] groq unavailable (HTTP Error 404)
    [llm] gemini unavailable (HTTP Error 429: Too Many Requests)

`beats_support_one_thesis` is a crude keyword-overlap test whose DESIGNED
escape hatch is a semantic judge, so with no judge it fails closed on stories
that are plainly on-topic — the headline "Americans Stopped Moving. Here's
Why." against a segment called "mortgage lock-in", which IS the why.

And a working Claude was in the same job the whole time. Every publishing
workflow already carries `CLAUDE_CODE_OAUTH_TOKEN` because the SHOWRUNNER
refuses to run without it. The judge simply never asked it.

This file holds the two halves that make that safe:

  - the brain is in the chain, and it is LAST, so it only runs when the free
    HTTP backends and the paid API have all failed;
  - it is BOUNDED, because the showrunner spends the same subscription and
    fails closed. An unbounded pre-render judge would drain the budget before
    the first render and then block the whole day — a worse outage than the
    one it fixes, arrived at by fixing it.

And the rule that governs the whole thing: THIS ADDS A JUDGE, IT DOES NOT
REMOVE ONE. No threshold moves and nothing gains a bypass.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import script_generator as sg          # noqa: E402
from scripts import editorial_gate as _eg          # noqa: E402


class TheBrainIsInTheChain(unittest.TestCase):

    def test_the_headless_brain_is_a_backend(self):
        self.assertIn("claude_cli", [n for n, _, _ in sg._LLM_CHAIN])

    def test_it_is_keyed_on_the_token_the_showrunner_already_needs(self):
        """CLAUDE.md: "any workflow that publishes MUST carry
        CLAUDE_CODE_OAUTH_TOKEN". That is why this backend costs nothing to
        add — it is already present wherever it would be used."""
        env = next(e for n, e, _ in sg._LLM_CHAIN if n == "claude_cli")
        self.assertEqual(env, "CLAUDE_CODE_OAUTH_TOKEN")

    def test_it_is_LAST_so_the_cheap_backends_go_first(self):
        """It spawns a process and spends a shared subscription, so it is the
        resort, not the default."""
        names = [n for n, _, _ in sg._LLM_CHAIN]
        # the last KEYED backend; the only thing after it is the mailbox,
        # which answers next run and needs no key (shared/llm_mailbox.py)
        keyed = [n for n, env, _ in sg._LLM_CHAIN if env]
        self.assertEqual(keyed[-1], "claude_cli")
        self.assertEqual(names[-1], "mailbox")
        for cheap in ("groq", "gemini"):
            self.assertLess(names.index(cheap), names.index("claude_cli"))


class ItCannotStarveTheShowrunner(unittest.TestCase):
    """The showrunner is the permanent quality authority and it FAILS CLOSED.
    A pre-render gate that spent its subscription would hold every video."""

    def test_there_is_a_bound_at_all(self):
        self.assertGreater(sg.CLAUDE_CLI_MAX_CALLS, 0)
        self.assertLess(sg.CLAUDE_CLI_MAX_CALLS, 200,
                        "a bound this high is not a bound — there are 85 "
                        "un-posted stories and the gate asks per story")

    def test_the_bound_actually_STOPS_it(self):
        before = sg._CLAUDE_CLI_CALLS
        try:
            sg._CLAUDE_CLI_CALLS = sg.CLAUDE_CLI_MAX_CALLS
            with self.assertRaises(RuntimeError) as cm:
                sg._call_claude_cli("sys", "user")
            self.assertIn("budget", str(cm.exception).lower())
        finally:
            sg._CLAUDE_CLI_CALLS = before

    def test_a_spent_budget_falls_through_like_any_outage(self):
        """It must RAISE, not return something — `_call_llm` walks the chain
        on exceptions, and a gate treats a non-verdict as unavailable."""
        import inspect
        src = inspect.getsource(sg._call_claude_cli)
        self.assertIn("raise RuntimeError", src)

    def test_the_showrunner_does_not_go_through_this_counter(self):
        """It shells the CLI itself, so the gate's allowance cannot reach it.
        If that ever changes, the two start competing for one budget."""
        src = (ROOT / "scripts" / "showrunner_review.py").read_text()
        self.assertNotIn("_call_llm", src)
        self.assertNotIn("CLAUDE_CLI_MAX_CALLS", src)


class ItADDSAJudgeAndRemovesNothing(unittest.TestCase):
    """The line that must never be crossed: "a video always posts" cannot
    mean "a video posts anyway"."""

    def test_an_unavailable_judge_still_HOLDS(self):
        """With no backend reachable the deterministic floor stands — the
        story is held, exactly as before. The change is only that
        'unavailable' stops being the answer when a brain IS reachable."""
        sc = {"title": "Americans Stopped Moving. Here's Why.",
              "hook": "1 in 5 Americans used to move every year.",
              "segments": [{"topic": "share of Americans who moved"},
                           {"topic": "mortgage lock-in"},
                           {"topic": "workers needing a license"}]}
        v = _eg.beats_support_one_thesis(sc, use_llm=False)
        self.assertFalse(v["ok"], "the floor stopped holding without a judge")

    def test_only_an_exact_true_counts_as_a_pass(self):
        """A missing key, the string "true", or anything else is UNAVAILABLE,
        not a bridge. Adding a backend must not soften that."""
        import inspect
        src = inspect.getsource(_eg.beats_support_one_thesis)
        self.assertIn("is True", src)

    def test_no_gate_threshold_moved_with_this_change(self):
        """The premise floor is still a digit in the title or hook, and the
        thesis floor is still keyword overlap. If a future change wants to
        move either, it does not get to do it under cover of adding a
        judge."""
        self.assertEqual(_eg._NUM_RE.pattern, r"\d")
        sc = {"title": "A Quiet Thing Happened", "hook": "No numbers here.",
              "segments": []}
        self.assertFalse(_eg.premise_ok(sc, use_llm=False)["ok"])


if __name__ == "__main__":
    unittest.main()
