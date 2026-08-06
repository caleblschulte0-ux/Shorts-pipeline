#!/usr/bin/env python3
"""Post the curated data-explainer STORY shorts to a single channel.

This is a separate, self-contained path from the trending daily pipeline
(scripts/run_trending_daily.py) so the existing channel is never touched.
It renders each story slug with studio_render and uploads it with the
YouTubeUploader — which enforces YOUTUBE_EXPECTED_CHANNEL, so a wrong token
can never post to the wrong account.

Auth (env, set in the workflow from repo secrets):
    YOUTUBE_CLIENT_SECRETS_JSON   shared OAuth client (same app is fine)
    YOUTUBE_TOKEN_JSON            the TARGET channel's token
    YOUTUBE_EXPECTED_CHANNEL      e.g. "short_explainer67" (hard guard)

Usage:
    python scripts/post_stories.py --dry-run            # render only, no upload
    python scripts/post_stories.py                      # render + upload (public)
    python scripts/post_stories.py --slugs debt-trap grocery-squeeze
    python scripts/post_stories.py --every-hours 6      # schedule, spaced out
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# studio_render (and its Pillow/matplotlib/numpy deps) is imported lazily
# inside the render loop so --check-channel works with only the google libs.

CONFIG = REPO / "data_learning" / "niche.config.json"
OUTPUT_DIR = REPO / "output"
STATE_DIR = REPO / "state"
# Deliberately a DIFFERENT log file from the trending pipeline's
# state/posted_log.json so the two channels never collide. Sibling channels
# (e.g. curiosity) pass --config/--log to get their own story config and
# posted-log; these module-level paths stay the explainer defaults.
LOG_PATH = STATE_DIR / "explainer_posted_log.json"


def _load_log(path: Path = LOG_PATH) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return {"posted": {}}


def _save_log(log: dict, path: Path = LOG_PATH) -> None:
    from shared.fsutil import atomic_write_json
    atomic_write_json(path, log)


# Evergreen hashtags every data-explainer Short carries, on top of whatever the
# story config specifies. Kept relevant (no spammy #viral/#fyp) so YouTube
# doesn't discard them, and deliberately short — YouTube IGNORES ALL hashtags in
# a description once there are more than 15, so we cap hard below.
BASE_HASHTAGS = ["shorts", "facts", "didyouknow", "data", "explained",
                 "education", "interesting"]
# Required attribution for the CC-BY music bed (Kevin MacLeod / incompetech).
ATTRIBUTION = ("Music by Kevin MacLeod (incompetech.com), licensed under "
               "Creative Commons: By Attribution 4.0 "
               "(creativecommons.org/licenses/by/4.0/)")


def _dedupe(seq):
    """Order-preserving, case-insensitive dedupe."""
    seen, out = set(), []
    for x in seq:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _merged_tags(cfg: dict) -> list[str]:
    """Story hashtags first (most specific), then evergreen base. For the API
    `tags` field, capped at YouTube's 30 (well within the 500-char limit for
    these short tags)."""
    return _dedupe(list(cfg.get("hashtags", [])) + BASE_HASHTAGS)[:30]


def _human_body(cfg: dict) -> str:
    """The prose part of the description (caption, or hook + closing)."""
    cap = (cfg.get("caption") or "").strip()
    if cap:
        parts = [cap]
    else:
        parts = [cfg.get("hook", "").strip()]
        if cfg.get("closing"):
            parts += ["", cfg["closing"].strip()]
    return "\n".join(p for p in parts if p)


def _desc_suffix(cfg: dict) -> str:
    """The non-prose tail appended to EVERY description (English and localized):
    a hashtag block (<=15 so YouTube keeps them) + the CC-BY attribution."""
    tags = _merged_tags(cfg)[:15]
    block = " ".join(f"#{t}" for t in tags)
    return (f"\n\n{block}" if block else "") + f"\n\n{ATTRIBUTION}"


def _description(cfg: dict) -> str:
    return (_human_body(cfg) + _desc_suffix(cfg))[:5000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*",
                    help="story slugs to post (default: every story in config)")
    ap.add_argument("--channel", default="explainer",
                    help="channel slug for token routing: 'explainer' reads "
                         "YOUTUBE_TOKEN_JSON_EXPLAINER (default); '' uses the "
                         "original YOUTUBE_TOKEN_JSON")
    ap.add_argument("--check-channel", action="store_true",
                    help="print which channel the token maps to and exit "
                         "(read-only, posts nothing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="render but do not upload")
    ap.add_argument("--publish", action="store_true",
                    help="EXPLICITLY opt in to uploading. Without this (and "
                         "without PUBLISH_ENABLED=1) publishing is FROZEN: the "
                         "pipeline renders + reviews but never uploads. The "
                         "channel's fail-closed kill-switch.")
    ap.add_argument("--force", action="store_true",
                    help="re-post even if the slug is in the posted log")
    ap.add_argument("--every-hours", type=float, default=0.0,
                    help="schedule uploads this many hours apart (private until "
                         "publishAt); 0 = publish immediately")
    ap.add_argument("--start-in-hours", type=float, default=1.0,
                    help="when scheduling, how long from now the first one posts")
    ap.add_argument("--config", type=Path, default=CONFIG,
                    help="story config JSON (default: data_learning/"
                         "niche.config.json; sibling channels pass their own)")
    ap.add_argument("--log", type=Path, default=LOG_PATH,
                    help="posted-log JSON (default: state/"
                         "explainer_posted_log.json)")
    ap.add_argument("--repair", type=int, default=2,
                    help="on a showrunner BLOCK, restructure the weakest scene "
                         "and re-render this many times before giving up "
                         "(0 = never repair)")
    ap.add_argument("--max-per-run", type=int, default=0,
                    help="render at most N new videos this run (0 = all); the "
                         "rest wait for the next run. Guards the CI job cap now "
                         "that each 3D render is slow.")
    args = ap.parse_args()

    if args.check_channel:
        from shared.uploaders import YouTubeUploader
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

    log = _load_log(args.log)
    results = []
    uploader = None
    rendered = 0
    when = datetime.now(timezone.utc) + timedelta(hours=args.start_in_hours)

    # PER-DAY cap, not just per-RUN. `--max-per-run` alone cannot hold the
    # registry's daily count when the workflow fires twice in a day (a cron
    # AND a chained trigger, or a manual re-run after a partial): the posted
    # log dedupes SLUGS, so a second run simply posts the NEXT four stories
    # — different videos, same day, 8/4. Count what already went out today
    # and shrink this run's budget by it. `--force` re-posts are exempt: an
    # operator explicitly re-shipping a fixed video is not a scheduling bug.
    if args.max_per_run and not args.force:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        posted_today = sum(
            1 for e in log["posted"].values()
            if str(e.get("at", "")).startswith(today))
        if posted_today:
            budget = max(0, args.max_per_run - posted_today)
            print(f"[post_stories] {posted_today} already posted today — "
                  f"this run's budget is {budget} (per-day cap "
                  f"{args.max_per_run})", flush=True)
            args.max_per_run = budget
            if budget == 0:
                print("[post_stories] the day is full — nothing to do",
                      flush=True)
                return 0

    # FAIL-CLOSED publish control. Publishing is FROZEN unless explicitly opted
    # into; nothing here can silently upload. See scripts/editorial_gate.py.
    from scripts import editorial_gate as _eg
    frozen = not args.dry_run and not _eg.publish_enabled(args.publish)
    if frozen:
        print("[post_stories] PUBLISH FROZEN — rendering + reviewing only, NOT "
              "uploading. Pass --publish (or set PUBLISH_ENABLED=1) to upload.",
              flush=True)

    for slug in slugs:
        sc = stories[slug]
        if not args.force and slug in log["posted"]:
            print(f"[{slug}] already posted -> {log['posted'][slug].get('url')}, "
                  f"skipping (use --force to repost)")
            continue

        # PRE-RENDER editorial gate (#2 real data, #3 premise bar). A story that
        # can never publish — synthetic numbers, or a searchable-noun premise —
        # is HELD before we spend a render on it. Previews (--dry-run) still
        # render so the result can be eyeballed, but the verdict is printed.
        pre = _eg.pre_render_verdict(sc)
        if not pre["ok"]:
            print(f"[{slug}] EDITORIAL HOLD (pre-render): "
                  + "; ".join(pre["reasons"][:8]), flush=True)
            if not args.dry_run:
                results.append({"slug": slug, "ok": False,
                                "error": "editorial_hold",
                                "reasons": pre["reasons"]})
                continue

        if args.max_per_run and rendered >= args.max_per_run:
            print(f"[{slug}] deferred to next run (hit --max-per-run="
                  f"{args.max_per_run})")
            continue
        rendered += 1
        out = OUTPUT_DIR / f"story_{slug}.mp4"
        print(f"[{slug}] rendering -> {out}", flush=True)
        from data_learning import studio_render       # lazy: needs Pillow etc.
        studio_render.render(slug, out, config_path=args.config)

        # SHOWRUNNER gate  (see the repair loop below: a BLOCK is a diagnosis
        # to act on, not the end of the story) — the editor with a veto. A headless Claude actually
        # WATCHES the finished video (extracts frames + reads the transcript)
        # and grades it against docs/DIRECTOR.md. Its verdict is authoritative.
        #
        # Fail direction depends on intent: on a PUBLISH run the gate fails
        # CLOSED — if the reviewer can't run (no key, API/ffmpeg error, timeout)
        # we do NOT know the video is good, so we HOLD it. Only a preview/frozen
        # run fails open (so iteration isn't blocked by infra). "If this is not
        # clearly good, it does not publish."
        will_upload = not args.dry_run and not frozen
        ctx = {"slug": slug, "title": sc.get("title"),
               "hook": sc.get("hook"), "closing": sc.get("closing"),
               "segments": [s.get("say") or s.get("topic")
                            for s in sc.get("segments", [])][:8]}
        # The policy — fail CLOSED on a publish run, SHOWRUNNER=off refused on
        # a publish run, a BLOCK is sovereign — moved to
        # `shared/showrunner_gate.py` so the trending channel (6 videos a day,
        # previously unwatched) runs the SAME gate rather than a second copy
        # of it. See docs/SYSTEM_AUDIT.md §D.
        from shared import showrunner_gate as _gate
        gate = _gate.run(out, slug=slug, context=ctx, will_upload=will_upload)
        _gate.log(gate, slug)
        blocked = gate["blocked"]
        verdict = gate["verdict"]

        # ---- BOUNDED SELF-REPAIR ------------------------------------------
        # The gate's verdict names the weakest scene and why. Rather than drop
        # the video there, restructure that ONE scene (scene_repair picks a
        # claim-compatible depiction, objective-gated then vision-ranked),
        # re-render, and let the gate judge again. The gate still decides —
        # this only gives it a better cut to judge. Bounded: a cut only ever
        # uploads on a SHIP verdict, so a repair that lands worse simply keeps
        # the video held, exactly as before.
        repairs = 0
        while (blocked and repairs < args.repair
               and (verdict or {}).get("score") is not None):
            repairs += 1
            try:
                from scripts import scene_repair as _sr2
                plan = _sr2.propose(slug, verdict, apply_plan=True)
                print(f"[{slug}] repair {repairs}/{args.repair}: seg "
                      f"{plan.get('seg')} -> {plan.get('chosen')}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{slug}] repair {repairs} could not plan a fix: "
                      f"{str(e)[:120]}", flush=True)
                break
            studio_render.render(slug, out, config_path=args.config)
            gate = _gate.run(out, slug=slug, context=ctx,
                             will_upload=will_upload)
            blocked = gate["blocked"]
            verdict = gate["verdict"]
            print(f"[{slug}] after repair {repairs}: "
                  f"{'BLOCK' if blocked else 'SHIP'} "
                  f"score={verdict.get('score')} — "
                  f"{verdict.get('one_line') or gate['reason']}", flush=True)

        if args.dry_run:
            print(f"[{slug}] dry-run: rendered, not uploading")
            results.append({"slug": slug, "ok": True,
                            "url": "(dry-run)" if not blocked
                                   else "(dry-run, showrunner BLOCK)"})
            continue

        if blocked:
            print(f"[{slug}] NOT POSTING — held by the review gate as not up to "
                  f"standard. See {out.name}.showrunner.json.", flush=True)
            results.append({"slug": slug, "ok": False,
                            "error": "showrunner_block"})
            continue

        if frozen:
            print(f"[{slug}] rendered + reviewed OK, but PUBLISH FROZEN — not "
                  f"uploading. Re-run with --publish to release.", flush=True)
            results.append({"slug": slug, "ok": True, "url": "(frozen)"})
            continue

        publish_at = None
        if args.every_hours > 0:
            publish_at = when.replace(microsecond=0).isoformat().replace(
                "+00:00", "Z")
            when += timedelta(hours=args.every_hours)

        if uploader is None:                 # lazy import → clear error if deps
            from shared.uploaders import YouTubeUploader
            uploader = YouTubeUploader(channel=args.channel)
        print(f"[{slug}] uploading"
              + (f" (scheduled {publish_at})" if publish_at else " (public now)"),
              flush=True)
        # studio_render writes a title-aligned thumbnail next to the mp4.
        thumb = out.with_suffix(".jpg")
        # Localized titles/descriptions (best-effort; English always ships).
        try:
            from shared.localize import localize_meta
            localizations = localize_meta(
                sc.get("title", slug), _human_body(sc), _desc_suffix(sc))
        except Exception as e:  # noqa: BLE001 — never let i18n block a post
            print(f"[{slug}] localization skipped: {e}", flush=True)
            localizations = {}
        # Upload is the one step that legitimately fails mid-batch (YouTube's
        # daily upload cap, a transient 5xx, a single bad video). Don't let one
        # failure abort the rest — record it and move on. The one exception is
        # the daily upload-limit: once hit, EVERY remaining upload will fail the
        # same way, so stop early rather than burn render time on videos that
        # physically can't post until the cap resets.
        try:
            res = uploader.upload(
                file_path=out,
                title=sc.get("title", slug)[:100],
                description=_description(sc),
                tags=_merged_tags(sc),
                publish_at=publish_at,
                thumbnail=thumb if thumb.exists() else None,
                localizations=localizations,
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            limit_hit = ("uploadLimitExceeded" in msg
                         or "exceeded the number of videos" in msg)
            print(f"[{slug}] UPLOAD FAILED: {msg}", flush=True)
            results.append({"slug": slug, "ok": False, "error": msg})
            if limit_hit:
                print("[post_stories] YouTube daily upload cap reached — "
                      "stopping; remaining stories will retry next run.",
                      flush=True)
                break
            continue
        url = getattr(res, "url", None) or str(res)
        print(f"[{slug}] uploaded -> {url}", flush=True)
        log["posted"][slug] = {
            "url": url, "title": sc.get("title"),
            "at": datetime.now(timezone.utc).isoformat(),
            "publish_at": publish_at,
        }
        _save_log(log, args.log)
        results.append({"slug": slug, "ok": True, "url": url})

    ok = sum(1 for r in results if r["ok"])
    print(f"\ndone: {ok}/{len(results)} ok")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
