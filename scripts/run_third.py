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


def _merged_tags(pkg: dict, led: dict) -> list[str]:
    tags = list(led.get("authored_tags") or []) + \
        list(pkg.get("hashtags") or [])
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:14]   # YouTube discards ALL hashtags past 15


def _description(pkg: dict, led: dict) -> str:
    tags = " ".join(f"#{t}" for t in _merged_tags(pkg, led))
    note = pkg.get("description_note", "")
    if led.get("kind") == "twitch_clip":
        detail = (f"Clip from {led['credit']} — full credit "
                  f"to the streamer. Source: {led['source_url']}\n"
                  f"Clipped by {led['clipper']}.")
    elif led.get("kind") == "sim":
        detail = (f"Simulation: {led['theme']}, one continuous speed ramp "
                  f"to x{led['peak_multiplier']} — the on-screen speed "
                  "counter is the sim's actual clock multiplier.")
    else:
        detail = (f"Measured: {led['wall_time_s']:.2f}s wall time, "
                  f"{led['files']['input']['rows']} rows in, "
                  f"{led['files']['output']['rows']} rows out.")
    return f"{pkg['proof_plan']}\n\n{note}\n\n{detail}\n\n{tags}"


def process(pkg_path: Path, *, dry_run: bool, publish_at, log: dict) -> dict:
    pkg = json.loads(pkg_path.read_text())
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
                # min_views gates only candidates that report views.
                cands = [c for c in cands
                         if c["url"] not in posted_urls
                         and (c["views"] == 0
                              or c["views"] >= spec.get("min_views", 2000))]
                cands.sort(key=lambda c: -c["views"])
                if not cands:
                    raise RuntimeError("no fresh clip across the allowlist")
                # viral signal = velocity, not raw views: probe ages for
                # the top of the board and re-rank by views/hour
                shortlist = cands[:8]
                for c in shortlist:
                    age = clip_edit.fetch_age_hours(c["url"])
                    c["vph"] = c["views"] / max(age, 0.5) if age else \
                        c["views"] / 24.0
                shortlist.sort(key=lambda c: -c["vph"])
                for c in shortlist[:5]:
                    print(f"[pick] {c['channel']:>14} {c['views']:>7}v "
                          f"{c['vph']:>8.0f}v/h  {c['title'][:50]!r}",
                          flush=True)
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
            composer.compose(pkg_path, ledger_path, out_mp4)
        result["video_path"] = str(out_mp4.relative_to(REPO))
        result["ledger"] = str(ledger_path.relative_to(REPO))
        title = pkg["title"].format(**_fmt_from_ledger(led))[:100]
        result["title"] = title
        if dry_run:
            result.update(ok=True, video_url="(dry-run)")
            if led.get("kind") == "twitch_clip":
                # in-memory only (never saved): keeps the next package in
                # this run from picking the same clip
                log["posted"][slug] = {"source_url": led["source_url"]}
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
                tags=_merged_tags(pkg, led),
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
    packages = sorted(day_dir.glob("*.json")) if day_dir.is_dir() else []
    if not packages:
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
    # uploaders.upload wants publish_at as an RFC3339 string, not datetime
    results = [process(p, dry_run=args.dry_run,
                       publish_at=((publish_base + timedelta(hours=2 * i))
                                   .strftime("%Y-%m-%dT%H:%M:%SZ")
                                   if publish_base else None),
                       log=log)
               for i, p in enumerate(packages)]
    print(json.dumps(results, indent=2))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
