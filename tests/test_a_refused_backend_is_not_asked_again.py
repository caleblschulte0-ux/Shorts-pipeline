"""A BACKEND THAT JUST REFUSED US IS BENCHED, NOT RE-ASKED.

2026-11-24, explainer run 45318587673 (the eighth run in a row to post
nothing). GROQ_API_KEY had been dead for two weeks — state/credentials.json
said "HTTP 403 — the credential was refused", alarmed daily — and Groq
answered every one of the run's 39 `_call_llm` calls with 429. The chain
fell through to Gemini each time, as `tests/test_llm_falls_through.py`
requires, but only after `_call_groq` had slept through its six retries at
12 seconds apiece (GROQ_MAX_RETRIES=6 in explainer.yml):

    39 calls x 6 retries x ~12s = 3,086 seconds asleep

Fifty-one minutes of a 94-minute run spent asking a backend the run had
already found dead, while the one render it attempted ran out of drawing
time ("beat(s) [0, 2] have no verified scene ... the next run finishes
drawing it").

Held here: a rate limit benches its backend, doubling on each repeat; a
refused key benches it for the rest of the process; a benched backend is
skipped and the next one asked straight away; an answer clears the bench;
every OTHER failure is still re-asked next call (a 404 is a model pin to
fix, not a backend to abandon); an explicit `backend=` ignores the bench;
the total-failure message says who was benched and why.

    python -m unittest tests.test_a_refused_backend_is_not_asked_again -v
"""
from __future__ import annotations

import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import script_generator as sg  # noqa: E402


def http(code: int, msg: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.example", code, msg, None, None)


class BenchCase(unittest.TestCase):
    """A scripted chain: each backend answers from a queue of outcomes
    (a string answers; an exception is raised; the last outcome repeats)."""

    def setUp(self):
        self.calls: list[str] = []
        self._chain = sg._LLM_CHAIN
        self._env = dict(os.environ)
        self.clock = [1000.0]
        sg.reset_benches()
        self._tick = mock.patch.object(sg.time, "monotonic",
                                       lambda: self.clock[0])
        self._tick.start()

    def tearDown(self):
        self._tick.stop()
        sg._LLM_CHAIN = self._chain
        os.environ.clear()
        os.environ.update(self._env)
        sg.reset_benches()

    def chain(self, **script):
        def mk(name):
            queue = list(script[name])

            def call(s, u, m):
                self.calls.append(name)
                out = queue.pop(0) if len(queue) > 1 else queue[0]
                if isinstance(out, BaseException):
                    raise out
                return f"{name} answered"
            return call
        sg._LLM_CHAIN = tuple((n, f"{n.upper()}_KEY", mk(n)) for n in script)
        for n in script:
            os.environ[f"{n.upper()}_KEY"] = "set"

    def ask(self, **kw):
        return sg._call_llm("sys", "user", **kw)


class TestTheRunThatSleptFiftyOneMinutes(BenchCase):

    def test_a_rate_limited_backend_is_skipped_on_the_next_call(self):
        """Fails on the old code: calls were groq, gemini, groq, gemini."""
        self.chain(groq=[http(429, "Too Many Requests")], gemini=["ok"])
        self.assertEqual(self.ask(), "gemini answered")
        self.assertEqual(self.ask(), "gemini answered")
        self.assertEqual(self.calls, ["groq", "gemini", "gemini"])

    def test_thirty_nine_calls_pay_for_groq_once(self):
        self.chain(groq=[http(429)], gemini=["ok"])
        for _ in range(39):
            self.ask()
        self.assertEqual(self.calls.count("groq"), 1)
        self.assertEqual(self.calls.count("gemini"), 39)

    def test_the_bench_expires_and_the_backend_is_asked_again(self):
        self.chain(groq=[http(429), "ok"], gemini=["ok"])
        self.ask()
        self.clock[0] += sg.BENCH_BASE_S + 1
        self.assertEqual(self.ask(), "groq answered")
        self.assertEqual(self.calls, ["groq", "gemini", "groq"])

    def test_a_repeat_offender_sits_out_twice_as_long(self):
        self.chain(groq=[http(429)], gemini=["ok"])
        self.ask()                                     # strike 1: BASE
        self.clock[0] += sg.BENCH_BASE_S + 1
        self.ask()                                     # strike 2: 2 x BASE
        self.clock[0] += sg.BENCH_BASE_S + 1           # not yet
        self.ask()
        self.assertEqual(self.calls.count("groq"), 2)
        self.clock[0] += sg.BENCH_BASE_S + 1           # now
        self.ask()
        self.assertEqual(self.calls.count("groq"), 3)

    def test_the_bench_is_capped(self):
        self.chain(groq=[http(429)], gemini=["ok"])
        for _ in range(12):
            self.ask()
            self.clock[0] += sg.BENCH_MAX_S + 1
        self.assertEqual(self.calls.count("groq"), 12,
                         "a bench longer than BENCH_MAX_S")

    def test_a_refused_key_is_benched_for_the_whole_run(self):
        """The dead GROQ_API_KEY: 403 does not get better with time."""
        self.chain(groq=[http(403, "Forbidden")], gemini=["ok"])
        self.ask()
        self.clock[0] += 10 * sg.BENCH_MAX_S
        self.ask()
        self.assertEqual(self.calls, ["groq", "gemini", "gemini"])
        self.assertIn("refused the key", sg.benched("groq"))

    def test_an_answer_clears_the_bench_and_the_strikes(self):
        self.chain(groq=[http(429), "ok", http(429)], gemini=["ok"])
        self.ask()                                     # strike 1
        self.clock[0] += sg.BENCH_BASE_S + 1
        self.assertEqual(self.ask(), "groq answered")  # cleared
        self.assertIsNone(sg.benched("groq"))
        self.ask()                                     # 429 again: strike 1
        self.clock[0] += sg.BENCH_BASE_S + 1
        self.ask()                                     # BASE, not 2 x BASE
        self.assertEqual(self.calls.count("groq"), 4)


class TestNothingElseChanges(BenchCase):

    def test_any_other_failure_is_still_asked_again_next_call(self):
        """A 404 is a retired model pin (2026-08-16), a timeout is weather:
        the fall-through test's behaviour, call for call."""
        for exc in (http(404, "Not Found"), http(503, "Unavailable"),
                    RuntimeError("down"), TimeoutError("slow")):
            sg.reset_benches()
            self.calls.clear()
            self.chain(groq=[exc], gemini=["ok"])
            self.ask()
            self.ask()
            self.assertEqual(self.calls, ["groq", "gemini", "groq", "gemini"],
                             repr(exc))

    def test_an_explicit_backend_ignores_the_bench(self):
        self.chain(groq=[http(429), http(429)], gemini=["ok"])
        self.ask()
        with self.assertRaises(urllib.error.HTTPError):
            self.ask(backend="groq")
        self.assertEqual(self.calls, ["groq", "gemini", "groq"])

    def test_the_total_failure_names_the_bench(self):
        self.chain(groq=[http(429)], gemini=[RuntimeError("quota")])
        with self.assertRaises(RuntimeError):
            self.ask()
        with self.assertRaises(RuntimeError) as cm:
            self.ask()
        msg = str(cm.exception)
        self.assertIn("groq: benched", msg)
        self.assertIn("rate-limited", msg)
        self.assertIn("gemini", msg)

    def test_a_new_process_starts_clean(self):
        self.assertEqual(sg._BENCH, {})
        self.chain(groq=[http(429)], gemini=["ok"])
        self.ask()
        sg.reset_benches()
        self.assertIsNone(sg.benched("groq"))


class TestTheRealChainBenchesTheRealFailures(unittest.TestCase):

    def test_a_429_and_a_refused_key_bench_nothing_else_does(self):
        self.assertIn("429", sg.bench_reason(http(429)) or "")
        self.assertIn("403", sg.bench_reason(http(403)) or "")
        self.assertIn("401", sg.bench_reason(http(401)) or "")
        for exc in (http(404), http(500), http(503), RuntimeError("x"),
                    TimeoutError(), ValueError("bad json")):
            self.assertIsNone(sg.bench_reason(exc), repr(exc))

    def test_the_base_is_long_enough_to_matter_and_short_enough_to_recover(self):
        """Six Groq retries cost ~72s; a bench shorter than that would save
        nothing. An hour cap means a backend that recovers is back within
        the run."""
        self.assertGreaterEqual(sg.BENCH_BASE_S, 120)
        self.assertLessEqual(sg.BENCH_BASE_S, 900)
        self.assertEqual(sg.BENCH_MAX_S, 3600)


if __name__ == "__main__":
    unittest.main()
