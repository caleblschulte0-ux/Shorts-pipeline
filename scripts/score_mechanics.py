#!/usr/bin/env python3
"""Score every mechanic in the library on whether it actually MOVES.

Operator ruling, 2026-09-21: *"those per video animations, like that laser
one and shit like that, like, those were sick, those were cool. People like
those."* — bespoke mechanic first, kit machine second, chart last.

`charts.FALLBACK` has said `mechanic -> scene -> diorama -> bubbles` for
months, so the ORDER was never the problem. SUPPLY was. Measured on
2026-09-21 against four common data shapes (rising, falling, a two-way duel,
a five-way ranking):

    library 60 mechanics:  30 move on at least one shape,  30 move on NONE
    of the 34 the brain had STARRED as its best work:      16 move on none

and `_mechanic_examples` teaches STARRED FIRST. So the two examples handed to
the brain every time it invents were, half the time, mechanics that the
motion gate refuses — it studied frozen work, wrote frozen work, got refused,
and the beat fell through to a kit scene or a chart. A teaching loop pointed
at its own failures.

This is the measurement that breaks the loop. It is the SAME check the
render path runs (`viz_scene.mechanic_dry_ok`, which ends in
`mechanic_motion_ok` using the SHOWRUNNER'S OWN frame detector), so a
mechanic scored `moves: true` here is one the renderer will accept, and the
library stops recommending what the pipeline will throw away.

NOTHING IS DELETED. A frozen mechanic keeps its row and its code; it simply
stops being offered as an example. It can be repaired and rescored.

    python scripts/score_mechanics.py            # report, write nothing
    python scripts/score_mechanics.py --write    # persist the `moves` flag
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

LIB = REPO / "data_learning" / "viz_mechanics.json"

#: A mechanic is written for ONE story's data, so judging all of them against
#: a single synthetic series is unfair — a two-way duel legitimately does not
#: animate on a four-point trend. It counts as ALIVE if it moves on ANY of
#: these, and what moves on none is static by construction, which is what
#: `VIZ_BRAIN.md` already forbids: "some element must traverse roughly a
#: screen dimension during the beat, or cycle".
SHAPES = {
    "rising": [("2015", 12.0), ("2018", 19.0), ("2021", 26.0), ("2024", 41.0)],
    "falling": [("2015", 41.0), ("2018", 26.0), ("2021", 19.0), ("2024", 12.0)],
    "duel": [("A", 63.0), ("B", 31.0)],
    "rank": [("One", 92.0), ("Two", 61.0), ("Three", 44.0),
             ("Four", 23.0), ("Five", 8.0)],
}


def _insight(topic: str, pairs):
    from data_learning.insights import Insight
    from data_learning.sources.base import DataPoint, Source
    return Insight(
        kind="trend", topic=topic or "a topic", main_insight="m",
        items=[DataPoint(label=a, value=b) for a, b in pairs],
        source=Source(name="scorer", publisher="scorer",
                      url="https://example.invalid", access_date="1970-01-01"),
        unit="count", highlight_label=pairs[-1][0])


def moves_on(entry: dict) -> list:
    """The shapes this mechanic visibly animates on. [] means static."""
    from data_learning import viz_scene as vs
    spec = {"mechanic": entry.get("mechanic", ""),
            "concept": entry.get("concept", ""),
            "code": entry.get("code", "")}
    good = []
    for name, pairs in SHAPES.items():
        try:
            if vs.mechanic_dry_ok(spec, _insight(entry.get("topic", ""), pairs)):
                good.append(name)
        except Exception:  # noqa: BLE001 — a crashing mechanic is not alive
            continue
    return good


def score(lib: list) -> list:
    out = []
    for entry in lib:
        good = moves_on(entry)
        row = dict(entry)
        row["moves"] = bool(good)
        row["moves_on"] = good
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="persist the `moves` flag back into the library")
    ap.add_argument("--lib", default=str(LIB))
    args = ap.parse_args()

    path = Path(args.lib)
    lib = json.loads(path.read_text())
    if not isinstance(lib, list):
        print(f"{path} is not a list of mechanics", file=sys.stderr)
        return 2

    import matplotlib
    matplotlib.use("Agg")
    scored = score(lib)

    alive = [m for m in scored if m["moves"]]
    dead = [m for m in scored if not m["moves"]]
    starred_dead = [m for m in dead if m.get("starred")]
    print(f"library {len(scored)}: {len(alive)} move, {len(dead)} static")
    print(f"  starred-but-static (these were teaching the brain to freeze): "
          f"{len(starred_dead)}")
    for m in dead:
        print(f"    static  {m.get('mechanic')}")

    if args.write:
        path.write_text(json.dumps(scored, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote `moves` for {len(scored)} mechanics -> {path}")
    else:
        print("\n(report only — pass --write to persist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
