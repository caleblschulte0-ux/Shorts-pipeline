#!/usr/bin/env python3
"""Compile several explainer stories into ONE long-form video and upload it.

The hybrid play (research: Shorts + long-form channels grow ~41% faster):
Shorts drive discovery, this long-form builds watch-time + ad revenue. It
reuses the studio renders (vertical), adds a branded intro card, and writes
YouTube chapter timestamps into the description so each breakdown is navigable.

Auth/upload reuse the channel-routed uploader + the channel guard, exactly
like post_stories.py.

Usage:
    python scripts/build_longform.py --dry-run                 # build, no upload
    python scripts/build_longform.py --title "Your Money, Explained"
    python scripts/build_longform.py --slugs debt-trap grocery-squeeze
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CONFIG = REPO / "data_learning" / "niche.config.json"
OUT = REPO / "output"
STATE = REPO / "state"
EXPLAINER_LOG = STATE / "explainer_posted_log.json"
LONGFORM_LOG = STATE / "longform_log.json"
W, H, FPS = 1080, 1920, 30


def _dur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _intro_card(title: str, path: Path, seconds: float = 3.0) -> Path:
    """A short branded title card (dark gradient + title), silent audio so it
    concatenates cleanly with the narrated stories."""
    safe = title.replace("'", "’").replace(":", "\\:")
    vf = (f"drawtext=text='{safe}':fontcolor=white:fontsize=50:"
          f"x=(w-text_w)/2:y=(h-text_h)/2-80:line_spacing=14,"
          f"drawtext=text='Data\\, explained.':fontcolor=0x4FD1C5:fontsize=40:"
          f"x=(w-text_w)/2:y=(h-text_h)/2+40")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i",
         f"gradients=s={W}x{H}:c0=0x0a0e20:c1=0x102b40:duration={seconds}:rate={FPS}",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-t", f"{seconds}", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-shortest", str(path)],
        check=True)
    return path


def _ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def _posted_slugs() -> list[str]:
    """Most-recent published explainer stories (newest last in the log)."""
    if not EXPLAINER_LOG.exists():
        return []
    posted = json.loads(EXPLAINER_LOG.read_text()).get("posted", {})
    items = [(slug, e) for slug, e in posted.items()
             if e and e.get("url") and not e.get("skipped")]
    items.sort(key=lambda kv: kv[1].get("at", ""))
    return [slug for slug, _ in items]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*",
                    help="stories to include (default: up to 6 most-recent "
                         "published explainer stories)")
    ap.add_argument("--title", default=None,
                    help="long-form title (default auto from the month)")
    ap.add_argument("--channel", default="explainer")
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true",
                    help="render + stitch but do not upload")
    ap.add_argument("--publish-at", default=None,
                    help="RFC3339 timestamp to schedule (else public now)")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    slugs = args.slugs or _posted_slugs()
    slugs = [s for s in slugs if s in stories][:args.max]
    if not slugs:
        print("no stories to compile", file=sys.stderr)
        return 2

    month = datetime.now(timezone.utc).strftime("%B %Y")
    title = (args.title or f"Your Money, Explained — {month}")[:100]
    OUT.mkdir(parents=True, exist_ok=True)

    from data_learning import studio_render
    intro = _intro_card(title, OUT / "lf_intro.mp4")
    parts = [intro]
    for slug in slugs:
        mp4 = OUT / f"lf_{slug}.mp4"
        print(f"[longform] rendering {slug}", flush=True)
        studio_render.render(slug, mp4)
        parts.append(mp4)

    # Chapters: cumulative start time of each part.
    chapters, t = [], 0.0
    chapters.append((_ts(0.0), "Intro"))
    t += _dur(intro)
    for slug in slugs:
        chapters.append((_ts(t), stories[slug].get("title", slug)))
        t += _dur(OUT / f"lf_{slug}.mp4")

    listf = OUT / "lf_concat.txt"
    listf.write_text("\n".join(f"file '{p.resolve()}'" for p in parts) + "\n")
    final = OUT / "longform.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(listf), "-c", "copy",
                    "-movflags", "+faststart", str(final)], check=True)
    print(f"[longform] {final} ({_dur(final):.0f}s, {len(slugs)} stories)")

    desc = ("Every data breakdown from this batch, in one place.\n\nChapters:\n"
            + "\n".join(f"{ts} {name}" for ts, name in chapters)
            + "\n\n#data #economy #explained #charts #money")
    if args.dry_run:
        print("DRY RUN — not uploading.\n" + desc)
        return 0

    from uploaders import YouTubeUploader
    up = YouTubeUploader(channel=args.channel)
    res = up.upload(file_path=final, title=title, description=desc[:5000],
                    tags=["data", "economy", "explained", "money", "charts"],
                    publish_at=args.publish_at)
    url = getattr(res, "url", None) or str(res)
    print(f"[longform] uploaded -> {url}")
    LONGFORM_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = (json.loads(LONGFORM_LOG.read_text())
           if LONGFORM_LOG.exists() else {"posted": []})
    log["posted"].append({"url": url, "title": title, "slugs": slugs,
                          "at": datetime.now(timezone.utc).isoformat()})
    LONGFORM_LOG.write_text(json.dumps(log, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
