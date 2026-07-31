#!/usr/bin/env python3
"""Grade every pro story's OPENING LINE offline, before anything renders.

The gap this closes: the hook gate is gate #1 in the DIRECTOR's order of
importance, and it is the one gate the pipeline states outright it cannot
repair — "needs a re-authored opening line (cannot auto-fix a line)". A film
whose first line trips NO_GAP_NO_STAKES is therefore unpassable no matter how
good the pictures are.

That verdict arrived after a ~2 HOUR render, three times running. It is a pure
text check: it costs milliseconds and needs no media, no TTS and no ffmpeg.
Running it at authoring time turns a two-hour dead end into an instant one.

This does not write hooks — nothing here invents an opening line, and a weak
hook is still the author's problem to solve. It only refuses to let a story
reach the render queue carrying a defect the renderer is known to be unable to
fix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from hook_director import grade_line  # noqa: E402

MIN_SCORE = 2          # below this the opening is not doing a hook's job
STORIES = REPO / "data_learning" / "pro_stories"


def check(path: Path) -> tuple[bool, str]:
    try:
        beats = (json.loads(path.read_text()).get("beats") or [])
    except Exception as e:  # noqa: BLE001 — a malformed story is its own error
        return False, f"unreadable ({str(e)[:60]})"
    if not beats:
        return False, "no beats"
    line = str(beats[0].get("narration", "")).strip()
    if not line:
        return False, "opening beat has no narration"
    g = grade_line(line)
    ok = not g["gates"] and g["score"] >= MIN_SCORE
    why = (f"score {g['score']}/5 hits={g['hits'] or '-'}"
           + (f" GATES={g['gates']}" if g["gates"] else ""))
    return ok, why


def main(argv) -> int:
    only = {a for a in argv if not a.startswith("-")}
    paths = sorted(p for p in STORIES.glob("*.beats.json")
                   if (only and p.name.split(".")[0] in only)
                   # the deliberate negative controls exist to FAIL the gates —
                   # holding them to the bar would invert what they are for
                   or (not only and not p.name.split(".")[0].endswith("-weak")))
    if not paths:
        print("no stories to check")
        return 0
    bad = []
    for p in paths:
        slug = p.name.split(".")[0]
        ok, why = check(p)
        print(f"{'ok  ' if ok else 'WEAK'} {slug:<28} {why}")
        if not ok:
            bad.append(slug)
    if bad:
        print(f"\n{len(bad)} story/stories open on a line the renderer cannot "
              f"repair: {', '.join(bad)}")
        print("Fix the FIRST narration line — give it a real gap (a question or "
              "an open loop), stakes, a specific number, or address the viewer "
              "directly. See data_learning/HOOK_DIRECTOR.md.")
        return 1
    print(f"\nall {len(paths)} opening line(s) clear the hook gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
