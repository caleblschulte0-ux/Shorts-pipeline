"""Visual + runtime benchmark for the parallax engine (Ticket E2).

Renders `maybe_parallax` vs the `kenburns` baseline over a demo set that
covers the categories where depth-parallax is known to succeed or fail:
portrait, animal, landscape, city, illustration/diagram, space, image with
text, overlapping foreground objects. Writes clips + a machine-readable
report to cache/bench/, then prints the review checklist.

Promotion rule (from docs/ENGINE_REGISTRY.md): parallax stays
`experimental` until a reviewer (human or vision-QA) scores the clips and
the pass rate justifies an automatic suitability gate. If it only works on
a minority of categories, it needs a gate, not broad availability.

Usage:
    python -m engines.benchmarks.parallax_bench            # full set
    python -m engines.benchmarks.parallax_bench --only portrait,space
Assets download at bench time (Wikimedia + repo assets) — none committed.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from engines import CACHE_DIR, ROOT
from engines.parallax import maybe_parallax
from engines.still_motion import maybe_kenburns

BENCH_DIR = CACHE_DIR / "bench"
ASSET_DIR = BENCH_DIR / "assets"

# Category -> source. Wikimedia Special:FilePath redirects to the original;
# all listed files are public domain or CC (bench-time download, not
# committed, not published — license only matters if a clip ships).
_WM = "https://commons.wikimedia.org/wiki/Special:FilePath/"
DEMO_SET: dict[str, str] = {
    "portrait": _WM + "Abraham%20Lincoln%20O-77%20matte%20collodion%20print.jpg",
    "animal": _WM + "Lion%20waiting%20in%20Namibia.jpg",
    "landscape": _WM + "Moraine%20Lake%2017092005.jpg",
    "city": _WM + "NYC%20Downtown%20Manhattan%20Skyline%20seen%20from%20Paulus%20Hook%202019-12-20%20IMG%207347%20FRD%20(cropped).jpg",
    "illustration": str(ROOT / "assets" / "mascot" / "anchor" / "laugh.png"),
    "space": _WM + "NGC%204414%20(NASA-med).jpg",
    "text": _WM + "United%20States%20Declaration%20of%20Independence.jpg",
    "overlap_fg": _WM + "Red%20Apple.jpg",
}

CHECKLIST = [
    "torn or haloed edges around foreground objects",
    "stretched / smeared background near depth boundaries",
    "rubber-sheet wobble on flat regions (esp. illustration + text)",
    "text remaining readable and rigid",
    "overall: does motion read as camera depth, or as distortion?",
]


def _fetch(category: str, src: str) -> Path | None:
    if not src.startswith("http"):
        p = Path(src)
        return p if p.is_file() else None
    dest = ASSET_DIR / f"{category}{Path(src.split('%20')[-1]).suffix or '.jpg'}"
    if dest.is_file():
        return dest
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(src, headers={"User-Agent": "engines-bench/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
        return dest
    except Exception as e:  # noqa: BLE001
        print(f"  [{category}] fetch failed: {e}")
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated categories")
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--size", default="1080x1350",
                    help="WxH (default 1080x1350 — the top-half aspect)")
    args = ap.parse_args(argv)
    w, h = (int(v) for v in args.size.split("x"))
    cats = (args.only.split(",") if args.only else list(DEMO_SET))

    results = {}
    for cat in cats:
        src = DEMO_SET.get(cat)
        if src is None:
            print(f"  unknown category {cat!r}")
            continue
        img = _fetch(cat, src)
        if img is None:
            results[cat] = {"error": "asset fetch failed"}
            continue
        print(f"[{cat}] {img.name}")
        entry: dict = {"image": str(img)}
        t0 = time.time()
        kb = maybe_kenburns(img, BENCH_DIR / f"{cat}_kenburns.mp4",
                            args.duration, size=(w, h))
        entry["kenburns"] = {"out": str(kb), "seconds": round(time.time() - t0, 2)} if kb else None
        t0 = time.time()
        px = maybe_parallax(img, BENCH_DIR / f"{cat}_parallax.mp4",
                            args.duration, size=(w, h))
        entry["parallax"] = {"out": str(px), "seconds": round(time.time() - t0, 2)} if px else None
        results[cat] = entry

    report = BENCH_DIR / "parallax_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(
        {"size": args.size, "duration": args.duration, "results": results,
         "checklist": CHECKLIST}, indent=2) + "\n")
    print(f"\nreport: {report}\nclips:  {BENCH_DIR}/")
    print("\nReview checklist (per parallax clip, vs its kenburns baseline):")
    for item in CHECKLIST:
        print(f"  [ ] {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
