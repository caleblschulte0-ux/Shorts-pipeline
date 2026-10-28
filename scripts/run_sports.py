#!/usr/bin/env python3
"""Baller Bro's daily posts: SPORTS MOMENTS (registry channel `trending`).

Operator, 2026-10-11, of the OG channel (439 graph races and Reddit
stories at ~3 views each): *"we need to turn that into something"*,
picked "sports moments" off the samples, then *"we'll switch it to
sports moments"*. The registry's `sports_moment` format says how many;
this is the run that makes and posts them.

Each slot is the sample maker's pipeline (`scripts/sports_samples.py`:
the week's most upvoted video posts on the sports subreddits, the brain
picks the moments with PEOPLE in them, the Twitch channel's editor cuts
them) plus the two things a post owes that a sample does not:

  * the SHOWRUNNER watches it and its block is sovereign, through the
    one shared policy (`shared/showrunner_gate`), fail-closed on a
    publish run;
  * the upload is CLAIMED ON MAIN before the API call, through the
    trending posted log's own `_guarded_upload` (`ClaimNotDurable`
    refuses an upload no later run could see). The Reddit permalink is
    the `topic`, so the same post is never cut twice whatever the title
    says.

    python scripts/run_sports.py              # post the registry's count
    python scripts/run_sports.py --dry-run    # render + judge, upload nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import run_trending_daily as rt  # noqa: E402
from scripts import sports_samples as ss  # noqa: E402
from shared import channel_registry as reg  # noqa: E402

CHANNEL = "trending"
FORMAT = "sports_moment"
OUT = ROOT / "output" / "sports"
REPORT = ROOT / "sports_report.json"
#: Candidates one run may cut per slot it owes. Each costs a download, a
#: transcription, an author call, a render and a judge (about three
#: minutes), and a gate that refuses everything on a bad day must not eat
#: the whole job timeout. The first dry run (2026-10-11) passed one cut in
#: seven, so three tries a slot would post one video a day, not three.
TRIES_PER_SLOT = 5
# A refused cut is REPAIRED before the post is dropped (2026-10-14: an
# Ovechkin cut scored 83 and was held for our line over the source's
# banner and an ending that drifted off the emotion, and the run moved on
# to weaker posts). The judge's own problems and fixes go back to the
# author, the post is cut again and judged again by the same gate, up to
# REPAIRS times. Below REPAIR_MIN there is no moment worth repairing.
REPAIR_MIN = 60
REPAIRS = 2

def permalink_key(c: dict) -> str:
    """The post's identity: its Reddit permalink, else its video URL."""
    p = (c.get("permalink") or "").strip()
    if p.startswith("/"):
        p = "https://www.reddit.com" + p
    return (p or c.get("url") or "").split("?")[0].rstrip("/")


def already_used(pool: list[dict], log: dict) -> set[str]:
    """Keys of pool posts the channel has already posted or claimed."""
    seen = {rt._norm(e.get("topic")) for e in log.get("posted") or []}
    seen |= {rt._norm(u.get("topic")) for u in log.get("uploads") or []}
    seen.discard("")
    return {permalink_key(c) for c in pool
            if rt._norm(permalink_key(c)) in seen}


def next_slot(slots, *, after: str = "", now: datetime | None = None,
              log: dict | None = None) -> str:
    """The next publish slot at least fifteen minutes out, later than the
    one the last post took AND the registry's gap clear of every other
    Baller Bro video going live (`log`, the trending posted log) — asked
    at upload time, not run start, because a run that spent an hour on
    cuts the gate refused must not hand YouTube a publishAt that has
    already passed, and a catch-up run must not land on a slot an earlier
    run or a mailbox ship already filled (operator, 2026-10-14: "we can't
    drop 3 videos in 2 hours")."""
    from shared import post_spacing
    now = now or datetime.now(timezone.utc)
    busy = post_spacing.taken(log or {}, now=now)
    gap = post_spacing.min_gap(CHANNEL)
    t = post_spacing.next_free_slot(slots or rt._publish_slots(), busy, gap,
                                    after=post_spacing.parse(after), now=now)
    return post_spacing.iso(t)


def description(meta: dict, c: dict) -> str:
    """Caption, the call to action, the credit, the tags."""
    parts = [meta.get("caption") or c.get("post_title") or "",
             meta.get("cta") or ""]
    parts.append(f"Via r/{c.get('sub')}: {permalink_key(c)}")
    tags = " ".join(f"#{t.lstrip('#')}" for t in meta.get("hashtags") or [])
    if tags:
        parts.append(tags)
    return "\n\n".join(p for p in parts if p.strip())


def tags(meta: dict, c: dict) -> list[str]:
    out = [t.lstrip("#") for t in meta.get("hashtags") or []]
    out += [c.get("who") or "", c.get("sub") or "", "sports", "shorts"]
    return [t for i, t in enumerate(out) if t and t not in out[:i]][:15]


def over_graphic(v: dict) -> bool:
    """The judge saw our line over a graphic the footage carries."""
    ws = v.get("weakest_scene") or {}
    text = " ".join([str(ws.get("failure_class") or "")]
                    + [str(x) for x in v.get("auto_fails") or []]
                    + [str(x) for x in v.get("problems") or []]).lower()
    return ("text_over_source" in text or "over the source" in text
            or "banner" in text or "lower-third" in text
            or "lower third" in text or "scorebug" in text)


def repair_notes(v: dict, meta: dict) -> str:
    """The refused cut's verdict, in words the author can cut from."""
    cut = (meta.get("edit") or {}).get("cut") or {}
    lines = [f"THE JUDGE REFUSED YOUR LAST CUT ({v.get('score')}/100). "
             f"It was titled {meta.get('title')!r} with the line "
             f"{meta.get('hook')!r}, cut from {cut.get('start')}s to "
             f"{cut.get('end')}s of the source. Cut it again so every "
             "problem below is gone: move the start and end, rewrite the "
             "title and line so they promise only what the footage shows. "
             "If it cannot be fixed from this footage, complete=false.",
             f"Verdict: {v.get('one_line') or ''}"]
    lines += [f"Problem: {p}" for p in (v.get("problems") or [])[:5]]
    lines += [f"Fix: {f}" for f in (v.get("fixes") or [])[:5]]
    return "\n".join(lines)


def judge(mp4: Path, c: dict, meta: dict, hook: str, *,
          will_upload: bool) -> dict:
    from shared import showrunner_gate
    slug = rt._slug(f"sports {c.get('who')} {permalink_key(c)[-12:]}")
    ctx = {"slug": slug, "title": meta.get("title"), "hook": hook,
           "format": FORMAT, "topic": permalink_key(c),
           "segments": [c.get("post_title"), meta.get("caption")]}
    gate = showrunner_gate.run(mp4, slug=slug, context=ctx,
                               will_upload=will_upload)
    showrunner_gate.log(gate, slug)
    return gate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=None,
                    help="default: the registry's sports_moment target")
    ap.add_argument("--period", default="week")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    want = a.count if a.count is not None else \
        reg.target_mix(CHANNEL).get(FORMAT, 0)
    report = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
              "format": FORMAT, "want": want, "dry_run": a.dry_run,
              "slots": []}

    def _save():
        REPORT.write_text(json.dumps(report, indent=1, default=str))

    if not want:
        print(f"[sports] the registry asks for no {FORMAT} today", flush=True)
        _save()
        return 0

    rt._refresh_log_from_origin()
    log = rt.load_log()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    done_today = [e for e in rt.uploaded_on(log, today)
                  if e.get("format") == FORMAT]
    need = max(0, want - len(done_today))
    report["already_today"] = len(done_today)
    if not need and not a.dry_run:
        print(f"[sports] {len(done_today)}/{want} already posted today",
              flush=True)
        _save()
        return 0
    need = need or want

    pool = ss.discover(a.period)
    used = already_used(pool, log)
    fresh = [c for c in pool if permalink_key(c) not in used]
    report.update(pool=len(pool), already_posted=len(used))
    print(f"[sports] {len(pool)} posts, {len(used)} already used, "
          f"{len(fresh)} fresh", flush=True)
    if not fresh:
        print("::error::no fresh sports video posts reached the runner",
              flush=True)
        _save()
        return 1

    picks = ss.pick(fresh, need * TRIES_PER_SLOT)
    slots = [tuple(s) for s in
             reg.channel(CHANNEL).get("cadence", {})
             .get("publish_slots_central") or []] or None
    last_slot = ""
    work = OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    shipped = 0
    for c in picks:
        if shipped >= need:
            break
        row = {k: c.get(k) for k in ("sub", "who", "why", "post_title",
                                     "upvotes", "url")}
        row["topic"] = permalink_key(c)
        report["slots"].append(row)
        _save()
        t0 = time.time()
        info = ss.fetch(c, work)
        if not info:
            row["skipped"] = "download failed"
            continue
        short = ss.unfit(info) or ss.too_short(info)
        if short:
            row["skipped"] = short
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", (c.get("who") or "").lower()
                      ).strip("-")[:40] or "clip"
        mp4 = OUT / f"{len(report['slots']):02d}_{slug}.mp4"
        try:
            made = ss.make(c, info, mp4)
        except Exception as e:  # noqa: BLE001
            row["skipped"] = f"render failed: {type(e).__name__}: {e}"[:300]
            continue
        if made.get("skipped") or not mp4.exists():
            row["skipped"] = made.get("skipped") or "no render"
            continue
        meta = made.get("meta") or {}
        if not meta.get("title"):
            # no brain wrote it: a post with no title of ours is not a post
            row["skipped"] = "author: no title"
            continue
        row.update(title=meta["title"], hook=made.get("hook"),
                   ledger=made.get("ledger"))

        gate = judge(mp4, c, meta, made.get("hook") or "",
                     will_upload=not a.dry_run)
        line_top = False
        for _ in range(REPAIRS):
            v = gate.get("verdict") or {}
            if not gate["blocked"] or (v.get("score") or 0) < REPAIR_MIN:
                break
            line_top = line_top or over_graphic(v)
            row.setdefault("repairs", []).append(
                {"score": v.get("score"), "reason": gate.get("reason")})
            try:
                again = ss.make(c, info, mp4, notes=repair_notes(v, meta),
                                line_top=line_top)
            except Exception as e:  # noqa: BLE001
                print(f"[sports] repair failed: {e}", flush=True)
                break
            if (again.get("skipped") or not mp4.exists()
                    or not (again.get("meta") or {}).get("title")):
                break
            made, meta = again, again["meta"]
            row.update(title=meta["title"], hook=made.get("hook"),
                       ledger=made.get("ledger"))
            gate = judge(mp4, c, meta, made.get("hook") or "",
                         will_upload=not a.dry_run)
        row["showrunner"] = {"blocked": gate["blocked"],
                             "reason": gate.get("reason"),
                             "score": (gate.get("verdict") or {})
                             .get("score")}
        if gate["blocked"]:
            row["skipped"] = f"showrunner_block: {gate.get('reason')}"
            continue
        if a.dry_run:
            row.update(ok=True, video_url="(dry-run)", file=mp4.name)
            shipped += 1
            continue

        rt._refresh_log_from_origin()
        publish_at = next_slot(slots, after=last_slot, log=rt.load_log())
        desc, tg = description(meta, c), tags(meta, c)

        def _do_upload():
            from shared.uploaders import YouTubeUploader
            up = YouTubeUploader(channel="").upload(
                file_path=mp4, title=meta["title"][:100], description=desc,
                tags=tg, publish_at=publish_at, category="17",
                # Real game footage, no AI voice or imagery: no label.
                synthetic_media=False)
            return getattr(up, "url", None) or str(up)
        try:
            row["video_url"] = rt._guarded_upload(
                title=meta["title"], topic=row["topic"], fmt=FORMAT,
                publish_at=publish_at, do_upload=_do_upload,
                extra={"songs": made.get("songs")})
        except rt.DuplicateUpload as e:
            row["skipped"] = f"duplicate: {e}"
            continue
        except rt.ClaimNotDurable as e:
            row["error"] = f"claim not durable: {e}"
            print(f"::error::{e}", flush=True)
            break
        except Exception as e:  # noqa: BLE001
            row["error"] = f"upload failed: {type(e).__name__}: {e}"[:300]
            print(f"::error::[sports] {row['error']}", flush=True)
            continue
        last_slot = publish_at
        row.update(ok=True, publish_at=publish_at,
                   seconds=round(time.time() - t0))
        shipped += 1
        print(f"[sports] POSTED {meta['title']!r} -> {row['video_url']} "
              f"(goes live {publish_at})", flush=True)
        try:
            from shared.crosspost import crosspost
            x = crosspost(CHANNEL, mp4, meta["title"][:100], desc, tg,
                          publish_at=publish_at)
            if x:
                row["crossposts"] = x
        except Exception as e:  # noqa: BLE001
            print(f"[sports] crosspost skipped: {e}", flush=True)
        _save()

    report["shipped"] = shipped
    _save()
    print(f"[sports] shipped {shipped}/{need}", flush=True)
    for r in report["slots"]:
        print(f"  {'OK  ' if r.get('ok') else 'SKIP'} r/{r['sub']} "
              f"{r['who']}: {r.get('title') or r['post_title'][:60]!r} "
              f"{r.get('skipped') or r.get('error') or ''}", flush=True)
    return 0 if shipped else 1


if __name__ == "__main__":
    sys.exit(main())
