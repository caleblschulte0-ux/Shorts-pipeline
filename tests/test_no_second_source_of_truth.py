"""CI drift guard — fail when a second source of channel policy grows back.

The registry only works if nothing else declares the same facts. Prose and
constants rot silently: the 2026-07-31 graph-led ruling landed in ONE of five
places that stated the mix, and for weeks the reserve bank banked a retired
format while every test passed.

So this scans the files where an operational rule would plausibly be written
down again and fails on:

  * a slate declaration outside `config/channel_registry.json`
  * a resurrected `TARGET_MIX` / `SLATE_MIX` style constant
  * a retired format named as something to author
  * a queue threshold typed as a literal

It is deliberately a TEXT scan. A type system cannot stop someone writing
"write exactly six packages" in a prompt, and a prompt is where the last one
hid.

    python -m unittest tests.test_no_second_source_of_truth -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import channel_registry as reg           # noqa: E402

#: Where an operational rule would plausibly be restated. Not the whole repo:
#: a scan that shouts about every file is a scan people learn to ignore.
WATCHED = [
    "CLAUDE_ROUTINE_INSTRUCTIONS.md",
    "CLAUDE.md",
    "exchange/README.md",
    "docs/EXCHANGE_PIPELINE.md",
    "docs/FALLBACKS.md",
    "shared/authoring_brief.py",
    "shared/package_buffer.py",
    "shared/exchange_bundle.py",
    "scripts/exchange_phase_a.py",
    "scripts/exchange_phase_b.py",
    "scripts/ingest_authored.py",
    "scripts/package_reserve.py",
    "scripts/run_trending_daily.py",
    ".github/workflows/daily.yml",
    ".github/workflows/exchange_phase_a.yml",
    ".github/workflows/exchange_phase_b.yml",
]

#: A line is allowed to mention an old ruling if it is explaining HISTORY or
#: explicitly disclaiming itself. These markers say "not normative".
_EXEMPT = re.compile(
    r"used to|no longer|previously|was written|went stale|historical|"
    r"do not edit by hand|generated from|EXPLANATORY|explanatory|"
    r"non-normative|illustration|example|for reference|the registry wins|"
    r"registry decides|NOT FROM THIS FILE|stale|drift|regression|"
    r"if your prompt|out of date|# noqa: drift", re.I)


def _lines(rel: str):
    p = ROOT / rel
    if not p.exists():
        return []
    return list(enumerate(p.read_text().splitlines(), start=1))


class TestNoSecondSourceOfTruth(unittest.TestCase):

    def _offences(self, pattern, *, why: str, files=None) -> list[str]:
        rx = re.compile(pattern, re.I)
        out = []
        for rel in files or WATCHED:
            for n, line in _lines(rel):
                if not rx.search(line):
                    continue
                if _EXEMPT.search(line):
                    continue
                out.append(f"{rel}:{n}: {line.strip()[:110]}  <- {why}")
        return out

    def test_no_slate_declaration_outside_the_registry(self):
        """`2 + 2 + 2`, `4+2`, `2/2/2` — a hand-written mix.

        Scoped to lines that are TALKING about a slate: "Features 1 + 3" and
        "Tickets 3/4/5" are not rulings, and a scan that flags them is a scan
        people learn to skip."""
        bad = self._offences(
            r"(?=.*\b(mix|slate|packages?|format|author|write)\b)"
            r"\b\d\s*[+/]\s*\d(\s*[+/]\s*\d)?\b",
            why="a slate written by hand; put it in "
                "config/channel_registry.json and read it with "
                "shared.channel_registry")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_no_resurrected_mix_constant(self):
        bad = self._offences(
            r"^\s*(TARGET_MIX|SLATE_MIX|FORMATS|LOW_WATER|"
            r"CURIOSITY_MIN_QUEUE|DEFAULT_SLATE)\s*=",
            why="a module-level constant duplicating registry policy")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_no_hardcoded_package_count(self):
        """'EXACTLY 6 files', 'six packages', 'write 6' — the shape that hid
        the last ruling inside a workflow prompt."""
        bad = self._offences(
            r"(exactly|write|author|ship)\s+(six|seven|eight|four|five|"
            r"\d{1,2})\s+(files|packages|videos|shorts)",
            why="a package count written by hand; interpolate "
                "`python -m shared.channel_registry --mix <channel>` instead")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_no_retired_format_is_told_to_be_authored(self):
        """A retired format may be MENTIONED (history, a renderer that still
        exists) but never instructed."""
        retired = [f for cid in reg.channel_ids()
                   for f in reg.retired_formats(cid)]
        self.assertTrue(retired, "no retired formats — widen this test when "
                                 "the first one appears")
        rx = re.compile(r"(write|author|produce|create|generate)\b[^.]{0,60}\b("
                        + "|".join(re.escape(f) for f in retired) + r")\b",
                        re.I)
        bad = []
        for rel in WATCHED:
            for n, line in _lines(rel):
                if rx.search(line) and not _EXEMPT.search(line):
                    bad.append(f"{rel}:{n}: {line.strip()[:110]}")
        self.assertEqual(bad, [], "a RETIRED format is being instructed:\n"
                         + "\n".join(bad))

    def test_the_registry_is_the_only_json_declaring_a_mix(self):
        """No other config file may carry a `target_mix` / `slate` key."""
        bad = []
        for p in sorted(ROOT.glob("config/*.json")) + \
                sorted(ROOT.glob("data_learning/*.config.json")):
            if p.name == "channel_registry.json":
                continue
            text = p.read_text()
            for key in ("target_mix", "slate_mix", "format_mix",
                        "target_count"):
                if f'"{key}"' in text:
                    bad.append(f"{p.relative_to(ROOT)} declares {key!r}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_production_code_imports_the_registry(self):
        """The consumers that decide a slate must resolve it, not carry it."""
        for rel in ("shared/authoring_brief.py", "shared/package_buffer.py",
                    "scripts/exchange_phase_a.py",
                    "scripts/exchange_phase_b.py"):
            text = (ROOT / rel).read_text()
            self.assertIn("channel_registry", text,
                          f"{rel} decides slate policy without reading the "
                          f"registry")

    def test_the_render_workflow_is_not_a_second_brain(self):
        wf = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
        self.assertNotIn("Brain — author today's packages", wf)
        self.assertNotIn("claude -p", wf)
        self.assertIn("--require-manifest", wf)
        self.assertIn("shared import channel_registry", wf,
                      "daily.yml must still resolve its render count from "
                      "the registry")

    def test_the_test_suite_is_actually_discoverable(self):
        """`python -m unittest discover -s tests` must WORK.

        It did not, on main, until 2026-08-01. `scripts/` holds 37 test_*.py
        files of its own and one of them — `scripts/test_exchange.py` —
        shadows `tests/test_exchange.py`. Every test module that did
        `sys.path.insert(0, ROOT/"scripts")` put the shadow ahead of the real
        one, and discovery died with an ImportError as soon as anything had
        imported or byte-compiled the scripts copy.

        The failure was invisible because nothing ran the suite in CI. Both
        halves are fixed; this pins the import-order half."""
        import subprocess
        out = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_exchange.py", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=180)
        self.assertNotIn("incorrectly imported", out.stderr,
                         "scripts/ is shadowing tests/ on sys.path again — "
                         "test modules must APPEND scripts/, never insert it "
                         "at position 0")
        self.assertEqual(out.returncode, 0, out.stderr[-800:])

    def test_no_test_module_puts_scripts_ahead_of_tests(self):
        # Match a real statement at the start of a line, not this file's own
        # description of the pattern it is banning.
        rx = re.compile(r'^sys\.path\.insert\(\s*0\s*,[^)]*scripts', re.M)
        offenders = [p.name for p in sorted(Path(ROOT / "tests").glob("*.py"))
                     if rx.search(p.read_text())]
        self.assertEqual(offenders, [],
                         "use sys.path.append for scripts/ — inserting it at "
                         "0 lets scripts/test_*.py shadow tests/test_*.py")

    def test_ci_actually_runs_the_suite(self):
        """The suite gated nothing until 2026-08-01: `automerge` needed only
        the sanity job, so a PR breaking every test merged itself."""
        wf = (ROOT / ".github" / "workflows" / "auto-merge.yml").read_text()
        self.assertIn("unittest discover -s tests", wf,
                      "no CI job runs the test suite")
        import yaml
        needs = yaml.safe_load(wf)["jobs"]["automerge"]["needs"]
        needs = [needs] if isinstance(needs, str) else needs
        self.assertIn("tests", needs,
                      "automerge does not wait for the test suite")

    def test_every_watched_file_exists(self):
        """A drift scan over files that have been renamed away is a scan that
        silently passes."""
        missing = [rel for rel in WATCHED if not (ROOT / rel).exists()]
        self.assertEqual(missing, [], f"update WATCHED: {missing}")


if __name__ == "__main__":
    unittest.main()
