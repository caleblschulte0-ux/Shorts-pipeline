"""Every model reply is read by shared.jsonreply.one_object. The greedy
`re.search(r"\\{.*\\}")` + `json.loads(m.group(0))` raised "Extra data" on a
reply with two objects and killed 1-3 Baller Bro posts a run
(2026-11-11..13); sixteen call sites across every channel did the same."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from shared.jsonreply import one_object

REPO = Path(__file__).resolve().parents[1]
SKIP = {".git", ".claude", "tests", "node_modules", ".venv", "cache"}


class OneObject(unittest.TestCase):
    def test_two_objects_is_the_last(self):
        self.assertEqual(one_object('{"a": 1}\n\n{"a": 2}'), {"a": 2})

    def test_prose_and_braces_in_strings(self):
        self.assertEqual(one_object('Here: {"x": "{y}"} -- done {oops'),
                         {"x": "{y}"})

    def test_nested_is_one_object(self):
        self.assertEqual(one_object('{"a": {"b": 1}}'), {"a": {"b": 1}})

    def test_nothing_raises_value_error(self):
        with self.assertRaises(ValueError):
            one_object("I could not answer")


class NoGreedyParseGrowsBack(unittest.TestCase):
    def test_no_module_parses_the_greedy_match(self):
        bad = []
        for p in REPO.rglob("*.py"):
            if SKIP & set(p.relative_to(REPO).parts):
                continue
            src = p.read_text(errors="ignore")
            if re.search(r"json\.loads\(\s*m\.group\(0\)\s*\)", src):
                bad.append(str(p.relative_to(REPO)))
        self.assertEqual(bad, [], "use shared.jsonreply.one_object")
