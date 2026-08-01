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


def test_probe_budget_is_shared_across_providers():
    """A provider must not be buried by another provider's verbosity.

    `max_probe` is 3 because probing means downloading and scanning a clip. With
    a flat relevance sort, Pixabay's 32 rows pushed Pexels' 6 past the budget, so
    the only provider that could serve the beat was never looked at. That is why
    'child running outdoors sunlight' resolved locally (Pexels-only key) and
    reverted to a card in CI (both keys live). Same query, same code — decided by
    how many rows each provider happened to return.
    """
    from data_learning.media import _interleave_sources
    cands = ([{"source": "pixabay", "n": i} for i in range(32)]
             + [{"source": "pexels", "n": i} for i in range(6)])
    top = _interleave_sources(cands)[:3]
    assert any(c["source"] == "pexels" for c in top), top
    # order WITHIN a provider is preserved — never promote a worse match
    order = [c["n"] for c in _interleave_sources(cands) if c["source"] == "pexels"]
    assert order == sorted(order), order
    print("ok  the probe budget reaches every provider (pexels was rank 33)")


def test_a_short_source_still_fills_the_whole_beat():
    """A shot is exactly as long as its beat, or the rest of the video desyncs.

    `full_frame_beat` cuts with `-t dur`. When the source runs out before then
    ffmpeg writes a SHORT clip and exits 0 — no error anywhere — so the concat
    comes up short and every clip after it slides off its narration. Stock clips
    are 3-6s and beats reach 10s, so this is the ordinary case. It only became
    reachable once `_footage_shot` learned to step its window down instead of
    raising, which is exactly when a silent version of it would have been read
    as "the video is just bad".
    """
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        print("skip: no ffmpeg")
        return
    from data_learning import footage_hybrid as fh
    work = Path(tempfile.mkdtemp())
    src, out = work / "src.mp4", work / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "testsrc=size=640x360:rate=25:duration=3",
                    str(src)], check=True)
    fh.full_frame_beat(src, 1.0, 8.0, out)
    got = fh._duration(out)
    assert abs(got - 8.0) < 0.35, f"beat asked 8.0s, shot is {got:.2f}s"
    print(f"ok  a 3s source fills an 8s beat ({got:.2f}s) instead of truncating")


if __name__ == "__main__":
    test_probe_budget_is_shared_across_providers()
    test_a_short_source_still_fills_the_whole_beat()
    main()
