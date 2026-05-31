#!/usr/bin/env python3
"""Daily orchestrator for the trending-shorts pipeline.

Two source-of-truth modes, checked in order:

  PRE-WRITTEN PACKAGES (preferred — hand-authored quality)
    If state/trending_packages/YYYYMMDD/ contains JSON packages, use
    those directly. This is the path when a scheduled Claude Code
    session has written the day's scripts in advance (recommended
    setup — much better script quality than the LLM fallback).

  GROQ FALLBACK (safety net)
    If no pre-written packages for today, run discovery + Groq ranker
    + Groq script generation. Lower quality but the day still ships.

Common path for each package:
  make_explainer_stacked.build_from_package() renders the 1080x1920
  short. uploaders.YouTubeUploader.upload() schedules each post at a
  different hour-slot so the day's 6 spread across 9am-7pm EDT.

Outputs daily_report.md (committed by the GH Action), daily_report.json
(machine-readable summary), updates state/posted_log.json.

Env:
  PEXELS_API_KEY + PIXABAY_API_KEY  (required, for stock B-roll)
  YOUTUBE_CLIENT_SECRETS_JSON + YOUTUBE_TOKEN_JSON  (required for upload)
  GROQ_API_KEY  (only required for the fallback path)
  KOKORO_VOICE  (optional voice override)

Flags:
  --count N        number of shorts to produce (default 6)
  --dry-run        render but don't upload — useful for testing
  --no-schedule    upload public immediately instead of scheduling slots
  --force-llm      ignore pre-written packages, use Groq fallback
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from scripts.discover_topic import discover_all  # noqa: E402
from scripts import rank_topics  # noqa: E402
import script_generator  # noqa: E402
import make_explainer_stacked  # noqa: E402

STATE_DIR = REPO / "state"
OUTPUT_DIR = REPO / "output"
PACKAGE_DIR = STATE_DIR / "trending_packages"
LOG_PATH = STATE_DIR / "posted_log.json"
REPORT_PATH = REPO / "daily_report.md"
REPORT_JSON = REPO / "daily_report.json"

# 6 publish slots in UTC. Maps to 9am, 11am, 1pm, 3pm, 5pm, 7pm EDT
# (UTC-4). The action fires at 12 UTC = 8am EDT so the first slot is
# +1hr and the rest spread through the workday.
DEFAULT_PUBLISH_HOURS_UTC = [13, 15, 17, 19, 21, 23]


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


def schedule_times(now: datetime, n: int, hours: list[int]) -> list[str]:
    """Pick the next n hour-slots ≥5 min in the future, walking into
    tomorrow if needed. Returns ISO-8601 strings in UTC."""
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = now + timedelta(minutes=5)
    picks: list[datetime] = []
    for day_offset in range(3):
        for hour in hours:
            t = base + timedelta(days=day_offset, hours=hour)
            if t > cutoff:
                picks.append(t)
            if len(picks) >= n:
                break
        if len(picks) >= n:
            break
    return [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in picks[:n]]


def _slug(s: str, n: int = 40) -> str:
    return "".join(c if c.isalnum() else "_" for c in s.lower())[:n]


def _description(pkg: dict, angle: str | None = None) -> str:
    parts = [pkg.get("script", "").strip()]
    if angle:
        parts.append("")
        parts.append(angle)
    parts.append("")
    parts.append("#shorts #news #explainer")
    return "\n".join(parts)[:5000]


def _tags(pkg: dict) -> list[str]:
    topic = (pkg.get("topic") or "").lower()
    base = [w for w in topic.split() if len(w) > 2][:5]
    return base + ["shorts", "news", "explainer", "trending"]


def todays_package_dir() -> Path:
    """Where a scheduled Claude Code session is expected to drop the
    day's hand-written packages. Format: state/trending_packages/YYYYMMDD/."""
    return PACKAGE_DIR / datetime.now(timezone.utc).strftime("%Y%m%d")


def most_recent_package_dir() -> Path | None:
    """Find the most-recent YYYYMMDD/ directory. The routine fires
    daily but the orchestrator might run before or after midnight UTC
    relative to when packages were written — and if a routine misses a
    day, using yesterday's packages is much better than falling back
    to Groq (which rate-limits at 6K TPM on the free tier and blows
    up trying to write 6+ scripts back-to-back)."""
    if not PACKAGE_DIR.exists():
        return None
    candidates = [
        p for p in PACKAGE_DIR.iterdir()
        if p.is_dir() and len(p.name) == 8 and p.name.isdigit()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)


def load_prewritten_packages() -> tuple[Path | None, list[dict]]:
    """Return (source_dir, packages). Prefers today's dir; falls back
    to the most-recent YYYYMMDD/ on disk so a missing routine run
    doesn't force the expensive Groq fallback path."""
    candidates = [todays_package_dir(), most_recent_package_dir()]
    seen: set[Path] = set()
    for d in candidates:
        if d is None or d in seen or not d.exists():
            continue
        seen.add(d)
        pkgs: list[dict] = []
        for p in sorted(d.glob("*.json")):
            try:
                pkg = json.loads(p.read_text())
                pkg.setdefault("_path", str(p.relative_to(REPO)))
                pkgs.append(pkg)
            except json.JSONDecodeError as e:
                print(f"[run_trending_daily] skipping malformed {p.name}: {e}",
                      file=sys.stderr)
        if pkgs:
            return d, pkgs
    return None, []


def run_one_from_package(pkg: dict, publish_at: str | None, *,
                         dry_run: bool, no_schedule: bool) -> dict:
    """Render + upload a pre-written package. No script generation."""
    result: dict = {
        "topic": pkg.get("topic", pkg.get("title", "untitled")),
        "title": pkg.get("title"),
        "publish_at": publish_at,
        "ok": False,
        "video_url": None,
        "error": None,
        "elapsed_seconds": 0.0,
        "package_path": pkg.get("_path"),
    }
    t_start = time.time()
    # BaseException not Exception — catches SystemExit too, so a
    # rogue sys.exit() in any downstream module can't kill the whole
    # batch silently. KeyboardInterrupt still propagates (Ctrl-C in
    # local dev).
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        slug = _slug(result["topic"])
        out_path = OUTPUT_DIR / f"daily_{ts}_{slug}.mp4"
        print(f"[{result['topic']!r}] rendering -> {out_path}", flush=True)
        make_explainer_stacked.build_from_package(pkg, out_path)
        result["video_path"] = str(out_path.relative_to(REPO))

        if dry_run:
            result["ok"] = True
            result["video_url"] = "(dry-run)"
        else:
            from uploaders import YouTubeUploader
            print(f"[{result['topic']!r}] uploading...", flush=True)
            uploader = YouTubeUploader()
            upload_result = uploader.upload(
                file_path=out_path,
                title=(result["title"] or result["topic"])[:100],
                description=_description(pkg),
                tags=_tags(pkg),
                publish_at=None if no_schedule else publish_at,
            )
            result["video_url"] = (
                getattr(upload_result, "url", None) or str(upload_result)
            )
            result["ok"] = True
    except KeyboardInterrupt:
        raise
    except BaseException as e:  # noqa: BLE001
        import traceback
        result["error"] = f"{type(e).__name__}: {e}"
        print(f"[{result['topic']!r}] FAILED: {result['error']}", flush=True)
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
    finally:
        result["elapsed_seconds"] = round(time.time() - t_start, 1)
    return result


def run_one(topic, publish_at: str | None, *, dry_run: bool,
            no_schedule: bool) -> dict:
    """Generate + render + upload a single short. Catches per-step
    failures so one bad topic doesn't tank the whole batch."""
    result: dict = {
        "topic": topic.query,
        "angle": topic.angle,
        "publish_at": publish_at,
        "ok": False,
        "video_url": None,
        "error": None,
        "elapsed_seconds": 0.0,
    }
    t_start = time.time()

    try:
        # 1. Groq writes the script package (with validation + retry).
        print(f"[{topic.query!r}] generating script...", flush=True)
        pkg = script_generator.generate(
            topic.query, topic.headlines, topic.snippets, backend="groq",
        )

        # Save the package alongside so we can re-render or audit later.
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        slug = _slug(topic.query)
        PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
        pkg_path = PACKAGE_DIR / f"{ts}_auto_{slug}.json"
        pkg_path.write_text(json.dumps(pkg, indent=2))
        result["title"] = pkg.get("title", topic.query)
        result["package_path"] = str(pkg_path.relative_to(REPO))

        # 2. Render to mp4.
        out_path = OUTPUT_DIR / f"daily_{ts}_{slug}.mp4"
        print(f"[{topic.query!r}] rendering -> {out_path}", flush=True)
        make_explainer_stacked.build_from_package(pkg, out_path)
        result["video_path"] = str(out_path.relative_to(REPO))

        # 3. Upload (unless dry-run).
        if dry_run:
            result["ok"] = True
            result["video_url"] = "(dry-run)"
        else:
            from uploaders import YouTubeUploader
            print(f"[{topic.query!r}] uploading...", flush=True)
            uploader = YouTubeUploader()
            upload_result = uploader.upload(
                file_path=out_path,
                title=result["title"][:100],
                description=_description(pkg, topic.angle),
                tags=_tags(pkg),
                publish_at=None if no_schedule else publish_at,
            )
            # uploaders return an UploadResult with .url; tolerate either
            # an object or a plain string for forward compat.
            result["video_url"] = (
                getattr(upload_result, "url", None) or str(upload_result)
            )
            result["ok"] = True
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
        print(f"[{topic.query!r}] FAILED: {result['error']}", flush=True)
    finally:
        result["elapsed_seconds"] = round(time.time() - t_start, 1)
    return result


def format_report(date_str: str, results: list[dict]) -> str:
    success = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    lines = [
        f"# Daily Trending Shorts — {date_str}",
        "",
        f"- queued: **{len(results)}**",
        f"- succeeded: **{len(success)}**",
        f"- failed: **{len(failed)}**",
        "",
    ]
    if success:
        lines.append("## Posted")
        for r in success:
            lines.append(f"- **{r.get('title', r['topic'])}**")
            lines.append(f"  - topic: {r['topic']}")
            if r.get("angle"):
                lines.append(f"  - angle: {r['angle']}")
            if r.get("publish_at"):
                lines.append(f"  - publishes: `{r['publish_at']}`")
            if r.get("video_url"):
                lines.append(f"  - {r['video_url']}")
            lines.append(f"  - took: {r['elapsed_seconds']}s")
        lines.append("")
    if failed:
        lines.append("## Failed")
        for r in failed:
            lines.append(f"- **{r['topic']}**")
            if r.get("error"):
                lines.append(f"  - error: `{r['error']}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6,
                    help="how many shorts to produce + post")
    ap.add_argument("--dry-run", action="store_true",
                    help="render but don't upload")
    ap.add_argument("--no-schedule", action="store_true",
                    help="upload immediately instead of scheduling slots")
    ap.add_argument("--top-k-buffer", type=int, default=3,
                    help="ask the ranker for N+buffer picks so failures "
                         "don't drop us below count (LLM fallback only)")
    ap.add_argument("--force-llm", action="store_true",
                    help="ignore pre-written packages, force Groq fallback")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Skip if we already posted today. Multiple triggers can fire
    # daily.yml in quick succession (workflow_run from auto-merge AND
    # push-paths AND manual dispatch) — without this guard we'd
    # double-post the same packages. We DON'T skip for dry runs since
    # those don't get logged.
    if not args.dry_run:
        log = load_log()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        already = [e for e in log.get("posted", [])
                   if (e.get("posted_at") or "").startswith(today)]
        if already and not args.force_llm:
            print(f"[run_trending_daily] already posted {len(already)} short(s) "
                  f"today ({today}); skipping. Use --force-llm to override.",
                  flush=True)
            # Still write an "empty" report so the commit step doesn't
            # confuse old + new state.
            REPORT_PATH.write_text(
                f"# Daily Trending Shorts — {today}\n\n"
                f"Already posted {len(already)} short(s) earlier today; "
                f"skipped duplicate trigger.\n"
            )
            REPORT_JSON.write_text(json.dumps({"skipped": True,
                                                "already_posted": len(already)},
                                               indent=2))
            return 0

    # Preflight log. If any of these are unexpected (no gameplay clips
    # at all, missing kokoro models, no packages today), they show up
    # at the top of the orchestrator log instead of being inferred from
    # a cryptic mid-render exit later.
    gameplay_dir = REPO / "gameplay"
    gameplay_files = (
        sorted(p.name for p in gameplay_dir.iterdir())
        if gameplay_dir.exists() else []
    )
    print(f"[preflight] gameplay/ contains: {gameplay_files}", flush=True)
    print(f"[preflight] today's package dir: "
          f"{todays_package_dir().relative_to(REPO)}", flush=True)
    if todays_package_dir().exists():
        pkg_files = sorted(p.name for p in todays_package_dir().iterdir())
        print(f"[preflight] today's packages: {pkg_files}", flush=True)

    now = datetime.now(timezone.utc)
    sched = schedule_times(now, args.count, DEFAULT_PUBLISH_HOURS_UTC)

    # Path A: pre-written packages dropped by a scheduled Claude Code
    # session. Render + upload directly, no LLM script generation. If
    # today's dir is missing (routine hasn't fired yet) we fall back
    # to the most recent day's packages — far better than burning
    # through Groq's free tier on emergency script generation.
    src_dir, prewritten = (None, []) if args.force_llm else load_prewritten_packages()
    if prewritten:
        rel = src_dir.relative_to(REPO) if src_dir else "(unknown)"
        print(f"=== using {len(prewritten)} pre-written packages from "
              f"{rel} ===", flush=True)
        results: list[dict] = []
        sched_idx = 0
        for pkg in prewritten[:args.count]:
            publish_at = sched[sched_idx] if sched_idx < len(sched) else None
            result = run_one_from_package(
                pkg, publish_at,
                dry_run=args.dry_run, no_schedule=args.no_schedule,
            )
            results.append(result)
            if result["ok"]:
                sched_idx += 1
    else:
        # Path B (fallback): no pre-written packages, run Groq end-to-end.
        if not os.environ.get("GROQ_API_KEY"):
            print("[run_trending_daily] no pre-written packages for today "
                  f"({todays_package_dir().relative_to(REPO)}) and no "
                  "GROQ_API_KEY for fallback", file=sys.stderr)
            return 2

        print("=== no pre-written packages — Groq fallback ===", flush=True)
        print("=== discovery ===", flush=True)
        raw = discover_all()
        print(f"=== ranking {len(raw)} raw candidates ===", flush=True)
        picks = rank_topics.rank(raw, top_k=args.count + args.top_k_buffer)
        print(f"=== Groq picked {len(picks)} candidates ===", flush=True)
        for i, t in enumerate(picks, 1):
            print(f"  {i}. [{t.score:>4.1f}] {t.query[:90]}", flush=True)
            if t.angle:
                print(f"      angle: {t.angle}", flush=True)

        results = []
        sched_idx = 0
        for topic in picks:
            if len([r for r in results if r["ok"]]) >= args.count:
                break
            publish_at = sched[sched_idx] if sched_idx < len(sched) else None
            result = run_one(
                topic, publish_at,
                dry_run=args.dry_run, no_schedule=args.no_schedule,
            )
            results.append(result)
            if result["ok"]:
                sched_idx += 1

    # 4. Update posted log with successful uploads.
    log = load_log()
    for r in results:
        if r["ok"] and not args.dry_run:
            log["posted"].append({
                "topic": r["topic"],
                "title": r.get("title"),
                "video_url": r["video_url"],
                "publish_at": r.get("publish_at"),
                "posted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
    save_log(log)

    # 5. Write report.
    date_str = now.strftime("%Y-%m-%d")
    REPORT_PATH.write_text(format_report(date_str, results) + "\n")
    REPORT_JSON.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n=== wrote {REPORT_PATH.name} + {REPORT_JSON.name} ===")

    # Exit non-zero if anything failed so the workflow's failure
    # counter bumps and we get a real notification.
    failed = [r for r in results if not r["ok"]]
    if failed:
        print(f"[run_trending_daily] {len(failed)} of {len(results)} failed",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
