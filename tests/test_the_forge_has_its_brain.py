"""THE FORGE HAS ITS BRAIN — installed before it runs, with its token.

Story forge run 44873077455 (2026-11-21, the first to write since 09-07):
every text brain was down (Groq 429, Gemini 429/503) and the headless
Claude path never ran, because `story_forge.yml` installed the CLI AFTER
the forge step and never gave the forge CLAUDE_CODE_OAUTH_TOKEN. The one
story kept carried deterministic fallback words — "India Beats Everyone On
General pupils secondary education — By 5.1x" — which the editorial gate
then held. explainer.yml fixed the same ordering on 2026-09-07 and said so
in a comment; this workflow never did.

The same run printed "[brain] unavailable ('NoneType' object has no
attribute 'group')": a brain that ANSWERED in prose, read as a brain that
was down, because the JSON search's miss was never checked.

Held here:
  * in story_forge.yml the CLI install step precedes the forge step and
    the forge step's env carries CLAUDE_CODE_OAUTH_TOKEN;
  * an LLM answer with no JSON object returns None and says so.
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import story_forge as sf                   # noqa: E402

WF = REPO / ".github" / "workflows" / "story_forge.yml"


def _steps(text: str) -> list[tuple[str, str]]:
    """(name, body) for every `- name:` step, in order."""
    parts = re.split(r"\n\s*- name: ", "\n" + text)[1:]
    return [(p.split("\n", 1)[0].strip(), p) for p in parts]


class TheBrainIsInstalledBeforeTheForge(unittest.TestCase):
    def setUp(self):
        self.steps = _steps(WF.read_text())
        self.names = [n for n, _ in self.steps]

    def _index(self, needle: str) -> int:
        hits = [i for i, n in enumerate(self.names) if needle in n]
        self.assertEqual(len(hits), 1, f"{needle!r}: {hits} in {self.names}")
        return hits[0]

    def test_the_cli_is_installed_before_the_forge_step(self):
        install = self._index("Install Claude Code CLI")
        forge = self._index("Forge stories from live open data")
        self.assertLess(install, forge,
                        "the forge's brain must exist when the forge runs")

    def test_the_forge_step_carries_the_token(self):
        body = self.steps[self._index("Forge stories from live open data")][1]
        env = body.split("run:", 1)[0]
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}",
                      env, "the headless brain is the forge's first writer")

    def test_the_predraw_still_has_a_cli_to_draw_with(self):
        install = self._index("Install Claude Code CLI")
        draw = self._index("Draw the next new-look stories")
        self.assertLess(install, draw)


class AProseAnswerIsSaidSo(unittest.TestCase):
    DSS = [{"title": "Net migration", "unit": "people", "insight_type": "trend",
            "geography": "World",
            "points": [{"label": "2000", "value": 1.0},
                       {"label": "2020", "value": 2.0}]}]

    def _words(self, answer: str):
        out = io.StringIO()
        with mock.patch.object(sf, "_claude_words", return_value=None), \
                mock.patch("shared.script_generator._call_llm",
                           return_value=answer), \
                contextlib.redirect_stdout(out):
            got = sf._brain_words(self.DSS)
        return got, out.getvalue()

    def test_prose_returns_none_and_names_the_cause(self):
        got, log = self._words("I would title this 'Nobody Is Moving Anymore'.")
        self.assertIsNone(got)
        self.assertIn("no JSON object", log)
        self.assertNotIn("NoneType", log)

    def test_a_json_answer_is_still_taken(self):
        got, log = self._words('{"title": "Nobody Is Moving Anymore", '
                               '"hook": "Net migration doubled, and the map '
                               'did not notice."}')
        self.assertEqual(got["title"], "Nobody Is Moving Anymore")


if __name__ == "__main__":
    unittest.main()
