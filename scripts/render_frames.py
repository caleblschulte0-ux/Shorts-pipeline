#!/usr/bin/env python3
"""The BRAIN's eyes: render the FINAL build frame of every segment for the given
story slugs as PNGs (no video, no TTS, no upload) so Claude can LOOK at each
depiction and judge it before anything ships.

    python scripts/render_frames.py bite-force-champions --out preview/frames

Prints [OK]/[FAIL] per segment with the depiction kind and the PNG path, and
exits non-zero if any segment failed to render — so the brain can iterate:
fix the scene -> re-render -> re-look, until every frame passes review.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
# The brain already decided the depictions; render exactly what's in the config.
os.environ.setdefault("VIZ_INVENT", "0")

from data_learning import story as story_mod    # noqa: E402

CFG = REPO / "data_learning" / "niche.config.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--out", default="preview/frames")
    a = ap.parse_args()
    cfg = json.load(open(CFG, encoding="utf-8"))
    byslug = {s["slug"]: s for s in cfg["stories"]}
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    wd = Path(tempfile.mkdtemp(prefix="brainframes_"))
    rc = 0
    for slug in a.slugs:
        st = byslug.get(slug)
        if not st:
            print(f"[MISS] unknown slug: {slug}")
            rc = 1
            continue
        # story.build() runs the REAL production path — director + renderers —
        # and leaves each segment's build-frame pattern on `chart_path`. We just
        # harvest the FINAL frame of each segment (the finished look).
        try:
            story = story_mod.build(st, cfg, wd, REPO)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {slug}: story build raised {type(e).__name__}: {e}")
            rc = 1
            continue
        for i, seg in enumerate(story.segments):
            pat = getattr(seg, "chart_path", None)
            files: list[str] = []
            if pat and "%" in pat:
                files = sorted(glob.glob(re.sub(r"%\d*d", "*", pat)))
            elif pat and Path(pat).exists():
                files = [pat]
            dest = outdir / f"{slug}_seg{i}.png"
            if files:
                shutil.copyfile(files[-1], dest)
                print(f"[OK] {slug} seg{i} kind={seg.kind} -> {dest}")
            else:
                print(f"[FAIL] {slug} seg{i}: kind={seg.kind} produced no frame")
                rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
