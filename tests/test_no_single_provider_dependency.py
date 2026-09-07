"""No unattended path may depend on ONE model provider.

`_call_llm` walks the configured backends until one answers — free before
paid — but only when the caller does not name one. An explicit `backend=` is
exact by design: the caller asked for that one, so it gets that one's error
rather than a silent substitution. That is right for a caller that genuinely
needs a specific model, and wrong for every unattended production path.

It has cost this channel two days, the same way both times:

  2026-08-11  all four trending backfill attempts died on `HTTP Error 429`
              — a Groq rate limit — while GEMINI_API_KEY sat configured and
              idle. `_call_llm` was fixed that day to fall through on a
              failure instead of merely selecting. The CALLER was not.
  2026-09-07  the same line, the same shape: `HTTP Error 401` from an
              expired Groq key, three backfill attempts dead in under two
              seconds each. Three slots the showrunner had correctly emptied
              could not be re-authored and the day shipped 3 of 6.

The backfill is the LAST unattended chance to fill a slot a gate emptied. It
is the one place that must never hang on a single provider.

Runs standalone:  python3 tests/test_no_single_provider_dependency.py
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Production code that runs with nobody watching. A pinned backend here is a
# single point of failure for a whole day's output.
UNATTENDED = (
    "scripts/run_trending_daily.py",
    "scripts/story_forge.py",
    "scripts/post_stories.py",
    "scripts/run_explainer_daily.py",
    "scripts/ingest_authored.py",
    "shared/authoring_brief.py",
    "third_capture/author.py",
    "data_learning/mascot_director.py",
)


def _pinned_backends(path: Path):
    """Every `backend="..."` keyword passed to a call in this file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "backend" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                out.append((path.name, node.lineno, kw.value.value))
    return out


class NoUnattendedPathPinsOneProvider(unittest.TestCase):
    def test_no_pinned_backend_in_production(self):
        pinned = []
        for rel in UNATTENDED:
            p = _REPO / rel
            if p.exists():
                pinned += _pinned_backends(p)
        self.assertEqual(
            pinned, [],
            "an unattended path names ONE model provider, so that provider "
            "being down is a lost day: " + str(pinned))

    def test_the_backfill_specifically_is_unpinned(self):
        """Named on its own because it is the last chance to fill a slot the
        showrunner emptied — and because this is the exact line that broke
        twice."""
        src = (_REPO / "scripts" / "run_trending_daily.py").read_text(
            encoding="utf-8")
        self.assertNotIn('backend="groq"', src)
        self.assertNotIn("backend='groq'", src)

    def test_the_chain_still_falls_through_on_failure(self):
        """The other half of the fix, which must not regress: an unnamed
        backend tries the next one when a call RAISES, not merely when a key
        is missing."""
        from shared import script_generator as sg
        import inspect
        src = inspect.getsource(sg._call_llm)
        self.assertIn("except Exception", src)
        self.assertIn("trying the next backend", src)

    def test_an_explicit_backend_is_still_exact(self):
        """Falling through on an EXPLICIT request would be a silent
        substitution — worse than the failure, because nobody would know
        which model wrote the words."""
        from shared import script_generator as sg
        import inspect
        src = inspect.getsource(sg._call_llm)
        self.assertIn("if backend is not None:", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
