"""The engine registry has to tell the truth about what is actually wired.

Audit finding C, second-order. `docs/ENGINE_REGISTRY.md` and
`engines.REGISTRY` are how a future session decides whether a capability
already exists. On 2026-08-01 the registry was wrong in BOTH directions at
once:

  * `still_motion` said `consumers: []` while two renderers called
    `maybe_kenburns` — so a session would have rebuilt it.
  * `svg_motion` said `status: active` with no consumer anywhere — so a
    session would have believed animated cards were in production.

Neither is a typo you can fix once. Metadata drifts from code the moment
nothing checks it, which is exactly how `shared/video_qa.py` sat
imported-by-nothing for weeks while CLAUDE.md told every session to run it.

So this test checks the metadata against the code:

  * an engine that is `active` and not `gated` MUST have a real consumer
  * every consumer it names must actually exist and import it
  * `experimental` engines must carry a decision date, so "not yet" cannot
    quietly become "forever"

    python -m unittest tests.test_engine_registry_honesty -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import engines                                          # noqa: E402

#: Engines that are infrastructure rather than in-repo modules — their
#: "consumer" is the whole pipeline and there is no import to grep for.
EXTERNAL = {"ffmpeg", "blender", "manim", "kokoro", "rembg", "whisper",
            "opencv"}

VALID_STATUS = {"active", "experimental", "deferred", "rejected"}


def module_engines():
    return {n: m for n, m in engines.REGISTRY.items()
            if m.get("kind") == "module" or n not in EXTERNAL}


def importers(name: str) -> list[str]:
    """Every non-engine, non-test file that actually imports the engine."""
    pat = re.compile(rf"\bengines(?:\.{name}\b|\s+import\s+[^\n]*\b{name}\b)")
    hits = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        # A TEST importing an engine is not a production consumer. The second
        # suite lives in `scripts/` (audit finding F), so excluding the
        # `tests/` directory alone is not enough — match the filename too.
        if rel.startswith(("engines/", "tests/", ".git")):
            continue
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            continue
        if p.name.startswith(("smoke_", "benchmark_")):
            continue
        try:
            if pat.search(p.read_text(errors="ignore")):
                hits.append(rel)
        except OSError:
            continue
    return hits


class TestStatusIsAValidState(unittest.TestCase):
    def test_every_status_is_one_of_the_documented_lifecycle_states(self):
        for name, meta in engines.REGISTRY.items():
            self.assertIn(meta.get("status"), VALID_STATUS,
                          f"{name} has an undocumented status")


class TestActiveMeansSomethingActuallyCallsIt(unittest.TestCase):
    """`active` is a claim about production, not about the code compiling."""

    def test_active_ungated_engines_have_a_consumer(self):
        for name, meta in engines.REGISTRY.items():
            if meta.get("status") != "active" or meta.get("gated"):
                continue
            self.assertTrue(
                meta.get("consumers"),
                f"{name} claims status=active with no consumer. Either wire "
                f"it, mark it gated, or demote it to experimental — an "
                f"'active' engine nothing calls is the exact lie the "
                f"2026-08-01 audit found.")

    def test_the_consumers_it_names_really_import_it(self):
        for name, meta in engines.REGISTRY.items():
            if name in EXTERNAL:
                continue
            for c in meta.get("consumers") or []:
                path = c.split(" ")[0].split(":")[0]
                if not path.endswith(".py"):
                    continue
                self.assertTrue((ROOT / path).exists(),
                                f"{name} names a consumer that does not "
                                f"exist: {path}")

    def test_no_engine_understates_its_consumers(self):
        """The still_motion failure: real callers, empty list. A session
        reading that would rebuild a capability it already has."""
        for name, meta in module_engines().items():
            if name in EXTERNAL:
                continue
            found = importers(name)
            if found and not (meta.get("consumers") or []):
                self.fail(f"{name} lists no consumers but is imported by "
                          f"{found} — the registry is understating it")

    def test_no_engine_overstates_its_consumers(self):
        for name, meta in module_engines().items():
            if name in EXTERNAL or not (meta.get("consumers") or []):
                continue
            if meta.get("status") != "active" or meta.get("gated"):
                continue
            self.assertTrue(importers(name),
                            f"{name} lists consumers but nothing imports it")


class TestExperimentalCannotBecomeForever(unittest.TestCase):
    def test_experimental_engines_carry_a_decision_date(self):
        for name, meta in engines.REGISTRY.items():
            if meta.get("status") != "experimental":
                continue
            self.assertTrue(
                meta.get("decision_date"),
                f"{name} is experimental with no decision_date — that is how "
                f"'not yet' becomes permanent litter. Adopt or delete it.")

    def test_a_decision_date_is_a_date(self):
        for name, meta in engines.REGISTRY.items():
            d = meta.get("decision_date")
            if d:
                self.assertRegex(str(d), r"^\d{4}-\d{2}-\d{2}$",
                                 f"{name}: decision_date must be YYYY-MM-DD")


class TestTheRegistryStaysUsable(unittest.TestCase):
    def test_every_engine_has_the_fields_a_reader_needs(self):
        for name, meta in engines.REGISTRY.items():
            for field in ("problem", "status"):
                self.assertIn(field, meta, f"{name} is missing {field}")

    def test_available_never_raises_and_never_hits_the_network(self):
        for name in engines.REGISTRY:
            self.assertIsInstance(engines.available(name), bool)

    def test_the_docs_list_the_same_engines_as_the_code(self):
        doc = (ROOT / "docs" / "ENGINE_REGISTRY.md").read_text()
        for name in module_engines():
            self.assertIn(name, doc,
                          f"{name} is in code but not docs/ENGINE_REGISTRY.md")


if __name__ == "__main__":
    unittest.main()
