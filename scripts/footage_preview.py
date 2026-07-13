#!/usr/bin/env python3
"""FOOTAGE-PRIMARY PREVIEW assembler (CURIOSITY_BRAIN §7.5 v9 — the hybrid).

Builds a documentary-length preview entirely from real NASA footage using the
panel-certified grammar (data_learning/footage_hybrid.py):
  real footage only  ·  full-frame with a matched push  ·  dissolve every seam.

A beat is one of:
  {"nasa_id": "...", "seconds": 6, "push": 1.06, "direction": "in"}   # pinned
  {"query":   "...", "seconds": 6, "push": 1.06, "direction": "in"}   # searched
Optional per beat: "at" (0..1 position of the cut inside the cleanest window),
"ss" (explicit start, overrides the clean-window scan).

It downloads each source once, cuts a full-frame matched-move beat from a
black-free window, deletes the (large) source, dissolve-joins the beats, and
writes a blind-judge package next to the output so the panel can gate it.

    python3 scripts/footage_preview.py beats.json out.mp4 [--work DIR] [--xfade 0.7]

`beats.json` is either a list of beats or {"beats": [...], "xfade": 0.7}.
Nothing here publishes; the blind panel (scripts/visual_judge.py) is the gate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import footage_hybrid as fh   # noqa: E402


def _resolve_source(beat: dict, work: Path, idx: int) -> Path | None:
    """Download the beat's source once (pinned nasa_id, or the top real-footage
    search hit). Returns the local path, or None if nothing real was found."""
    dest = work / f"src_{idx:02d}.mp4"
    if dest.exists():
        return dest
    nasa_id = beat.get("nasa_id")
    if not nasa_id:
        hits = fh.search_footage(str(beat.get("query", "")), limit=6)
        if not hits:
            print(f"[preview] beat {idx}: no real footage for "
                  f"{beat.get('query')!r} — skipped", file=sys.stderr)
            return None
        nasa_id = hits[0]["nasa_id"]
        print(f"[preview] beat {idx}: {beat.get('query')!r} -> {nasa_id}")
    try:
        fh.download_video(str(nasa_id), dest)
    except Exception as e:  # noqa: BLE001
        print(f"[preview] beat {idx}: download failed ({e}) — skipped",
              file=sys.stderr)
        return None
    return dest


def build(beats: list[dict], out: Path, work: Path,
          xfade: float = 0.7) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for i, beat in enumerate(beats):
        src = _resolve_source(beat, work, i)
        if src is None:
            continue
        secs = float(beat.get("seconds", 6.0))
        if beat.get("ss") is not None:
            ss = float(beat["ss"])
        else:
            wins = [w for w in fh.clean_windows(src, min_len=secs + 0.3)
                    if w[1] - w[0] >= secs]
            if wins:
                w0, w1 = wins[0]
                at = float(beat.get("at", 0.5))
                ss = max(w0, min(w0 + (w1 - w0 - secs) * at, w1 - secs))
            else:
                ss = 3.0
                print(f"[preview] beat {i}: no clean window >= {secs}s, "
                      f"using ss=3.0 (may hit a slate)", file=sys.stderr)
        clip = work / f"beat_{i:02d}.mp4"
        fh.full_frame_beat(src, ss, secs, clip,
                           push=float(beat.get("push", 1.06)),
                           direction=beat.get("direction", "in"))
        clips.append(clip)
        print(f"[preview] beat {i}: cut {secs:.1f}s @ {ss:.1f}s -> {clip.name}")
        # free the large source immediately (disk allowance is fixed)
        try:
            src.unlink()
        except OSError:
            pass
    if not clips:
        raise RuntimeError("no beats produced — every source failed")
    fh.dissolve_join(clips, out, xfade=xfade)
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)], capture_output=True, text=True
    ).stdout.strip()
    print(f"[preview] assembled {len(clips)} beats -> {out}  ({dur}s)")
    # blind-judge package alongside the output
    pkg = out.with_suffix("")
    pkg = pkg.with_name(pkg.name + "_pkg")
    try:
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "visual_judge.py"),
             str(out), "--out", str(pkg), "--grid", "6x3"], check=True)
        print(f"[preview] blind-judge package -> {pkg}")
    except Exception as e:  # noqa: BLE001
        print(f"[preview] judge package failed ({e})", file=sys.stderr)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("beats", type=Path, help="beats.json")
    ap.add_argument("out", type=Path)
    ap.add_argument("--work", type=Path, default=None)
    ap.add_argument("--xfade", type=float, default=0.7)
    args = ap.parse_args(argv)
    spec = json.loads(args.beats.read_text())
    beats = spec["beats"] if isinstance(spec, dict) else spec
    xfade = spec.get("xfade", args.xfade) if isinstance(spec, dict) \
        else args.xfade
    work = args.work or args.out.with_suffix("").with_name(
        args.out.stem + "_work")
    build(beats, args.out, work, xfade=xfade)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
