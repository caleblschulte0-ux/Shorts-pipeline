#!/usr/bin/env python3
"""Build ONE purpose-built 16:9 long-form video and publish it, gated.

WHAT CHANGED (2026-08-25, operator ruling: "I want long form videos to
start posting", purpose-built 16:9, fail-closed gate)
-----------------------------------------------------------------------
This script used to concatenate six already-rendered VERTICAL 1080x1920
Shorts with an intro card and `ffmpeg -c copy`, then upload the result. It
posted nine of those weekly between 2026-06-07 and 2026-08-02, and every
one landed as a `youtube.com/shorts/...` URL. That is a playlist in a
single file, not a watch-page video: the shape is wrong for the surface
long-form is supposed to win (watch time, mid-rolls, suggested), and its
quality is capped at exactly the quality of the Shorts it stapled
together.

Meanwhile `data_learning/longform_render.py` — 725 lines, written for the
curiosity channel — already renders a STORY as a 4-8 minute **1920x1080**
watch-page video with a title card, one documentary exhibit frame per
beat, Ken Burns pushes, calm narration, a ducked music bed, a closing
card, a **custom 1920x1080 thumbnail** and a **chapter list**. Nothing in
the long-form path imported it. That is the exact shape rule zero in
CLAUDE.md forbids: a capability built and left unwired while a worse
implementation shipped in its place.

So: this builds ONE story as a real 16:9 watch-page video, and it does not
publish until the SHOWRUNNER has watched it.

THE GATE IS FAIL-CLOSED, like every other publishing channel
-----------------------------------------------------------------------
Long-form had no showrunner, no QA, no judge of any kind — it uploaded
whatever ffmpeg produced. Turning publishing on without a gate would have
recreated the finding in docs/SYSTEM_AUDIT.md §B verbatim: trending
shipped 6/day ungated (best video 45 views) while explainer shipped 1/day
gated (best video 1,063). Volume through a lower bar is the one move this
repo refuses.

`shared.showrunner_gate.run(...)` is the same policy object the shorts
channels call — `decide()` is pure and fails CLOSED on a publish run: no
verdict, an infra error or a timeout HOLDS the video. `SHOWRUNNER=off` is
refused whenever this run would upload.

Usage:
    python scripts/build_longform.py --dry-run          # build + judge only
    python scripts/build_longform.py                    # build, judge, publish
    python scripts/build_longform.py --slug debt-trap
"""
from __future__ import annotations

import argparse
import json
import os
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

# The channel long-form posts to. It is the EXPLAINER channel's watch page —
# long-form is a second format on an existing channel, not a channel of its
# own, which is exactly why the 2026-08-05 ruling could not reach it through
# the registry and it kept its own cron. See docs note in longform.yml.
CHANNEL = "explainer"
EXPECTED_CHANNEL = "short_explainer67"


def _ts(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    return f"{m}:{s:02d}"


def _posted_slugs() -> list[str]:
    """Published explainer stories, NEWEST FIRST."""
    from shared.fsutil import load_state_json
    if not EXPLAINER_LOG.exists():
        return []
    posted = (load_state_json(EXPLAINER_LOG, default={}) or {}).get("posted", {})
    items = [(slug, e) for slug, e in (posted or {}).items()
             if isinstance(e, dict) and e.get("url") and not e.get("skipped")]
    items.sort(key=lambda kv: kv[1].get("at", ""), reverse=True)
    return [slug for slug, _ in items]


def _already_longformed() -> set[str]:
    """Slugs a long-form has already been built from — never twice."""
    from shared.fsutil import load_state_json
    log = load_state_json(LONGFORM_LOG, default={"posted": []}) or {}
    done: set[str] = set()
    for e in log.get("posted") or []:
        if not isinstance(e, dict):
            continue
        for s in e.get("slugs") or []:
            done.add(s)
        if e.get("slug"):
            done.add(e["slug"])
    return done


def pick_slug(cfg: dict, explicit: str | None = None) -> str | None:
    """The story this week's long-form is built from.

    Newest published explainer story that has NOT already carried a
    long-form. Published means it cleared the shorts showrunner, so the
    long-form starts from material the gate already liked — and the
    long-form gate still judges the finished 16:9 cut on its own terms.
    """
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    if explicit:
        return explicit if explicit in stories else None
    done = _already_longformed()
    for slug in _posted_slugs():
        if slug in stories and slug not in done:
            return slug
    return None


def _description(story_cfg: dict, meta: dict) -> str:
    """Watch-page description: the hook, YouTube chapters, then sources.

    Chapters are what make a watch-page video navigable (and are what the
    renderer's meta.json exists to provide) — YouTube needs the first one
    at 0:00, which `longform_render` already guarantees.
    """
    lines = [(story_cfg.get("hook") or story_cfg.get("title") or "").strip(), ""]
    chapters = meta.get("chapters") or []
    if chapters:
        lines.append("Chapters:")
        for ch in chapters:
            lines.append(f"{_ts(float(ch.get('t', 0.0)))} {ch.get('label', '')}")
        lines.append("")
    srcs = meta.get("sources") or []
    if srcs:
        lines.append("Sources:")
        lines.extend(f"- {s}" for s in srcs[:12])
        lines.append("")
    lines.append("#data #explained #charts #documentary")
    return "\n".join(lines)[:5000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None,
                    help="story to build (default: newest published "
                         "explainer story that has not had a long-form)")
    ap.add_argument("--title", default=None,
                    help="override the video title (default: the story's)")
    ap.add_argument("--dry-run", action="store_true",
                    help="render and JUDGE, but never upload")
    ap.add_argument("--publish-at", default=None,
                    help="RFC3339 timestamp to schedule (else public now)")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    slug = pick_slug(cfg, args.slug)
    if not slug:
        # Not a failure: a week where every published story already has a
        # long-form is an honest no-op, not an outage.
        print("[longform] no eligible story — nothing to build", flush=True)
        return 0
    story_cfg = stories[slug]

    will_upload = not args.dry_run
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / f"longform_{slug}.mp4"

    # ---- render the REAL 16:9 watch-page video -------------------------
    print(f"[longform] rendering 1920x1080 watch-page: {slug}", flush=True)
    from data_learning import longform_render
    longform_render.render(slug, final, config_path=CONFIG)

    meta_p = final.with_suffix(".meta.json")
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    thumb = final.with_suffix(".jpg")
    dur = float(meta.get("duration") or 0.0)
    print(f"[longform] {final} ({dur:.0f}s, "
          f"{len(meta.get('chapters') or [])} chapters, "
          f"thumbnail={'yes' if thumb.exists() else 'no'})", flush=True)

    # ---- THE GATE (fail-closed on a publish run) -----------------------
    from shared import showrunner_gate
    gate = showrunner_gate.run(
        final, slug=f"longform:{slug}", will_upload=will_upload,
        context={"format": "long_form", "channel": CHANNEL,
                 "aspect": "16:9", "duration_s": round(dur, 1),
                 "chapters": meta.get("chapters") or [],
                 "title": story_cfg.get("title", slug),
                 "hook": story_cfg.get("hook", "")})
    print(showrunner_gate.log(gate, slug=slug), flush=True)
    if gate.get("blocked"):
        # HELD, not lost: the mp4 stays in output/ for the preview branch and
        # the verdict is in the ledger, so the next build can act on it.
        print(f"[longform] NOT POSTING — held by the review gate: "
              f"{gate.get('reason', '')}", flush=True)
        return 0 if not will_upload else 3

    if args.dry_run:
        print("[longform] DRY RUN — judged, not uploading.", flush=True)
        return 0

    # ---- publish -------------------------------------------------------
    title = (args.title or story_cfg.get("title") or slug)[:100]
    desc = _description(story_cfg, meta)
    from shared.uploaders import YouTubeUploader
    up = YouTubeUploader(channel=CHANNEL)
    res = up.upload(file_path=final, title=title, description=desc,
                    tags=["data", "explained", "documentary", "charts"],
                    publish_at=args.publish_at,
                    thumbnail=thumb if thumb.exists() else None)
    url = getattr(res, "url", None) or str(res)
    print(f"[longform] uploaded -> {url}", flush=True)

    from shared.fsutil import load_state_json
    log = load_state_json(LONGFORM_LOG, default={"posted": []}) or {"posted": []}
    log.setdefault("posted", []).append({
        "url": url, "title": title, "slug": slug, "slugs": [slug],
        "format": "long_form_16x9", "duration_s": round(dur, 1),
        "showrunner_score": (gate.get("verdict") or {}).get("score"),
        "at": datetime.now(timezone.utc).isoformat()})
    LONGFORM_LOG.write_text(json.dumps(log, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
