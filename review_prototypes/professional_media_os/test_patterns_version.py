"""Version-ordering tests for the isolated pattern library."""

from __future__ import annotations

from dataclasses import replace
import unittest

from .contracts import ContractError, Maturity, PatternRecord
from .patterns import PatternLibrary


class PatternVersionTests(unittest.TestCase):
    def _record(self, version: str) -> PatternRecord:
        return PatternRecord(
            pattern_id="pattern-version-001",
            name="Version fixture",
            applies_to=("authority-conflict",),
            excludes=(),
            structure=("open", "resolve"),
            strengths={"hook": "directional"},
            failure_modes=("fixture only",),
            evidence_ids=("evidence-one", "evidence-two"),
            maturity=Maturity.EXPERIMENTAL,
            confidence=0.75,
            version=version,
            review_after="2026-10-01T00:00:00Z",
        )

    def test_semantic_version_ordering_does_not_use_lexical_order(self) -> None:
        library = PatternLibrary((self._record("1.9.0"), self._record("1.10.0")))
        self.assertEqual(library.latest("pattern-version-001").version, "1.10.0")

    def test_invalid_pattern_version_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            PatternLibrary((self._record("version-two"),))


if __name__ == "__main__":
    unittest.main()
