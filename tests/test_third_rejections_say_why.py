"""Every Third rejection records WHY, in the durable record.

2026-09-08..22: 110 rejected-* entries in the posted log, and 44 of them
carried no reason at all — three `_blocklist` sites (preflight, the
director's "clip incomplete", QA) wrote `qa_rejected: true` and nothing
else. A third of the channel's losses could not be attributed to any judge,
so nobody could say whether supply, framing, or the director was the drain.

This reads every `_blocklist(...)` call from the source, so a fourth site
cannot grow back silent.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "scripts" / "run_third.py").read_text()


def _blocklist_calls():
    return [n for n in ast.walk(ast.parse(SRC))
            if isinstance(n, ast.Call)
            and getattr(n.func, "id", None) == "_blocklist"]


class EveryRejectionSaysWhy(unittest.TestCase):
    def test_there_are_blocklist_sites_to_check(self):
        self.assertGreaterEqual(len(_blocklist_calls()), 5)

    def test_every_site_records_who_rejected_and_why(self):
        for call in _blocklist_calls():
            entry = call.args[2] if len(call.args) >= 3 else None
            with self.subTest(line=call.lineno):
                self.assertIsInstance(
                    entry, ast.Dict,
                    "entry must be a literal so its keys can be checked")
                keys = {k.value for k in entry.keys
                        if isinstance(k, ast.Constant)}
                self.assertIn("rejected_by", keys,
                              f"line {call.lineno}: a rejection with no judge")
                self.assertIn("rejected_why", keys,
                              f"line {call.lineno}: a rejection with no reason")


if __name__ == "__main__":
    unittest.main()
