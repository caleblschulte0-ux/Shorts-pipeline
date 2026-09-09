"""A response that answers a DIFFERENT plan is refused WHOLE.

Doctor finding b9f879c22ed1. `contract_problems()` detects when
response.json declares a registry revision, source commit or production date
that differs from the bundle's frozen snapshot — and Phase B turned that into
refused MEDIA POINTERS only. ingest(), ingest_explainer(), ingest_curiosity()
and the punch-up then ran anyway, re-reading the same response.json with no
idea it had been rejected.

So a stale response could not supply a single image and could still promote
an entire authored slate against today. Media and words come out of the same
file; they are trusted or refused together.

    python -m unittest tests.test_contract_isolation -v
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import media_checkpoint as mc               # noqa: E402

PHASE_B = ROOT / "scripts" / "exchange_phase_b.py"


def _bundle(**over):
    c = {"registry_revision": 12, "registry_sha256": "abc123",
         "source_commit": "deadbeef", "production_date": "20260909"}
    c.update(over)
    return {"bundle_id": "b1", "contract": c, "requests": []}


def _response(**over):
    """A response that is VALID IN EVERY OTHER WAY — real authored packages,
    real explainer words. The whole point of the finding is that a mismatch
    must refuse content that would otherwise sail through."""
    c = {"registry_revision": 12, "registry_sha256": "abc123",
         "source_commit": "deadbeef", "production_date": "20260909"}
    c.update(over)
    return {
        "contract": c,
        "authored_packages": [{"slug": "a-real-package", "beats": [1, 2, 3]}],
        "explainer": [{"slug": "a-real-story", "narration": "words"}],
        "curiosity": [{"slug": "a-real-entry"}],
        "media": [],
    }


class TestTheMismatchIsDetected(unittest.TestCase):
    def test_a_matching_response_has_no_problems(self):
        self.assertEqual(mc.contract_problems(_response(), _bundle()), [])

    def test_a_stale_source_commit_is_a_problem(self):
        p = mc.contract_problems(_response(source_commit="cafe00"), _bundle())
        self.assertTrue(p)
        self.assertIn("source_commit", p[0])

    def test_yesterdays_production_date_is_a_problem(self):
        self.assertTrue(mc.contract_problems(
            _response(production_date="20260908"), _bundle()))

    def test_a_newer_registry_revision_is_a_problem(self):
        self.assertTrue(mc.contract_problems(
            _response(registry_revision=13), _bundle()))

    def test_silence_is_tolerated(self):
        """An older worker simply does not declare a contract. That is not
        evidence of a mismatch, so it must not be treated as one."""
        r = _response()
        r.pop("contract")
        self.assertEqual(mc.contract_problems(r, _bundle()), [])


class TestTheRefusalCoversTheWholeResponse(unittest.TestCase):
    """The regression itself, asserted against the source: every consumer of
    response.json must be behind the same admission decision."""

    def setUp(self):
        self.src = PHASE_B.read_text()
        tree = ast.parse(self.src)
        self.main = [n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "main"][0]

    def _guarded(self, needle: str) -> bool:
        """Is `needle` inside an `if` whose test mentions contract_refused?"""
        for node in ast.walk(self.main):
            if not isinstance(node, ast.If):
                continue
            test = ast.dump(node.test)
            if "contract_refused" not in test:
                continue
            body = "\n".join(
                ast.get_source_segment(self.src, st) or "" for st in node.body)
            if needle in body:
                return True
        return False

    def test_the_decision_is_made_once_for_the_whole_response(self):
        self.assertIn("contract_refused = list(", self.src)

    def test_authored_package_ingest_is_gated(self):
        self.assertTrue(self._guarded("ingest(args.date"))

    def test_explainer_ingest_is_gated(self):
        self.assertTrue(self._guarded("ingest_explainer("))

    def test_curiosity_ingest_is_gated(self):
        self.assertTrue(self._guarded("ingest_curiosity("))

    def test_the_punchup_is_gated(self):
        self.assertTrue(self._guarded("punchup_guard.check"))

    def test_media_is_still_refused_too(self):
        """The original half must not regress while fixing the rest."""
        self.assertIn("refused.setdefault(r[\"request_id\"]", self.src)

    def test_the_refusal_is_recorded_in_the_report(self):
        """Without this the report shows a day that simply had no ChatGPT
        content, which is a different thing entirely."""
        self.assertIn('"contract_refused": contract_refused', self.src)

    def test_the_gate_is_unconditional_so_it_cannot_be_skipped(self):
        """A NameError path would fail open — the worst possible outcome for
        an admission decision."""
        depth = {}

        def walk(node, d):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, ast.Assign):
                    for t in ch.targets:
                        if isinstance(t, ast.Name) and \
                                t.id == "contract_refused":
                            depth["d"] = d
                nd = d + 1 if isinstance(
                    ch, (ast.If, ast.Try, ast.For, ast.While,
                         ast.With)) else d
                walk(ch, nd)
        walk(self.main, 0)
        self.assertEqual(depth.get("d"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
