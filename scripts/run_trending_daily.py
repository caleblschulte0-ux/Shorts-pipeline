#!/usr/bin/env python3
"""Daily trending-shorts auto-poster.

Reads today's v8 package JSONs from state/trending_packages/YYYYMMDD/,
renders each as a stacked explainer short via make_explainer_stacked.py,
and uploads to YouTube at the scheduled publish time.

Called by: .github/workflows/trending_daily.yml at 12:00 UTC daily.
Packages written by: Claude + scripts/rank_topics.py (human review step).

v8 Package JSON schema
----------------------
  version     int     8
  slug        str     kebab-case-id
  title       str     YouTube title ≤80 chars
  tags        [str]
  script      str     60-80 word narration (TTS input)
  shots       [Shot]  5-7 B-roll segments
    phrase    str     verbatim substring of script (Whisper trigger)
    image_url str?    Wikipedia/Commons still — shows IMAGE_SHOT_SECS then stock
    query     str     Pexels/Pixabay search fallback
  punches     [Punch] 4-7 text pop-ons
    phrase    str     verbatim substring of script (Whisper trigger)
    text      str     display text ($ triggers ka-ching SFX; RIP/DEAD/CRASH shock)
    color     str     hex color (red #ff3030 / green #50ff80 / orange #ffe24a / white)
    flash_bg  str?    optional full-frame background flash (hex)
    size      int?    font size, default 160
    duration  float?  seconds visible, default 2.5
  music_vibe  str     dark | cinematic | hiphop
  gameplay    str     minecraft | subway | random

Usage:
    python3 scripts/run_trending_daily.py [--date 20260530] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

STATE_DIR = REPO / "state"
PACKAGES_DIR = STATE_DIR / "trending_packages"
LOG_PATH = STATE_DIR / "posted_log.json"

IMAGE_SHOT_SECS = 1.8  # Wikipedia image duration before stock video fills the rest
DEFAULT_PUBLISH_HOURS_UTC = [13, 15, 17, 19, 21, 23]

URL_RE = re.compile(r"\[upload\] youtube: (https://\S+)")


# ---------- package loading ----------

def load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"posted": []}


def save_log(log: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n")


def load_package(path: Path) -> dict:
    pkg = json.loads(path.read_text())
    v = pkg.get("version")
    if v != 8:
        raise ValueError(f"Expected v8 package, got version={v} in {path}")
    return pkg


def validate_package(pkg: dict) -> list[str]:
    """Return list of validation errors (empty = OK)."""
    errors: list[str] = []
    script = pkg.get("script", "")
    for shot in pkg.get("shots", []):
        phrase = shot.get("phrase", "")
        if phrase not in script:
            errors.append(f"shot.phrase not in script: {phrase!r}")
        if not shot.get("query"):
            errors.append(f"shot missing query field: {phrase!r}")
    for punch in pkg.get("punches", []):
        phrase = punch.get("phrase", "")
        if phrase not in script:
            errors.append(f"punch.phrase not in script: {phrase!r}")
    return errors


# ---------- rendering ----------

def download_image(url: str, dest: Path) -> Path | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrendingShorts/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "webp" in content_type:
            ext = "webp"
        out = dest.with_suffix(f".{ext}")
        out.write_bytes(data)
        return out
    except Exception as e:
        print(f"  WARN: image download failed {url}: {e}", file=sys.stderr)
        return None


def render_package(pkg: dict, out_path: Path, dry_run: bool = False) -> bool:
    from make_explainer_stacked import Shot, Punch, build_video

    script = pkg["script"]
    gameplay = pkg.get("gameplay", "minecraft")
    workdir = Path(tempfile.mkdtemp(prefix="trending_"))

    try:
        shots: list[Shot] = []
        for i, s in enumerate(pkg["shots"]):
            clip_path = None
            if s.get("image_url") and not dry_run:
                img_dest = workdir / f"img_{i:02d}"
                clip_path = download_image(s["image_url"], img_dest)
            shots.append(Shot(
                phrase=s["phrase"],
                clip=clip_path,
                pexels_query=s["query"],
                fallback_extend=IMAGE_SHOT_SECS if clip_path else 0.0,
            ))

        punches: list[Punch] = []
        for p in pkg["punches"]:
            punches.append(Punch(
                phrase=p["phrase"],
                text=p["text"],
                color=p.get("color", "#ffffff"),
                size=p.get("size", 160),
                duration=p.get("duration", 2.5),
                flash_bg=p.get("flash_bg", ""),
            ))

        if dry_run:
            print(f"  [dry-run] {pkg['slug']} — {len(shots)} shots, {len(punches)} punches")
            return True

        build_video(script, shots, punches, gameplay, out_path)
        return True

    except Exception as e:
        print(f"ERROR rendering {pkg.get('slug', '?')}: {e}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def upload_package(pkg: dict, video: Path, publish_at: str | None) -> str | None:
    from uploaders import upload_to
    title = pkg.get("title", pkg["slug"])
    tags = pkg.get("tags", [])
    try:
        upload_to(
            ["youtube"], video,
            title=title, description=pkg.get("script", ""), tags=tags,
            publish_at=publish_at,
        )
    except Exception as e:
        print(f"  upload error: {e}", file=sys.stderr)
        return None
    return None  # URL parsed from stdout by caller if needed


# ---------- scheduling ----------

def schedule_slots(now: datetime, n: int) -> list[str]:
    from datetime import timedelta
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = now + timedelta(minutes=5)
    picks: list[datetime] = []
    for day in range(3):
        for hour in DEFAULT_PUBLISH_HOURS_UTC:
            t = base + timedelta(days=day, hours=hour)
            if t > cutoff:
                picks.append(t)
            if len(picks) >= n:
                break
        if len(picks) >= n:
            break
    return [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in picks[:n]]


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y%m%d"),
                    help="Package date YYYYMMDD (default: today UTC)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", help="Where to write rendered MP4s (default: output/)")
    ap.add_argument("--no-upload", action="store_true", help="render only, no YouTube upload")
    args = ap.parse_args()

    pkg_dir = PACKAGES_DIR / args.date
    if not pkg_dir.exists():
        print(f"No packages for {args.date} — create JSONs in {pkg_dir}/", file=sys.stderr)
        return 1

    pkg_files = sorted(pkg_dir.glob("*.json"))
    if not pkg_files:
        print(f"No .json files in {pkg_dir}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else REPO / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    schedule = schedule_slots(now, len(pkg_files))
    log = load_log()

    print(f"Rendering {len(pkg_files)} packages for {args.date}")
    results: list[dict] = []

    for pkg_file, publish_at in zip(pkg_files, schedule):
        pkg = load_package(pkg_file)
        slug = pkg["slug"]
        print(f"\n--- {slug} -> {publish_at} ---")

        errs = validate_package(pkg)
        if errs:
            print(f"  VALIDATION ERRORS:", file=sys.stderr)
            for e in errs:
                print(f"    {e}", file=sys.stderr)

        out_path = out_dir / f"{args.date}_{slug}.mp4"
        t0 = time.time()
        ok = render_package(pkg, out_path, dry_run=args.dry_run)
        elapsed = round(time.time() - t0, 1)

        video_url = None
        if ok and not args.dry_run and not args.no_upload and out_path.exists():
            upload_package(pkg, out_path, publish_at)

        result = {"slug": slug, "ok": ok, "elapsed": elapsed, "video_url": video_url,
                  "publish_at": publish_at}
        results.append(result)

        if ok and not args.dry_run:
            log["posted"].append({
                "slug": slug,
                "date": args.date,
                "posted_at": now.isoformat(),
                "publish_at": publish_at,
                "video_url": video_url,
            })
            save_log(log)

    success = sum(1 for r in results if r["ok"])
    print(f"\nDone: {success}/{len(results)} succeeded")
    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
