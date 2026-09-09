"""No runbook may state the Phase B backstop as a wall-clock UTC time.

Doctor finding a2d4a0aea829: four operator-facing docs still published
retired schedules — README said 06:15 UTC, FALLBACKS, exchange/README and
CLAUDE_ROUTINE_INSTRUCTIONS said 12:45 UTC — while the live workflow runs
paired 13:30/14:30 UTC crons gated in America/Chicago to land at 08:30
Central in both DST halves. FALLBACKS contradicted itself twelve sections
apart.

Any UTC statement of this time is wrong for half the year BY CONSTRUCTION:
the finalizer's task is local-time and shifts an hour at DST while a cron
does not. That is the entire reason the paired-cron arrangement exists, and
a doc naming one UTC hour re-describes the bug the arrangement fixed.

So the rule is not "keep the number in sync" — a number four docs must
remember to update is a number that drifts. The rule is that the backstop is
described in CENTRAL, everywhere, and the UTC hours live only in
exchange_phase_b.yml with `FINALIZER_HOUR_CENTRAL` deciding between them.

Historical prose explaining WHY a retired UTC time was wrong is fine and is
deliberately not matched here — CLAUDE.md and docs/EXCHANGE_PIPELINE.md both
carry that account, and losing it is how the mistake gets made again.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A LIVE claim about when the backstop runs, stated in UTC.
_LIVE_UTC_BACKSTOP = re.compile(
    r"\d{1,2}:\d{2}\s*UTC\s+backstop"
    r"|backstop\s+cron\s+at\s+\d{1,2}:\d{2}\s*UTC"
    r"|backstop[^.\n]{0,20}\bat\s+\d{1,2}:\d{2}\s*UTC",
    re.I)

DOCS = ["README.md", "CLAUDE.md", "CLAUDE_ROUTINE_INSTRUCTIONS.md",
        "exchange/README.md"]


def _doc_paths() -> list[Path]:
    out = [ROOT / d for d in DOCS]
    out += sorted((ROOT / "docs").glob("*.md"))
    return [p for p in out if p.exists()]


class TheBackstopIsDescribedInCentral(unittest.TestCase):
    def test_there_are_docs_to_check(self):
        self.assertGreaterEqual(len(_doc_paths()), 8)

    def test_no_doc_states_the_backstop_as_a_utc_wall_clock_time(self):
        offenders = []
        for path in _doc_paths():
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if _LIVE_UTC_BACKSTOP.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "the Phase B backstop is 08:30 CENTRAL, decided in code by "
            "FINALIZER_HOUR_CENTRAL between two UTC crons — a doc naming one "
            "UTC hour is wrong for half the year:\n" + "\n".join(offenders))

    def test_the_retired_hours_appear_only_as_history(self):
        """06:15 and 12:45 may be discussed; they may not be presented as the
        schedule. A mention has to sit next to a word that dates it."""
        past = re.compile(r"was|were|used to|once|old|retired|stale|until|"
                          r"earlier|former|previous|stated|said|sat", re.I)
        # Only where the line is TALKING about the schedule. 06:15 is also a
        # perfectly ordinary clock time in a checkpoint timeline, and a test
        # that flags those gets edited into uselessness the first time it
        # cries wolf.
        about = re.compile(r"backstop|cron|schedul|phase b", re.I)
        offenders = []
        for path in _doc_paths():
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if (re.search(r"\b(?:06:15|12:45)\b", line)
                        and about.search(line) and not past.search(line)):
                    offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_docs_agree_with_the_code_they_describe(self):
        """If the hour ever legitimately moves, this test moves with it —
        it reads the source, not a remembered number."""
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        src = (ROOT / "scripts" / "exchange_phase_b.py").read_text()
        m = re.search(r"FINALIZER_HOUR_CENTRAL\s*=\s*(\d+)", src)
        self.assertIsNotNone(m, "FINALIZER_HOUR_CENTRAL is gone — docs stale")
        # The backstop is one clear hour past the finalizer's start hour.
        hour = int(m.group(1))
        wall = f"{hour + 1:02d}:30"
        wf = (ROOT / ".github" / "workflows" / "exchange_phase_b.yml").read_text()
        self.assertIn("30 13", wf)
        self.assertIn("30 14", wf)
        stated = [p.relative_to(ROOT) for p in _doc_paths()
                  if "backstop" in p.read_text().lower()
                  and wall not in p.read_text()]
        self.assertEqual(
            [str(s) for s in stated], [],
            f"these docs describe the backstop without ever naming {wall} "
            "Central, the time it actually runs")


if __name__ == "__main__":
    unittest.main()
