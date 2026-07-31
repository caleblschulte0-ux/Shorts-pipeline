#!/usr/bin/env python3
"""A beat cannot be denied footage just for being LONG.

THE DEFECT (diagnosed 2026-07-31, network-verified, currently UNFIXED).

`media.motion_first(query, seconds, ...)` requires a single clip containing one
clean, moving window of the FULL beat length. Stock clips are typically 3-6s, so
any beat asking for ~6s is unservable however good the candidates are:

    motion_first('child running outdoors sunlight', 6.0) -> None
        'a little boy running in a backyard': no clean 6.0s window — skipping
        'kid running in the park':            no clean 6.0s window — skipping
    motion_first('child running outdoors sunlight', 3.5) -> pexels motion=32.4
    motion_first('child running outdoors sunlight', 2.5) -> pexels motion=27.5

Same query, same candidates, same second — only the requested duration differs.

This is why shared-air's PAYOFF (beat 18) reverted to a designed card in EVERY
run, which then produced the SYNC mismatch the director keeps reporting
(narration says "person", the fallback visual is a sun). It was misread as a
Pexels outage for five renders; the provider is fine — `pexels WORKING — 32
candidates` in the same CI job that then found "no dynamic clip".

THE FIX (not yet implemented — do not close this without doing it):
  motion_first should fall back to the LONGEST clean window a candidate can
  actually offer, down to a floor (~2.5s), and RETURN that length so the caller
  knows. `_depict_source` then emits the footage shot for the window the clip
  really has and lets the existing development phase carry the remainder, rather
  than discarding a good clip and downgrading the whole beat to a card.

This test documents the contract that fix must satisfy. It is skipped without a
key/network, so it never turns CI red for being offline.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

Q = "child running outdoors sunlight"
LONG, SHORT = 6.0, 3.5


def main():
    if not os.environ.get("PEXELS_API_KEY"):
        print("skip: no PEXELS_API_KEY (this check needs the live provider)")
        return
    from data_learning import media
    work = Path(tempfile.mkdtemp())
    quiet = lambda m: None  # noqa: E731

    short = media.motion_first(Q, SHORT, work, perspective="human-scale",
                               log=quiet)
    if not short:
        print(f"skip: no clip for {Q!r} even at {SHORT}s — provider or network "
              "is down, which is not what this check is about")
        return
    print(f"ok  a {SHORT}s window resolves: {short['source']} "
          f"motion={short['motion']}")

    long_ = media.motion_first(Q, LONG, work, perspective="human-scale",
                               log=quiet)
    if long_:
        print(f"ok  a {LONG}s window ALSO resolves ({long_['source']}) — the "
              "length ceiling is gone; this test can become a hard assert")
        return

    # The defect, still present. Fail loudly rather than pass quietly: a beat
    # that a 3.5s window can serve must not be denied footage for asking 6s.
    raise SystemExit(
        f"FAIL: {Q!r} resolves at {SHORT}s but NOT at {LONG}s — motion_first "
        "still requires one clip to cover the whole beat, so long beats get no "
        "footage and downgrade to a card. See this file's docstring for the fix."
    )


if __name__ == "__main__":
    main()
