"""Two things the story arm got wrong after it started working (2026-10-01).

1. EVERY STORY TITLE WAS NAMELESS. All four stories through 2026-10-01
   shipped titles like "Her Stalker Bought a New PC Just to Keep Harassing
   Her" — no streamer. This channel is ~89% YouTube search; a title without
   the name people type cannot be found. That story held 98.7% of the people
   who found it, and 5 people found it. Clip titles have always been anchored
   to the streamer by a rule inside `author._postprocess`; it is now one
   function, `author.anchor_streamer`, and the story title goes through it.

2. A SLOT RETRY ERASED THE STORY'S RECORD. The story runs on attempt 1 only
   (#442); `process()` cleared every verdict on each attempt, so when the
   story's fallback clip failed and retried, the whole deliberation vanished.
   On 2026-10-01 the arm ran 24 minutes, tried six candidates, rendered one,
   and state/third_qa_stats.json held none of it.
"""
from __future__ import annotations

import ast
import difflib
import importlib.util
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import author                         # noqa: E402


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _original_inline(title: str, streamer: str) -> str:
    """The block as it sat inside `_postprocess` before extraction, kept
    VERBATIM as the oracle (CLAUDE.md: consolidation is tested for
    equivalence against the originals)."""
    pretty = streamer.strip("_").title()
    fixed_words = []
    matched = False
    for word in title.split():
        if _norm(word) == _norm(streamer) or \
                difflib.SequenceMatcher(
                    None, _norm(word), _norm(streamer)).ratio() > 0.8:
            fixed_words.append(pretty)
            matched = True
        else:
            fixed_words.append(word)
    title = " ".join(fixed_words)
    if not matched:
        title = f"{pretty}: {title}"
    return title


class ExtractionChangedNothingForClips(unittest.TestCase):
    def test_equivalent_to_the_original_over_generated_titles(self):
        rng = random.Random(20261001)
        streamers = ["kaicenat", "caseoh_", "stableronaldo", "xqc",
                     "jasontheween", "buddha", "lacy", "jynxzi"]
        words = ["Snaps", "After", "Chat", "Gets", "Mad", "Kai", "Cenat",
                 "Stablernaldo", "Caseoh", "XQC", "Jason", "Lacy", "The",
                 "Wildest", "Moment", "Jynxzi", "Buddah", "$20K", "—"]
        for _ in range(2000):
            s = rng.choice(streamers)
            t = " ".join(rng.choice(words) for _ in range(rng.randint(1, 9)))
            with self.subTest(title=t, streamer=s):
                self.assertEqual(author.anchor_streamer(t, s),
                                 _original_inline(t, s))

    def test_postprocess_calls_the_shared_rule(self):
        src = (ROOT / "third_capture" / "author.py").read_text()
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_postprocess")
        self.assertIn("anchor_streamer(title, streamer)",
                      ast.get_source_segment(src, fn))


class StoryTitlesNameTheStreamer(unittest.TestCase):
    def test_a_nameless_story_title_gets_the_name(self):
        self.assertEqual(
            author.anchor_streamer(
                "Her Stalker Bought a New PC Just to Keep Harassing Her",
                "extraemily"),
            "Extraemily: Her Stalker Bought a New PC Just to Keep "
            "Harassing Her")

    def test_a_title_that_already_names_them_is_not_doubled(self):
        self.assertEqual(
            author.anchor_streamer("Jynxzi Finally Gets Back In", "jynxzi"),
            "Jynxzi Finally Gets Back In")

    def test_the_story_arm_uses_it(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_story_attempt")
        body = ast.get_source_segment(src, fn)
        self.assertIn("author.anchor_streamer(", body)
        self.assertIn('"authored_title": _st', body)


class ARetryKeepsTheStoryRecord(unittest.TestCase):
    """Driven through the real `process()` — an already-posted slug returns
    right after the judges are set up, which is exactly the code under test."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "run_third_retry", ROOT / "scripts" / "run_third.py")
        cls.rt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.rt)

    def _run(self, attempt):
        rt = self.rt
        rt._JUDGES.clear()
        rt._JUDGES["story_director"] = {"clusters": [{"outcome": "x"}]}
        rt._JUDGES["banger"] = {"score": 0.4}
        pkg = {"slug": "clip-x-3", "capture": {"kind": "twitch_clip"}}
        rt.process(pkg, None, dry_run=True, publish_at=None,
                   log={"posted": {"clip-x-3": {}}}, attempt=attempt)
        return dict(rt._JUDGES)

    def test_attempt_two_keeps_the_story_deliberation(self):
        j = self._run(2)
        self.assertIn("story_director", j)
        self.assertNotIn("banger", j, "the clip's own verdicts are per-attempt")

    def test_attempt_one_still_starts_clean(self):
        self.assertEqual(self._run(1), {})


if __name__ == "__main__":
    unittest.main()
