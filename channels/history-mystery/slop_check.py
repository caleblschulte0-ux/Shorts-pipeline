#!/usr/bin/env python3
"""No-AI-Slop gate for History & Mystery scripts.

Lints a v8 package JSON (or a raw .txt script) against the OPERATING_MANUAL §4
banned-phrase list and the §6 specificity requirement. Additive and standalone —
it imports nothing from the base pipeline and changes no renderer code.

Usage:
    python3 channels/history-mystery/slop_check.py path/to/package.json [more...]
    python3 channels/history-mystery/slop_check.py path/to/script.txt

Exit code 0 = all clean. Non-zero = at least one script was rejected.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# §4 — algorithm/credibility-suppressing AI-slop tells. Matched case-insensitively
# as substrings (the curly and straight apostrophes both covered).
BANNED_PHRASES = [
    "imagine ",
    "imagine,",
    "what if i told you",
    "you won't believe",
    "you wont believe",
    "in a world where",
    "little did they know",
    "buckle up",
    "let that sink in",
    "prepare to be",
    "mind-blowing",
    "mind blowing",
    "absolutely insane",
    "you've never heard",
    "youve never heard",
    "the internet is losing",
    "will shock you",
    "this changes everything",
]

# §6 — specificity. A credible "sounds fake but true" script must name real
# anchors. We require, at minimum: a date/year, a proper noun, and a concrete
# number. These are heuristics — the human fact-check (templates/) is the real
# gate; this is the cheap backstop.
YEAR_RE = re.compile(r"\b(1\d{3}|20\d{2})\b")  # 1000–2099
# any standalone number of 1+ digits (years already covered; this catches "3 days",
# "25,000 birds", "5:45 a.m.")
NUMBER_RE = re.compile(r"\b\d[\d,]*\b")
# a capitalized word that is NOT at the start of a sentence => likely a proper noun
PROPER_NOUN_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)

# Common sentence-initial words that get capitalized but aren't proper nouns —
# don't count these toward "named entities".
STOPWORD_CAPS = {
    "The", "This", "That", "They", "Then", "There", "These", "Those",
    "And", "But", "For", "Some", "One", "Two", "When", "What", "Why",
    "How", "His", "Her", "Their", "It", "In", "On", "At", "By", "As",
    "Records", "Historians", "Today", "Back", "First", "Now",
}


def _extract_script(path: Path) -> str:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("script", "")).strip()
    return path.read_text(encoding="utf-8").strip()


def check_script(script: str) -> list[str]:
    """Return a list of rejection reasons. Empty list == passes."""
    problems: list[str] = []
    low = script.lower()

    for phrase in BANNED_PHRASES:
        if phrase in low:
            problems.append(f"banned slop phrase: {phrase.strip()!r}")

    # repeated-fact heuristic: the same 6+-word window appearing twice
    words = re.findall(r"\w+", low)
    seen: set[str] = set()
    for i in range(len(words) - 5):
        window = " ".join(words[i : i + 6])
        if window in seen:
            problems.append(f"repeated phrase (filler/duplication): {window!r}")
            break
        seen.add(window)

    if not YEAR_RE.search(script):
        problems.append("missing specificity: no year/date (e.g. '1518')")

    if not NUMBER_RE.search(script):
        problems.append("missing specificity: no concrete number")

    proper_nouns = [
        w for w in PROPER_NOUN_RE.findall(script) if w not in STOPWORD_CAPS
    ]
    if len(set(proper_nouns)) < 1:
        problems.append(
            "missing specificity: no proper noun (place/person/artifact)"
        )

    return problems


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]]
    if not paths:
        print(__doc__)
        return 2

    any_failed = False
    for path in paths:
        if not path.exists():
            print(f"✗ {path}: file not found")
            any_failed = True
            continue
        script = _extract_script(path)
        if not script:
            print(f"✗ {path}: no 'script' content found")
            any_failed = True
            continue
        problems = check_script(script)
        if problems:
            any_failed = True
            print(f"✗ {path}: REJECTED")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"✓ {path}: clean")

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
