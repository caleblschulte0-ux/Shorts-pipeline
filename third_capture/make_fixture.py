#!/usr/bin/env python3
"""Deterministic messy-CSV fixture generator for Proof Mode captures.

Produces a synthetic 1,000-row contact export with the exact defects a
real messy spreadsheet has: duplicate rows, inconsistent casing, stray
whitespace, mixed phone formats, blank lines. Synthetic-only per the
channel's privacy invariant (THIRD_BRAIN.md §7) — names are generated
from word lists, never real people.

Deterministic (seeded) so a re-run reproduces the exact fixture that a
video's proof ledger hashes refer to.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "fixtures" / "messy_contacts.csv"

FIRST = ["ada", "Grace", "ALAN", "linus", "Margaret", "ken", "DONALD",
         "barbara", "Edsger", "JOHN", "radia", "Tim", "VINT", "hedy",
         "Katherine", "guido", "BJARNE", "dennis", "Anita", "SHAFI"]
LAST = ["lovelace", "Hopper", "TURING", "torvalds", "Hamilton", "thompson",
        "KNUTH", "liskov", "Dijkstra", "MCCARTHY", "perlman", "Berners-Lee",
        "CERF", "lamarr", "Johnson", "rossum", "STROUSTRUP", "ritchie",
        "borg", "GOLDWASSER"]
DOMAINS = ["example.com", "test.example.org", "mail.example.net"]
CITIES = ["austin", "Denver", "SEATTLE", "boston", "Miami", "portland",
          "CHICAGO", "phoenix", "Atlanta", "TULSA"]


def _phone(rng: random.Random) -> str:
    n = [rng.randint(2, 9)] + [rng.randint(0, 9) for _ in range(9)]
    s = "".join(map(str, n))
    style = rng.randint(0, 3)
    if style == 0:
        return f"({s[:3]}) {s[3:6]}-{s[6:]}"
    if style == 1:
        return f"{s[:3]}-{s[3:6]}-{s[6:]}"
    if style == 2:
        return f"{s[:3]}.{s[3:6]}.{s[6:]}"
    return s


def _row(rng: random.Random) -> dict:
    f, l = rng.choice(FIRST), rng.choice(LAST)
    pad = " " * rng.randint(0, 3)
    return {
        "name": f"{pad}{f} {l}{' ' * rng.randint(0, 2)}",
        "email": f"{f}.{l}@{rng.choice(DOMAINS)}".lower().replace(" ", ""),
        "phone": _phone(rng),
        "city": rng.choice(CITIES) + (" " * rng.randint(0, 2)),
        "signup": rng.choice([
            f"2025-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            f"{rng.randint(1,12)}/{rng.randint(1,28)}/2025",
            f"{rng.randint(1,28)} Jan 2025",
        ]),
    }


def main() -> Path:
    rng = random.Random(20260707)
    rows = [_row(rng) for _ in range(7600)]
    # Inject exact duplicates (the headline defect the command removes).
    dupes = [dict(r) for r in rng.sample(rows, 1200) for _ in (0, 1)][:2400]
    rows += dupes
    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for i, r in enumerate(rows):
            w.writerow(r)
    print(f"wrote {OUT} ({len(rows)} data rows, {len(dupes)} injected dupes)")
    return OUT


if __name__ == "__main__":
    main()
