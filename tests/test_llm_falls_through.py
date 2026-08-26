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
    def test_order_is_groq_then_gemini_then_anthropic(self):
        self.assertEqual([n for n, _e, _c in sg._LLM_CHAIN],
                         ["groq", "gemini", "anthropic"])

    def test_each_entry_names_its_own_env_var(self):
        for name, env, _call in sg._LLM_CHAIN:
            self.assertEqual(env, f"{name.upper()}_API_KEY")


class TestDailyRepairUsesTheFallbackChain(unittest.TestCase):
    """The production call site must not defeat _call_llm's fallback."""

    def test_trending_repair_does_not_pin_groq(self):
        import ast

        source = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        tree = ast.parse(source)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "generate"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "script_generator"
        ]
        self.assertTrue(calls, "script_generator.generate call not found")
        for call in calls:
            self.assertNotIn(
                "backend",
                {kw.arg for kw in call.keywords},
                "pinning backend='groq' disables the configured fallback chain",
            )


if __name__ == "__main__":
    unittest.main()
