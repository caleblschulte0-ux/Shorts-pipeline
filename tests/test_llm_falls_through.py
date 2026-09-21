"""A rate-limited backend is not an outage.

2026-08-11. `_call_llm`'s docstring said "fall back to whichever has a
configured key", but the code only ever SELECTED one and then raised
whatever that one raised. Groq returned 429 all morning, so:

  * all four trending backfill attempts died — "[backfill] replacement also
    held: HTTP Error 429" x4 — which is the re-authoring path the whole
    "if something doesn't run properly, it goes through and tries again"
    ruling rests on;
  * the entity-media pass was skipped;
  * the candidate ranking fell back to unranked.

`GEMINI_API_KEY` was present and idle the entire time — the showrunner's
fallback judge requires it, and the run's own preflight had checked for it.

    python -m unittest tests.test_llm_falls_through -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import script_generator as sg  # noqa: E402


class ChainCase(unittest.TestCase):
    def setUp(self):
        self.calls: list[str] = []
        self._chain = sg._LLM_CHAIN

    def tearDown(self):
        sg._LLM_CHAIN = self._chain

    def chain(self, **behaviour):
        """behaviour: name -> "ok" | Exception | None (key not configured)."""
        def mk(name):
            def call(s, u, m):
                self.calls.append(name)
                out = behaviour[name]
                if isinstance(out, Exception):
                    raise out
                return f"{name} answered"
            return call
        sg._LLM_CHAIN = tuple(
            (n, f"{n.upper()}_KEY", mk(n)) for n in behaviour
            if behaviour[n] is not None)
        self._env = {f"{n.upper()}_KEY": "set" for n in behaviour
                     if behaviour[n] is not None}

    def call(self, **kw):
        import os
        old = dict(os.environ)
        try:
            os.environ.update(self._env)
            return sg._call_llm("sys", "user", **kw)
        finally:
            os.environ.clear()
            os.environ.update(old)


class TestItFallsThroughOnFailure(ChainCase):

    def test_the_2026_08_11_case_groq_429_gemini_answers(self):
        self.chain(groq=urllib_429(), gemini="ok")
        self.assertEqual(self.call(), "gemini answered")
        self.assertEqual(self.calls, ["groq", "gemini"])

    def test_the_first_working_backend_wins(self):
        self.chain(groq="ok", gemini="ok")
        self.assertEqual(self.call(), "groq answered")
        self.assertEqual(self.calls, ["groq"])

    def test_it_walks_the_whole_chain(self):
        self.chain(groq=urllib_429(), gemini=RuntimeError("down"),
                   anthropic="ok")
        self.assertEqual(self.call(), "anthropic answered")
        self.assertEqual(self.calls, ["groq", "gemini", "anthropic"])

    def test_every_backend_failing_names_every_failure(self):
        """The error a human reads has to say what was tried, or the next
        session re-diagnoses this from scratch."""
        self.chain(groq=urllib_429(), gemini=RuntimeError("quota"))
        with self.assertRaises(RuntimeError) as cm:
            self.call()
        msg = str(cm.exception)
        self.assertIn("groq", msg)
        self.assertIn("gemini", msg)
        self.assertIn("quota", msg)

    def test_an_unconfigured_backend_is_never_called(self):
        self.chain(groq=None, gemini="ok")
        self.assertEqual(self.call(), "gemini answered")
        self.assertEqual(self.calls, ["gemini"])

    def test_nothing_configured_still_says_how_to_configure_it(self):
        self.chain()
        with self.assertRaises(RuntimeError) as cm:
            self.call()
        self.assertIn("GROQ_API_KEY", str(cm.exception))


class TestAnExplicitBackendIsStillExact(ChainCase):
    """Callers that name a backend are usually pinning a capability (JSON
    mode, a vision model). Silently answering from a different one would be
    a worse bug than the outage this fixes."""

    def test_it_does_not_substitute(self):
        self.chain(groq=urllib_429(), gemini="ok")
        with self.assertRaises(Exception):
            self.call(backend="groq")
        self.assertEqual(self.calls, ["groq"])

    def test_it_does_not_require_the_env_var(self):
        """An explicit backend is the caller's business — the key check
        belongs to that backend's own call."""
        self.chain(gemini="ok")
        self.assertEqual(self.call(backend="gemini"), "gemini answered")

    def test_an_unknown_name_is_an_error_not_a_silent_default(self):
        self.chain(groq="ok")
        with self.assertRaises(RuntimeError):
            self.call(backend="llama-on-a-toaster")


def urllib_429():
    import urllib.error
    return urllib.error.HTTPError(
        "https://api.groq.com", 429, "Too Many Requests", None, None)


class TestTheRealChainIsStillWiredFreeFirst(unittest.TestCase):
    """The ORDER is the contract: free before paid, cheap before slow.

    This used to assert the exact list ["groq", "gemini", "anthropic"], which
    made it a test of the chain's LENGTH as much as its order — so adding the
    subscription brain on 2026-09-13 failed it twice for no defect. The
    ordering rule is what matters and it is what is asserted now; a fourth
    backend that broke the rule would still fail, and one that honours it
    does not have to edit this file to be allowed.
    """

    #: The two free HTTP backends, in the order they are tried.
    FREE = ("groq", "gemini")
    #: Costs money per call.
    PAID = ("anthropic",)
    #: The CLAUDE_CODE_OAUTH_TOKEN subscription — free, but it spawns a
    #: process and the SHOWRUNNER spends the same budget, so it goes last.
    SUBSCRIPTION = ("claude_cli",)
    #: The ChatGPT mailbox — no key, answers on the NEXT run
    #: (shared/llm_mailbox.py). Dead last: it cannot answer now.
    MAILBOX = ("mailbox",)

    def test_every_backend_is_accounted_for_here(self):
        """A new backend has to declare which kind it is, so the ordering
        rules below actually cover it instead of silently skipping it."""
        known = (set(self.FREE) | set(self.PAID) | set(self.SUBSCRIPTION)
                 | set(self.MAILBOX))
        names = {n for n, _e, _c in sg._LLM_CHAIN}
        self.assertEqual(names - known, set(),
                         "an unclassified backend — add it to FREE, PAID or "
                         "SUBSCRIPTION so its position is governed")

    def test_free_http_backends_come_first_and_in_order(self):
        names = [n for n, _e, _c in sg._LLM_CHAIN]
        self.assertEqual([n for n in names if n in self.FREE],
                         list(self.FREE))
        for free in self.FREE:
            for paid in self.PAID:
                if paid in names:
                    self.assertLess(names.index(free), names.index(paid),
                                    f"{paid} is tried before {free}")

    def test_the_subscription_brain_is_the_last_resort(self):
        """...of the backends that can answer NOW. The mailbox after it
        answers next run, so it never spends the subscription's turn."""
        names = [n for n, _e, _c in sg._LLM_CHAIN]
        keyed = [n for n, env, _c in sg._LLM_CHAIN if env]
        for sub in self.SUBSCRIPTION:
            if sub not in names:
                continue
            self.assertEqual(keyed[-1], sub,
                             "the showrunner shares this subscription — it "
                             "must only be reached once everything else has "
                             "failed")
        self.assertEqual(names[-1], self.MAILBOX[0])

    def test_each_entry_names_the_env_var_that_enables_it(self):
        """`_call_llm` SKIPS a backend whose env var is unset, so a wrong name
        here means the backend is silently never tried — which is exactly how
        a judge can be present and unreachable at the same time."""
        expected = {"claude_cli": "CLAUDE_CODE_OAUTH_TOKEN",
                    # the mailbox needs no key: env=None means "always
                    # configured" in `_call_llm` (it files the ask instead)
                    "mailbox": None}
        for name, env, _call in sg._LLM_CHAIN:
            self.assertEqual(env, expected.get(name, f"{name.upper()}_API_KEY"),
                             name)


if __name__ == "__main__":
    unittest.main()
