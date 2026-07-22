#!/usr/bin/env python3
"""Render + upload the curiosity channel's LONG-FORM watch-page videos.

The curiosity channel (OpenRangeInteractive, CURIOSITY_BRAIN.md) publishes
4-5 minute 1920x1080 videos on the main feed — NOT Shorts — so it has its
own orchestrator instead of post_stories.py: the long-form renderer emits a
chapters sidecar, and the description is assembled playbook-style (premise
-> chapters block -> sources -> hashtags). Everything else mirrors the
explainer path: posted-log dedupe, channel-routed token, channel guard,
upload-cap early stop.

Auth (env, set in the workflow from repo secrets):
    YOUTUBE_CLIENT_SECRETS_JSON     shared OAuth client
    YOUTUBE_TOKEN_JSON_CURIOSITY    the curiosity channel's token
    YOUTUBE_EXPECTED_CHANNEL        e.g. "OpenRangeInteractive" (hard guard)

Usage:
    python scripts/post_curiosity.py --dry-run             # render only
    python scripts/post_curiosity.py --max 1               # weekly cadence
    python scripts/post_curiosity.py --slugs kola-deepest-hole
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CONFIG = REPO / "data_learning" / "curiosity.config.json"
OUTPUT_DIR = REPO / "output"
LOG_PATH = REPO / "state" / "curiosity_posted_log.json"

BASE_HASHTAGS = ["curiosity", "educational", "documentary", "facts",
                 "science", "visualized"]
ATTRIBUTION = ("Music by Kevin MacLeod (incompetech.com), licensed under "
               "Creative Commons: By Attribution 4.0 "
               "(creativecommons.org/licenses/by/4.0/)")


def _load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"posted": {}}


def _save_log(log: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2) + "\n")


def _tags(sc: dict) -> list[str]:
    seen, out = set(), []
    for t in list(sc.get("hashtags", [])) + BASE_HASHTAGS:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:15]


def _ts(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def _chapters_block(meta: dict) -> str:
    lines = [f"{_ts(c['t'])} {c['label']}" for c in meta.get("chapters", [])]
    # YouTube requires the first stamp at 00:00 and >=3 stamps.
    if len(lines) < 3 or not lines[0].startswith("00:00"):
        return ""
    return "\n".join(lines)


def _human_body(sc: dict) -> str:
    cap = (sc.get("caption") or "").strip()
    if cap:
        return cap
    return f"{sc.get('hook', '')}\n\n{sc.get('closing', '')}".strip()


def _description(sc: dict, meta: dict) -> str:
    parts = [_human_body(sc)]
    ch = _chapters_block(meta)
    if ch:
        parts.append("Chapters:\n" + ch)
    if meta.get("sources"):
        parts.append("Sources:\n" + "\n".join(
            f"- {s}" for s in meta["sources"][:8]))
    tags = " ".join(f"#{t}" for t in _tags(sc))
    parts.append(tags)
    parts.append(ATTRIBUTION)
    return "\n\n".join(p for p in parts if p)[:5000]


def _render_story(slug: str, out: Path, config: Path) -> dict:
    """Render through the CANONICAL pro pipeline (produce.py: pro_render + the full
    director loop + gates + repair + publishing package + fallback/vision verdict).
    Legacy ``longform_render`` is the EXPLICIT fallback, used only when there is no
    pro beat story for the slug or the pro build itself cannot run — never as the
    default publisher (audit #1: "make the pro renderer the publishing renderer").

    Returns {"engine": "pro"|"legacy", "produce": <produce result or None>}.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import produce
        produce.resolve_story(slug)          # raises FileNotFoundError if no pro story
    except Exception as e:  # noqa: BLE001 — no pro story: fall back to legacy engine
        print(f"[{slug}] no pro story ({str(e)[:70]}) — LEGACY longform fallback",
              flush=True)
        from data_learning import longform_render
        longform_render.render(slug, out, config_path=config)
        return {"engine": "legacy", "produce": None}
    print(f"[{slug}] rendering through PRO producer (canonical path)", flush=True)
    result = produce.produce(slug, out)
    return {"engine": "pro", "produce": result}


def _prepublish_gate(out: Path, sc: dict) -> tuple[bool, list[str]]:
    """A flagged video MUST NOT ship (data_learning/DIRECTOR.md). The production
    renderer (longform) can't run the full auto-fix loop, but the publish boundary
    still enforces the law: run the renderer-agnostic judges — the HOOK director
    (opening) and the INTEREST judge (dead time) — on the finished mp4 and BLOCK
    the upload if either fails. Reported, never silently published."""
    import subprocess
    import tempfile
    sys.path.insert(0, str(REPO / "scripts"))
    reasons: list[str] = []
    try:
        import hook_director
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([sys.executable, str(REPO / "scripts" /
                            "interest_judge.py"), str(out), "--out", td],
                           check=True, capture_output=True)
            interest = json.loads(
                (Path(td) / "interest" / "interest.json").read_text())
        if interest.get("dead_fraction", 0) > 0.5:
            reasons.append(f"dead-time {interest['dead_fraction']} > 0.5 "
                           "(too many boring stretches)")
        line = str(sc.get("hook") or sc.get("headline")
                   or sc.get("title") or "").strip()
        hv = hook_director.grade(line, out, hook_seconds=8.0)
        if not hv["pass"]:
            reasons.append(f"weak hook {hv['total']}/10 "
                           f"visual={hv['visual'].get('gates')} "
                           f"line={hv['line'].get('gates')}")
    except Exception as e:  # noqa: BLE001 — a gate error must FAIL CLOSED, not
        reasons.append(f"gate could not run ({str(e)[:60]}) — refusing to "
                       "publish unjudged")            # publish something unjudged
    return (not reasons, reasons)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*",
                    help="story slugs to post (default: un-posted, oldest "
                         "config order first)")
    ap.add_argument("--max", type=int, default=0,
                    help="post at most N stories this run (0 = no cap); "
                         "the weekly cadence uses --max 1")
    ap.add_argument("--channel", default="curiosity",
                    help="channel slug for token routing (reads "
                         "YOUTUBE_TOKEN_JSON_CURIOSITY)")
    ap.add_argument("--check-channel", action="store_true",
                    help="print which channel the token maps to and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="render but do not upload")
    ap.add_argument("--force", action="store_true",
                    help="re-post even if the slug is in the posted log "
                         "(dedup/scheduling only — NEVER bypasses a quality, "
                         "factual, legal, or technical gate)")
    ap.add_argument("--publish-in-hours", type=float, default=0.0,
                    help="schedule the upload this many hours from now "
                         "(private until publishAt); 0 = public now")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--log", type=Path, default=LOG_PATH)
    args = ap.parse_args()

    if args.check_channel:
        from uploaders import YouTubeUploader
        me = YouTubeUploader(channel=args.channel).whoami()
        print(f"token maps to channel: title={me['title']!r} "
              f"handle={me['handle']!r} id={me['id']}")
        return 0

    cfg = json.loads(args.config.read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    slugs = args.slugs or list(stories)
    unknown = [s for s in slugs if s not in stories]
    if unknown:
        print(f"unknown slugs: {unknown}\navailable: {list(stories)}",
              file=sys.stderr)
        return 2

    log = json.loads(args.log.read_text()) if args.log.exists() else \
        {"posted": {}}
    log.setdefault("posted", {})
    results, uploader, posted_this_run = [], None, 0

    for slug in slugs:
        if args.max and posted_this_run >= args.max:
            print(f"--max {args.max} reached; remaining slugs wait for the "
                  "next run")
            break
        sc = stories[slug]
        if not args.force and slug in log["posted"]:
            print(f"[{slug}] already posted -> "
                  f"{log['posted'][slug].get('url')}, skipping")
            continue
        out = OUTPUT_DIR / f"curiosity_{slug}.mp4"
        print(f"[{slug}] rendering long-form -> {out}", flush=True)
        render_report = _render_story(slug, out, args.config)
        meta = json.loads(out.with_suffix(".meta.json").read_text())
        dur = meta.get("duration", 0)
        if dur < 120:
            print(f"[{slug}] REJECTED: {dur:.0f}s is too short for the "
                  "watch-page format (target 4-5 min) — expand the story",
                  file=sys.stderr)
            results.append({"slug": slug, "ok": False, "error": "too short"})
            continue

        # QUALITY GATE — a flagged video must not ship (DIRECTOR.md). TWO layers:
        # (1) the producer's own verdict — the full director loop + honest fallback
        #     classifier + vision taste verdict. A QUARANTINE here is non-bypassable:
        #     an unacceptable fallback / missing judge / failed package must NOT
        #     publish, and --force must never override a quality/factual/legal gate
        #     (audit #5). --force covers only dedup + scheduling.
        # (2) the renderer-agnostic hook + dead-time judges on the finished mp4.
        gate_reasons: list[str] = []
        prod = render_report.get("produce")
        if prod is not None and prod.get("status") != "pass":
            gate_reasons.append("producer QUARANTINE: " + "; ".join(prod["reasons"]))
        gate_ok, judge_reasons = _prepublish_gate(out, sc)
        gate_reasons.extend(judge_reasons)
        if gate_reasons:
            print(f"[{slug}] QUALITY GATE FAILED: {'; '.join(gate_reasons)}",
                  file=sys.stderr)
            print(f"[{slug}] refusing to publish (--force cannot bypass quality "
                  "gates; it only overrides dedup/scheduling)", file=sys.stderr)
            results.append({"slug": slug, "ok": False,
                            "error": "quality gate: " + "; ".join(gate_reasons)})
            continue

        if args.dry_run:
            print(f"[{slug}] dry-run: rendered {dur:.0f}s, not uploading")
            results.append({"slug": slug, "ok": True, "url": "(dry-run)"})
            posted_this_run += 1
            continue

        publish_at = None
        if args.publish_in_hours > 0:
            when = (datetime.now(timezone.utc)
                    + timedelta(hours=args.publish_in_hours))
            publish_at = when.replace(microsecond=0).isoformat().replace(
                "+00:00", "Z")

        if uploader is None:
            from uploaders import YouTubeUploader
            uploader = YouTubeUploader(channel=args.channel)
        desc = _description(sc, meta)
        thumb = out.with_suffix(".jpg")
        try:
            from localize import localize_meta
            localizations = localize_meta(
                sc.get("title", slug), _human_body(sc),
                "\n\n" + _chapters_block(meta))
        except Exception as e:  # noqa: BLE001 — never let i18n block a post
            print(f"[{slug}] localization skipped: {e}", flush=True)
            localizations = {}
        print(f"[{slug}] uploading {dur:.0f}s video"
              + (f" (scheduled {publish_at})" if publish_at else ""),
              flush=True)
        srt = out.with_suffix(".srt")
        try:
            res = uploader.upload(
                file_path=out,
                title=sc.get("title", slug)[:100],
                description=desc,
                tags=_tags(sc),
                publish_at=publish_at,
                thumbnail=thumb if thumb.exists() else None,
                localizations=localizations,
                category="27",              # Education — the watch-page niche
                audio_language="en",
                captions_srt=srt if srt.exists() else None,
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            print(f"[{slug}] UPLOAD FAILED: {msg}", flush=True)
            results.append({"slug": slug, "ok": False, "error": msg})
            if ("uploadLimitExceeded" in msg
                    or "exceeded the number of videos" in msg):
                print("[post_curiosity] daily upload cap reached — stopping.",
                      flush=True)
                break
            continue
        url = getattr(res, "url", None) or str(res)
        vid = (getattr(res, "raw", None) or {}).get("id")
        if vid:                       # long-form: a watch URL, not /shorts/
            url = f"https://www.youtube.com/watch?v={vid}"
        print(f"[{slug}] uploaded -> {url}", flush=True)
        log["posted"][slug] = {
            "url": url, "title": sc.get("title"),
            "at": datetime.now(timezone.utc).isoformat(),
            "publish_at": publish_at, "duration": dur,
        }
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(json.dumps(log, indent=2) + "\n")
        results.append({"slug": slug, "ok": True, "url": url})
        posted_this_run += 1

    ok = sum(1 for r in results if r["ok"])
    print(f"\ndone: {ok}/{len(results)} ok")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
