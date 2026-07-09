#!/usr/bin/env python3
"""Proof Mode ("third" channel) orchestrator: capture -> compose -> upload.

Fully isolated from the shared trending/explainer pipelines
(THIRD_BRAIN.md §13): reads packages from state/third_packages/YYYYMMDD/,
logs to state/third_posted_log.json, uploads with channel="third" so the
uploader reads YOUTUBE_TOKEN_JSON_THIRD, and honors YOUTUBE_EXPECTED_CHANNEL.

Each package's `capture` block is EXECUTED for real (capture_cli) and the
resulting proof ledger drives every number the composer puts on screen.
If the capture fails (non-zero exit), the package is killed, not
improvised — THIRD_BRAIN.md §7.

Usage:
    python scripts/run_third.py --dry-run            # render only
    python scripts/run_third.py                      # render + upload
    python scripts/run_third.py --date 20260707
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from third_capture import capture_cli  # noqa: E402
from third_capture import compose as composer  # noqa: E402

PACKAGE_DIR = REPO / "state" / "third_packages"
LOG_PATH = REPO / "state" / "third_posted_log.json"
OUTPUT_DIR = REPO / "output"


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


def run_capture(pkg: dict, work: Path) -> Path:
    """Execute the package's real task and write the proof ledger."""
    spec = pkg["capture"]
    if spec["kind"] != "cli":
        raise RuntimeError(f"unsupported capture kind {spec['kind']!r}")
    if spec.get("fixture"):
        importlib.import_module(spec["fixture"]).main()
    inp = REPO / spec["input"]
    out = REPO / spec["output"]
    # Run from the fixture dir with basenames so the typed command and the
    # replayed output show the same short filenames (cosmetic only —
    # THIRD_BRAIN.md §7 allows path shortening, never command changes).
    argv = [a.format(input=inp.name, output=out.name)
            for a in spec["argv_template"]]
    cap = capture_cli.capture(argv, cwd=inp.parent,
                              shell_line=spec["shell_line"])
    if cap.exit_code != 0:
        raise RuntimeError(
            f"capture failed (exit {cap.exit_code}) — killing package, "
            "never improvising claims")
    capture_cli.record_file(cap, "input", inp)
    capture_cli.record_file(cap, "output", out)
    return capture_cli.save_ledger(cap, work / f"{pkg['slug']}.ledger.json")


def _fmt_from_ledger(led: dict) -> dict:
    if led.get("kind") == "twitch_clip":
        # the Groq author's title beats the raw clip title ("v", "W"...)
        return {"clip_title": led.get("authored_title") or led["clip_title"],
                "streamer": led["streamer"]}
    if led.get("kind") == "sim":
        return {"peak": f"{led['peak_multiplier']:.1f}"}
    n_in = led["files"]["input"]["rows"]
    n_out = led["files"]["output"]["rows"]
    return {"n_in": f"{n_in:,}", "n_out": f"{n_out:,}",
            "removed": f"{n_in - n_out:,}", "wall": f"{led['wall_time_s']:.2f}"}


def _hashtags(pkg: dict, led: dict) -> list[str]:
    """Description hashtags: 3-4, sparse and relevant (over-tagging
    reduces relevance; YouTube surfaces at most 3 by the title)."""
    tags = list(led.get("authored_tags") or []) or \
        list(pkg.get("hashtags") or [])
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:4]


def _yt_tags(pkg: dict, led: dict) -> list[str]:
    """The tags FIELD (not hashtags): sparse, mostly name variants —
    YouTube says tags play a minimal role beyond misspellings."""
    if led.get("kind") != "twitch_clip":
        return list(pkg.get("hashtags") or [])[:10]
    s = led["streamer"]
    return [s, f"{s} clips", f"{s} stream", "streamer clips",
            *(led.get("authored_tags") or [])][:10]


def _description(pkg: dict, led: dict) -> str:
    tags = " ".join(f"#{t}" for t in _hashtags(pkg, led))
    note = pkg.get("description_note", "")
    if led.get("kind") == "twitch_clip":
        # the public caption: one human sentence, credit, tags — never
        # internal pipeline jargon
        lead = led.get("authored_caption") \
            or led.get("authored_title") or led["clip_title"]
        credit = (f"Clip from {led['credit']} — full credit to the "
                  f"streamer.\nSource: {led['source_url']}\n"
                  f"Clipped by {led['clipper']}.")
        return f"{lead}\n\n{credit}\n\n{tags}"
    if led.get("kind") == "sim":
        detail = (f"Simulation: {led['theme']}, one continuous speed ramp "
                  f"to x{led['peak_multiplier']} — the on-screen speed "
                  "counter is the sim's actual clock multiplier.")
    else:
        detail = (f"Measured: {led['wall_time_s']:.2f}s wall time, "
                  f"{led['files']['input']['rows']} rows in, "
                  f"{led['files']['output']['rows']} rows out.")
    return f"{pkg['proof_plan']}\n\n{note}\n\n{detail}\n\n{tags}"


def process(pkg: dict, pkg_path: Path | None, *,
            dry_run: bool, publish_at, log: dict) -> dict:
    slug = pkg["slug"]
    result = {"slug": slug, "ok": False}
    if slug in log["posted"]:
        result.update(ok=True, skipped="already posted")
        return result
    work = OUTPUT_DIR / "third"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        out_mp4 = work / f"third_{slug}.mp4"
        if pkg["capture"]["kind"] == "twitch_clip":
            from third_capture import clip_edit
            spec = pkg["capture"]
            if spec.get("clip_url"):
                info = clip_edit.download(spec["clip_url"], work)
                platform = spec.get("platform", "twitch")
                streamer = spec["credit"]
            else:
                posted_urls = {v.get("source_url")
                               for v in log["posted"].values()}
                # sources: {"twitch": [...], "kick": [...], "rumble": [...]}
                # (legacy "channels" list = twitch). A platform that's
                # blocked/unreachable logs a warning and never kills the
                # run — the other platforms carry the day.
                sources = spec.get("sources") \
                    or {"twitch": spec.get("channels", [])}
                cands = []
                for platform, chans in sources.items():
                    for ch in chans:
                        try:
                            cands += clip_edit.discover(
                                platform, ch, top=spec.get("top", 8),
                                range_=spec.get("range", "24hr"))
                        except Exception as e:  # noqa: BLE001
                            print(f"::warning::discover {platform}:{ch} "
                                  f"failed ({type(e).__name__}) — skipped",
                                  flush=True)
                # views are comparable on twitch, best-effort elsewhere;
                # min_views gates only candidates that report views. On a
                # thin day, relax to the hard floor instead of losing the
                # slot — a 1.5k-view core-cluster clip still beats nothing.
                fresh = [c for c in cands if c["url"] not in posted_urls]
                # VARIETY (operator law): cap clips PER STREAMER per day
                # (default 2) and hard-limit 1 clip of the same EVENT per
                # day. The event cap is the important one — it stops one
                # hot moment (Streamer University) flooding every channel;
                # the streamer cap just trims monotony, so 2 is fine and
                # lets us actually fill the daily slate.
                per_streamer = spec.get("max_per_streamer", 2)
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                posted_today = [v for v in log["posted"].values()
                                if str(v.get("ts", "")).startswith(today)]
                from collections import Counter
                streamer_counts = Counter(v.get("streamer")
                                          for v in posted_today)
                used_titles = [str(v.get("title", "")).lower()
                               for v in posted_today]

                def _same_event(title: str) -> bool:
                    toks = {t for t in re.findall(r"[a-z]{5,}",
                                                  title.lower())}
                    return any(len(toks & set(re.findall(r"[a-z]{5,}", u)))
                               >= 2 for u in used_titles)

                varied = [c for c in fresh
                          if streamer_counts[c["channel"]] < per_streamer
                          and not _same_event(c["title"])]
                if varied:
                    fresh = varied
                else:
                    print("::warning::variety rules exhausted the pool — "
                          "allowing repeats", flush=True)
                min_v = spec.get("min_views", 2500)
                floor = spec.get("min_views_floor", 800)
                cands = [c for c in fresh
                         if c["views"] == 0 or c["views"] >= min_v]
                if not cands:
                    cands = [c for c in fresh if c["views"] >= floor]
                    if cands:
                        print(f"::warning::thin day — relaxed min_views "
                              f"{min_v} -> floor {floor}", flush=True)
                cands.sort(key=lambda c: -c["views"])
                if not cands:
                    raise RuntimeError("no fresh clip across the allowlist")
                # viral signal = velocity, not raw views: probe ages for
                # the top of the board and re-rank by views/hour, weighted
                # by franchise fit (core cluster > fallback supply)
                core = set(spec.get("core", []))
                shortlist = cands[:8]
                for c in shortlist:
                    # helix candidates carry exact age; yt-dlp ones probe
                    age = c.get("age_h") or clip_edit.fetch_age_hours(c["url"])
                    c["vph"] = c["views"] / max(age, 0.5) if age else \
                        c["views"] / 24.0
                    c["score"] = c["vph"] * \
                        (1.0 if not core or c["channel"] in core else 0.45)
                shortlist.sort(key=lambda c: -c["score"])
                for c in shortlist[:5]:
                    print(f"[pick] {c['channel']:>14} {c['views']:>7}v "
                          f"{c['vph']:>8.0f}v/h score={c['score']:>7.0f} "
                          f"{c['title'][:45]!r}", flush=True)
                pick = shortlist[0]
                info = clip_edit.download(pick["url"], work)
                platform, streamer = pick["platform"], pick["channel"]
            # transcribe once, then let the Groq author write the
            # packaging from what's actually said in the clip
            wmodel = spec.get("whisper_model", "small")
            has_cut = spec.get("start") or spec.get("end")
            words = None if has_cut else \
                clip_edit.transcribe_words(info["path"], wmodel)
            meta = None
            if words is not None:
                from third_capture import author
                meta = author.author_package(
                    streamer, info["title"],
                    " ".join(w["w"] for w in words), info["views"])
            hook = (meta or {}).get("hook") or pkg.get("hook", "")
            led = clip_edit.edit(
                info["path"], out_mp4,
                credit=clip_edit.credit_label(platform, streamer),
                hook=hook, words=words,
                start=spec.get("start", 0.0), end=spec.get("end", 0.0),
                whisper_model=wmodel)
            if meta:
                led["authored_title"] = meta["title"]
                led["authored_tags"] = meta["hashtags"]
                led["authored_caption"] = meta.get("caption", "")
                led["series"] = meta.get("series", "chaos")
            led["source_url"] = info["url"]
            led["source_views"] = info["views"]
            led["clip_title"] = info["title"]
            led["clipper"] = info["clipper"]
            led["streamer"] = streamer
            led["platform"] = platform
            ledger_path = work / f"{slug}.ledger.json"
            ledger_path.write_text(json.dumps(led, indent=2) + "\n")
        elif pkg["capture"]["kind"] == "sim":
            from third_capture import sim_video
            led = sim_video.compose_sim(pkg, out_mp4)
            ledger_path = work / f"{slug}.ledger.json"
            ledger_path.write_text(json.dumps(led, indent=2) + "\n")
        else:
            ledger_path = run_capture(pkg, work)
            led = json.loads(ledger_path.read_text())
            if pkg_path is None:
                raise RuntimeError("cli/sim packages must exist on disk")
            composer.compose(pkg_path, ledger_path, out_mp4)
        result["video_path"] = str(out_mp4.relative_to(REPO))
        result["ledger"] = str(ledger_path.relative_to(REPO))
        title = pkg["title"].format(**_fmt_from_ledger(led))[:100]
        result["title"] = title
        if dry_run:
            result.update(ok=True, video_url="(dry-run)")
            if led.get("kind") == "twitch_clip":
                # in-memory only (never saved): keeps the next package in
                # this run from re-picking the clip, streamer, or event
                log["posted"][slug] = {
                    "source_url": led["source_url"],
                    "streamer": led["streamer"],
                    "title": led.get("authored_title") or led["clip_title"],
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
        else:
            from uploaders import YouTubeUploader
            description = _description(pkg, led)
            # every language: extended locale set (clipper content is
            # visual-first, so localized metadata travels worldwide)
            localizations = None
            try:
                from localize import translate_metadata, ALL_LANGS
                localizations = translate_metadata(title, description,
                                                   langs=ALL_LANGS)
            except Exception as e:  # noqa: BLE001
                print(f"[localize] extended set skipped: {e}", flush=True)
            up = YouTubeUploader(channel="third").upload(
                file_path=out_mp4, title=title,
                description=description,
                tags=_yt_tags(pkg, led),
                publish_at=publish_at,
                localizations=localizations,
            )
            result.update(ok=True, video_url=getattr(up, "url", str(up)))
            entry = {
                "url": result["video_url"], "title": title,
                "kind": led.get("kind", "cli"),
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            if led.get("kind") == "twitch_clip":
                entry["source_url"] = led["source_url"]
                entry["streamer"] = led["streamer"]
            elif "files" in led:
                entry["ledger_sha_input"] = \
                    led["files"]["input"]["sha256"][:16]
            log["posted"][slug] = entry
            _save_log(log)
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
    result["took_s"] = round(time.time() - t0, 1)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc)
                    .strftime("%Y%m%d"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-schedule", action="store_true",
                    help="publish immediately instead of next 17:00 UTC slot")
    args = ap.parse_args()

    day_dir = PACKAGE_DIR / args.date
    paths = sorted(day_dir.glob("*.json")) if day_dir.is_dir() else []
    packages: list[tuple[dict, Path | None]] = \
        [(json.loads(p.read_text()), p) for p in paths]
    if not packages:
        # self-sufficient cron: synthesize the day's slate from the
        # default template so no one has to author packages daily
        template = PACKAGE_DIR / "default_clip.json"
        if template.exists():
            base = json.loads(template.read_text())
            n = int(base.pop("count", 3))
            for i in range(1, n + 1):
                pkg = json.loads(json.dumps(base))
                pkg["slug"] = f"clip-{args.date}-{i}"
                packages.append((pkg, None))
            print(f"no authored packages — synthesized {n} from template")
        else:
            print(f"no packages under {day_dir}")
            return 0
    publish_base = None
    if not args.no_schedule and not args.dry_run:
        now = datetime.now(timezone.utc)
        publish_base = now.replace(hour=17, minute=0, second=0,
                                   microsecond=0)
        # next slot at least 30 min out; extra packages 2h apart
        while publish_base < now + timedelta(minutes=30):
            publish_base += timedelta(hours=2)

    log = _load_log()
    # uploaders.upload wants publish_at as an RFC3339 string, not datetime.
    # Slot index only advances for packages that will actually post, so
    # already-posted slugs don't leave gaps in the schedule.
    results, slot = [], 0
    for pkg, path in packages:
        publish_at = None
        if publish_base and pkg["slug"] not in log["posted"]:
            publish_at = (publish_base + timedelta(hours=2 * slot)) \
                .strftime("%Y-%m-%dT%H:%M:%SZ")
            slot += 1
        results.append(process(pkg, path, dry_run=args.dry_run,
                               publish_at=publish_at, log=log))
    print(json.dumps(results, indent=2))
    # partial success is success: a late-day slot finding no fresh clip
    # must not fail the run (that skips the posted-log commit and desyncs
    # dedupe state). Fail only when NOTHING succeeded.
    return 0 if any(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
