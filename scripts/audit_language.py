#!/usr/bin/env python3
"""Hear what language each video speaks, with the posting run's own check
(shared/sports_scope.not_english): local Whisper, no API.

    python scripts/audit_language.py posted/*.mp4

Prints one line per video: words heard, Whisper's English probability and
the verdict, so the floor can be checked on real posts (operator,
2026-11-11: "no more videos that aren't English").
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import sports_scope  # noqa: E402
from third_capture import clip_edit  # noqa: E402


def main(paths: list[str]) -> int:
    bad = 0
    for p in map(Path, paths):
        words = clip_edit.transcribe_words(p)
        prob = (sports_scope.english_probability(p, words)
                if len(words) >= sports_scope.MIN_WORDS else None)
        why = sports_scope.not_english(p, words)
        bad += bool(why)
        print(f"{len(words):4d} words  en_p={'-' if prob is None else f'{prob:.2f}':>5}  "
              f"{'REFUSE' if why else 'ok':6}  {p.name}", flush=True)
    print(f"{bad} of {len(paths)} would be refused as not English")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
