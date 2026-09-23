#!/usr/bin/env python3
"""Render, judge and publish the next OpenRangeInteractive sleep film.

The whole path for one episode, and every gate is fail-closed:

  1. stop if the kill switch (`state/curiosity_kill_switch`) or PAUSED exists
  2. settle any upload a previous run left unconfirmed (never guess)
  3. the next unposted, VALID episode script in `data_learning/ori_episodes/`
  4. render it (`data_learning/ori_sleep.py`)
  5. technical floor: long enough to be a sleep film, a real thumbnail
  6. THE SHOWRUNNER (`shared/showrunner_gate.run`) watches it — a BLOCK,
     no verdict, an infra error or a timeout all HOLD on a publish run
  7. leak-scan the public payload (`publish_security.scan_upload`)
  8. claim -> upload to the curiosity channel token -> receipt -> posted log

    python scripts/post_ori.py --dry-run          # render + judge, no upload
    python scripts/post_ori.py                    # the cron path
    python scripts/post_ori.py --slug what-did-early-humans-do-at-night
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from data_learning import ori_sleep as OS      # noqa: E402

CONFIG = REPO / "data_learning" / "ori.config.json"
LOG = REPO / "state" / "curiosity_posted_log.json"
PENDING = REPO / "state" / "ori_pending.json"
KILL = REPO / "state" / "curiosity_kill_switch"
OUT = REPO / "output"
CHANNEL = "curiosity"

ATTRIBUTION = ("Music by Kevin MacLeod (incompetech.com), licensed under "
               "Creative Commons: By Attribution 4.0 "
               "(creativecommons.org/licenses/by/4.0/)")
BASE_TAGS = ["history for sleep", "sleep story", "relaxing history", "bedtime story",
             "history", "fall asleep", "cozy"]
DRAWN = ("Every picture in this film is drawn from scratch for this channel — "
         "no AI-generated images.")


def _ts(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def _load(path: Path, default):
    from shared.fsutil import load_state_json
    return load_state_json(path, default, expect_type=dict)


def _write(path: Path, data: dict) -> None:
    from shared.fsutil import atomic_write_json
    atomic_write_json(path, data)


def description(ep: dict, meta: dict) -> str:
    parts = [ep.get("description", "").strip()]
    ch = meta.get("chapters") or []
    if len(ch) >= 3:
        parts.append("Chapters:\n" + "\n".join(
            f"{_ts(c['t'])} {c['label']}" for c in ch))
    if ep.get("sources"):
        parts.append("Sources:\n" + "\n".join(
            f"- {s['name']}: {s['url']}" for s in ep["sources"]))
    parts.append(DRAWN)
    parts.append(ATTRIBUTION)
    parts.append(" ".join("#" + t.replace(" ", "") for t in tags(ep)[:5]))
    return "\n\n".join(p for p in parts if p)[:5000]


def tags(ep: dict) -> list[str]:
    seen, out = set(), []
    for t in list(ep.get("tags") or []) + BASE_TAGS:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:15]


def next_episode(explicit: str | None, posted: dict) -> dict | None:
    if explicit:
        ep = OS.load(explicit)
        bad = OS.validate(ep)
        if bad:
            raise SystemExit(f"{explicit}: invalid script: {'; '.join(bad)}")
        return ep
    import ori_author
    for slug in ori_author.queue():
        if slug not in posted:
            return OS.load(slug)
    return None


def reconcile(log: dict) -> int:
    """0 = safe to go on. An upload that STARTED and never confirmed is a
    question only a human can answer (was it accepted?) — guessing either
    way is a duplicate or an orphan, so the run stops and says exactly what
    to check."""
    p = _load(PENDING, {})
    if not p:
        return 0
    slug = p.get("slug")
    if p.get("phase") == "uploaded":
        if slug not in log["posted"]:
            log["posted"][slug] = {k: p.get(k) for k in
                                   ("url", "title", "at", "duration")}
            log["posted"][slug]["recovered"] = True
            _write(LOG, log)
            print(f"::warning::[ori] recovered accepted upload {slug} -> "
                  f"{p.get('url')}", flush=True)
        _write(PENDING, {})
        return 0
    print(f"::error::[ori] an upload of {slug!r} ({p.get('title')!r}) started "
          f"at {p.get('at')} and never confirmed. Check the OpenRangeInteractive "
          f"channel: if the video EXISTS add it to {LOG.name} under 'posted' "
          f"and empty {PENDING.name}; if it does NOT, just empty "
          f"{PENDING.name}. Then re-run.", flush=True)
    return 3


def technical_floor(out: Path, meta: dict, cfg: dict) -> list[str]:
    bad = []
    if not out.exists():
        return ["no rendered video on disk"]
    dur = float(meta.get("duration") or 0)
    if dur < float(cfg.get("min_seconds", 5400)):
        bad.append(f"{dur:.0f}s is under the {cfg.get('min_seconds')}s sleep-film floor")
    thumb = out.with_suffix(".jpg")
    try:
        from PIL import Image
        with Image.open(thumb) as im:
            if im.size != (1920, 1080):
                bad.append(f"thumbnail is {im.size}, not 1920x1080")
    except Exception:                                   # noqa: BLE001
        bad.append("no readable thumbnail")
    if len(meta.get("chapters") or []) < OS.MIN_CHAPTERS:
        bad.append(f"{len(meta.get('chapters') or [])} chapters rendered (at least {OS.MIN_CHAPTERS})")
    return bad


def judge_context(ep: dict, meta: dict) -> dict:
    """What the showrunner reads beside the frames. Its context window is a
    few thousand characters, so a two-hour script travels as each chapter's
    opening lines — enough to check a frame against what is being said."""
    return {"format": "sleep", "channel": CHANNEL, "aspect": "16:9",
            "duration_s": meta.get("duration"), "chapters": meta.get("chapters") or [],
            "title": ep["title"], "era": ep["era"],
            "hook": ep["chapters"][0]["beats"][0]["say"],
            "script": [{"chapter": c["title"],
                        "opening": c["beats"][0]["say"][:180]} for c in ep["chapters"]]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--publish-at", default=None)
    args = ap.parse_args()

    if KILL.exists() or (REPO / "PAUSED").exists():
        print("[ori] kill switch / PAUSED present — nothing runs", flush=True)
        return 0
    cfg = json.loads(CONFIG.read_text())
    log = _load(LOG, {"posted": {}})
    log.setdefault("posted", {})
    rc = reconcile(log)
    if rc:
        return rc

    ep = next_episode(args.slug, log["posted"])
    if ep is None:
        print("::warning::[ori] no unposted valid episode — run "
              "scripts/ori_author.py", flush=True)
        return 0
    slug = ep["slug"]
    will_upload = not args.dry_run
    out = OUT / f"ori_{slug}.mp4"
    print(f"[ori] episode {slug}: {ep['title']}", flush=True)
    meta = OS.render(ep, out)

    reasons = technical_floor(out, meta, cfg)
    from shared import showrunner_gate
    gate = showrunner_gate.run(
        out, slug=f"ori:{slug}", will_upload=will_upload, context=judge_context(ep, meta))
    print(showrunner_gate.log(gate, slug=slug), flush=True)
    if gate.get("blocked"):
        reasons.append("showrunner: " + str(gate.get("reason") or "blocked"))
    import publish_security
    desc = description(ep, meta)
    ok, sec = publish_security.scan_upload(out, ep["title"], desc, tags(ep))
    if not ok:
        reasons.extend(sec)
    (out.with_suffix(".result.json")).write_text(json.dumps(
        {"slug": slug, "publishable": not reasons, "reasons": reasons,
         "duration": meta.get("duration"),
         "score": (gate.get("verdict") or {}).get("score")}, indent=2) + "\n")
    if reasons:
        print(f"[ori] NOT POSTING {slug}: " + "; ".join(reasons), flush=True)
        return 3 if will_upload else 0
    if not will_upload:
        print(f"[ori] DRY RUN — {slug} is publishable, not uploading", flush=True)
        return 0

    now = datetime.now(timezone.utc).isoformat()
    _write(PENDING, {"slug": slug, "phase": "uploading", "title": ep["title"],
                     "at": now})
    from shared.uploaders import YouTubeUploader
    up = YouTubeUploader(channel=CHANNEL)
    srt = out.with_suffix(".srt")
    res = up.upload(file_path=out, title=ep["title"][:100], description=desc,
                    tags=tags(ep), publish_at=args.publish_at,
                    thumbnail=out.with_suffix(".jpg"), category="27",
                    audio_language="en",
                    captions_srt=srt if srt.exists() else None)
    vid = (getattr(res, "raw", None) or {}).get("id")
    url = f"https://www.youtube.com/watch?v={vid}" if vid else \
        (getattr(res, "url", None) or str(res))
    entry = {"url": url, "title": ep["title"], "at": now,
             "publish_at": args.publish_at, "duration": meta.get("duration"),
             "format": "sleep",
             "showrunner_score": (gate.get("verdict") or {}).get("score")}
    _write(PENDING, {"slug": slug, "phase": "uploaded", **entry})
    log["posted"][slug] = entry
    _write(LOG, log)
    _write(PENDING, {})
    print(f"[ori] uploaded {slug} -> {url}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
