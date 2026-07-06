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


# Pre-render illustration gate. A package whose shots mostly fall to bare
# keyword stock (no real image_url, no fundable named entity) is the one
# that ships off-topic imagery — a serval beat showing a leopard, a
# "conservation officers" beat showing fishermen. We quarantine it BEFORE
# burning render time, ship the rest of the slate, and report it so the
# author can pin real photos. Tunable without a code change via the env
# var; set to 0 to disable. This complements the render-time
# RelevanceGateError in make_explainer_stacked (which judges the ACTUAL
# resolved media post-render) — this one is the cheap pre-flight.
MIN_ILLUSTRATION_PCT = float(os.environ.get("MIN_ILLUSTRATION_PCT", "20"))


def _illustration_quarantine(pkg: dict) -> str | None:
    """Return a human-readable quarantine reason if this package's
    illustration coverage is below MIN_ILLUSTRATION_PCT, else None.

    Best-effort: any failure in the validator (no LLM key, network out,
    bad JSON) returns None so a flaky validator never blocks a render —
    the render-time relevance gate is the backstop."""
    if MIN_ILLUSTRATION_PCT <= 0:
        return None
    try:
        import entity_media
        report = entity_media.validate_package(pkg)
    except Exception as e:  # noqa: BLE001
        print(f"[quarantine] validator error, allowing render: "
              f"{type(e).__name__}: {str(e)[:80]}", flush=True)
        return None
    illus = report.get("illustration_pct", 100.0)
    if illus >= MIN_ILLUSTRATION_PCT:
        return None
    bad = report.get("keyword_only_shots", [])
    return (f"illustration coverage {illus}% < {MIN_ILLUSTRATION_PCT}% — "
            f"{len(bad)} shot(s) have no real image and would fall to "
            f"off-topic keyword stock: {bad}")


# Baseline reach hashtags appended to every short. Package-specific
# topical hashtags come from the routine (pkg['hashtags']) and rank
# higher in the final list — these are the always-on reach tags that
# fill out the description.
BASELINE_HASHTAGS = [
    "shorts", "news", "explainer", "trending", "viral", "fyp",
    "didyouknow", "breakingnews", "factsdaily", "shortsfeed",
]


def _hashtag_list(pkg: dict, max_total: int = 25) -> list[str]:
    """Merge package hashtags (topical, written by the routine) with
    the baseline reach set. Dedupes case-insensitively and keeps the
    topical ones in front — algos weight the first few hardest."""
    out: list[str] = []
    seen: set[str] = set()
    pkg_tags = pkg.get("hashtags") or []
    # Routine writes hashtags as bare words OR with leading '#' — accept both.
    for t in list(pkg_tags) + BASELINE_HASHTAGS:
        clean = (t or "").strip().lstrip("#").replace(" ", "")
        if not clean:
            continue
        k = clean.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(clean)
        if len(out) >= max_total:
            break
    return out


def _description(pkg: dict, angle: str | None = None) -> str:
    parts = [pkg.get("script", "").strip()]
    if angle:
        parts.append("")
        parts.append(angle)
    tags = _hashtag_list(pkg)
    parts.append("")
    parts.append(" ".join(f"#{t}" for t in tags))
    return "\n".join(parts)[:5000]


def _tags(pkg: dict) -> list[str]:
    """YouTube tags field (15 max in practice). Topical first, baseline
    fills the rest."""
    return _hashtag_list(pkg, max_total=15)


# --------------------------------------------------------------------------- #
# Gemini assists (image backfill, thumbnail, vision QA). All best-effort:
# they no-op without GEMINI_API_KEY and never raise into render/upload.
# --------------------------------------------------------------------------- #
def _img_prompt(pkg: dict, shot: dict | None) -> str:
    """Build an image-gen prompt from the story + (optional) shot beat."""
    title = (pkg.get("title") or pkg.get("topic") or "").strip()
    if shot is None:
        return f"Editorial news photo for a story titled: {title}."
    phrase = (shot.get("phrase") or "").strip()
    query = (shot.get("query") or "").strip()
    bits = [b for b in (phrase, query, f"Story: {title}") if b]
    return "Editorial news photo illustrating: " + ". ".join(bits) + "."


def _backfill_illustrations(pkg: dict) -> None:
    """Feature 2: for beats that would fall to off-topic keyword stock,
    generate an on-topic image (Pollinations.ai, free + keyless) and pin it
    as the shot's image_url (the renderer accepts local image paths). Lifts
    illustration coverage so a good story isn't quarantined for thin
    imagery. Best-effort — no-ops if generation/network is unavailable."""
    try:
        import gemini_images
        import entity_media
    except Exception:  # noqa: BLE001
        return
    try:
        keyword_only = set(entity_media.validate_package(pkg)
                           .get("keyword_only_shots") or [])
    except Exception:  # noqa: BLE001
        return
    if not keyword_only:
        return
    outdir = OUTPUT_DIR / "gen_images"
    # Cap generations per package: each call can wait out a slow Pollinations
    # response, so bound the time cost (a render-time budget, not a money one).
    MAX_GEN = int(os.environ.get("MAX_GEN_IMAGES", "3"))
    n = 0
    for s in pkg.get("shots") or []:
        if n >= MAX_GEN:
            break
        if s.get("image_url"):
            continue
        phrase = s.get("phrase") or ""
        # validate_package stores the phrase truncated to 50 chars.
        if phrase[:50] not in keyword_only:
            continue
        dest = outdir / f"{_slug(phrase)}_{n}.png"
        got = gemini_images.generate_image(_img_prompt(pkg, s), dest,
                                           width=1080, height=1080)
        if got:
            s["image_url"] = str(got)
            n += 1
    if n:
        print(f"[backfill] pinned {n} generated image(s) for thin beats",
              flush=True)


def _sample_frames(video: Path, n: int = 3) -> list[str]:
    """Extract up to n evenly-spaced JPEG frames from the video for QA."""
    import subprocess
    frames: list[str] = []
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", str(video)],
            capture_output=True, text=True, timeout=30)
        dur = float((out.stdout or "0").strip() or 0) or 30.0
    except Exception:  # noqa: BLE001
        dur = 30.0
    fdir = OUTPUT_DIR / "qa_frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        ts = dur * i / (n + 1)
        fp = fdir / f"{video.stem}_qa{i}.jpg"
        try:
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", str(video),
                 "-frames:v", "1", "-q:v", "3", str(fp)],
                capture_output=True, timeout=60)
            if fp.exists():
                frames.append(str(fp))
        except Exception:  # noqa: BLE001
            continue
    return frames


def _qa_and_thumbnail(pkg: dict, out_path: Path, result: dict) -> tuple[str | None, str | None]:
    """Features 1 + 3. Returns (thumbnail_path_or_None, qa_block_reason_or_None).
    A non-None block reason means vision QA flagged the video as
    broken/unsafe and the caller should skip the upload."""
    block: str | None = None
    thumb: str | None = None
    try:
        import gemini_images
    except Exception:  # noqa: BLE001
        return None, None
    # Feature 3 — vision QA (blocks only broken/unsafe; fail-open).
    try:
        verdict = gemini_images.vision_judge(
            _sample_frames(out_path), topic=result.get("topic", ""),
            title=result.get("title") or "")
        result["qa"] = verdict
        if not verdict.get("ok"):
            block = f"vision QA: {verdict.get('verdict')} — {verdict.get('reason')}"
    except Exception as e:  # noqa: BLE001
        print(f"[qa] skipped: {type(e).__name__}: {e}", flush=True)
    # Feature 1 — custom thumbnail (best pinned image as bg, hook overlaid).
    try:
        bg = next((s.get("image_url") for s in (pkg.get("shots") or [])
                   if s.get("image_url")), None)
        hook = (pkg.get("script") or "").split("?")[0].split("!")[0][:60]
        tp = OUTPUT_DIR / f"{out_path.stem}_thumb.jpg"
        made = gemini_images.build_thumbnail(
            tp, title=result.get("title") or pkg.get("title") or "",
            hook=hook, bg_image=bg, bg_prompt=_img_prompt(pkg, None))
        if made:
            thumb = str(made)
    except Exception as e:  # noqa: BLE001
        print(f"[thumb] skipped: {type(e).__name__}: {e}", flush=True)
    return thumb, block


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
            if p.name.startswith("_"):
                continue  # _schedule.json etc. are config, not packages
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
    # Feature 2: backfill thin beats with generated imagery so a good
    # story isn't quarantined for stock-only shots (no-op without a key).
    _backfill_illustrations(pkg)
    # Pre-render illustration gate. Quarantine (don't render) a package
    # that would ship off-topic stock; the batch continues without it.
    reason = _illustration_quarantine(pkg)
    if reason is not None:
        result["error"] = f"quarantined: {reason}"
        result["quarantined"] = True
        result["elapsed_seconds"] = round(time.time() - t_start, 1)
        print(f"[{result['topic']!r}] QUARANTINED — {reason}", flush=True)
        return result
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

        # Features 1 + 3: custom thumbnail + vision QA on the finished mp4.
        thumb, qa_block = _qa_and_thumbnail(pkg, out_path, result)
        if qa_block:
            result["error"] = f"quarantined: {qa_block}"
            result["quarantined"] = True
            print(f"[{result['topic']!r}] QUARANTINED — {qa_block}", flush=True)
            return result

        if dry_run:
            result["ok"] = True
            result["video_url"] = "(dry-run)"
        else:
            from uploaders import YouTubeUploader
            # `channel` selects which YOUTUBE_TOKEN_JSON_* secret the
            # uploader reads. Empty/missing → baller_bro_2_0 (the
            # original `YOUTUBE_TOKEN_JSON`). Set on the package by
            # the morning routine to route to a different channel.
            channel = (pkg.get("channel") or "").strip().lower()
            result["channel"] = channel or "default"
            print(f"[{result['topic']!r}] uploading to "
                  f"{result['channel']}...", flush=True)
            uploader = YouTubeUploader(channel=channel)
            upload_result = uploader.upload(
                file_path=out_path,
                title=(result["title"] or result["topic"])[:100],
                description=_description(pkg),
                tags=_tags(pkg),
                publish_at=None if no_schedule else publish_at,
                thumbnail=thumb,
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

        # 1b. Backfill thin beats, then the pre-render illustration gate.
        _backfill_illustrations(pkg)
        reason = _illustration_quarantine(pkg)
        if reason is not None:
            result["error"] = f"quarantined: {reason}"
            result["quarantined"] = True
            result["elapsed_seconds"] = round(time.time() - t_start, 1)
            print(f"[{topic.query!r}] QUARANTINED — {reason}", flush=True)
            return result

        # 2. Render to mp4.
        out_path = OUTPUT_DIR / f"daily_{ts}_{slug}.mp4"
        print(f"[{topic.query!r}] rendering -> {out_path}", flush=True)
        make_explainer_stacked.build_from_package(pkg, out_path)
        result["video_path"] = str(out_path.relative_to(REPO))

        # Features 1 + 3: custom thumbnail + vision QA on the finished mp4.
        thumb, qa_block = _qa_and_thumbnail(pkg, out_path, result)
        if qa_block:
            result["error"] = f"quarantined: {qa_block}"
            result["quarantined"] = True
            print(f"[{topic.query!r}] QUARANTINED — {qa_block}", flush=True)
            return result

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
                thumbnail=thumb,
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
    quarantined = [r for r in results if r.get("quarantined")]
    failed = [r for r in results if not r["ok"] and not r.get("quarantined")]
    lines = [
        f"# Daily Trending Shorts — {date_str}",
        "",
        f"- queued: **{len(results)}**",
        f"- succeeded: **{len(success)}**",
        f"- quarantined (off-topic imagery): **{len(quarantined)}**",
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
    if quarantined:
        lines.append("## Quarantined (off-topic imagery — fix & re-author)")
        for r in quarantined:
            lines.append(f"- **{r['topic']}**")
            if r.get("error"):
                lines.append(f"  - {r['error']}")
        lines.append("")
    if failed:
        lines.append("## Failed")
        for r in failed:
            lines.append(f"- **{r['topic']}**")
            if r.get("error"):
                lines.append(f"  - error: `{r['error']}`")
        lines.append("")
    return "\n".join(lines)


def _assign_bottom_diversity(pkgs: list[dict]) -> None:
    """Spread the bottom across the batch so it isn't the same clip six
    times. DEFAULT bottom is real gameplay footage: round-robin a distinct
    `_gameplay_tag` per video across the seeded gameplay pool. A package can
    still opt into the procedural engine (bottom_style: procedural); those
    keep the old relevant-theme diversity. Mutates pkgs in place."""
    try:
        import make_explainer_stacked as mes
        import themed_bottom
    except Exception:  # noqa: BLE001
        return
    tags = mes._seeded_gameplay_tags() or list(mes.GAMEPLAY_TAGS)
    gi = 0
    used_theme: dict[str, int] = {}
    used_tag: dict[str, int] = {}
    for i, p in enumerate(pkgs):
        p["_theme_seed"] = f"{p.get('slug') or p.get('title', '')}-{i}"
        style = (p.get("bottom_style") or "gameplay").strip().lower()
        if style == "procedural":
            explicit = (p.get("bottom_theme") or "").strip().lower()
            if explicit and explicit != "auto":
                choice = explicit
            else:
                ranked = themed_bottom.smart_rank(
                    p.get("title", ""), p.get("script", ""), p.get("hashtags"))
                choice = (min(ranked, key=lambda th: (used_theme.get(th, 0),
                                                      ranked.index(th)))
                          if ranked else "plinko")
            used_theme[choice] = used_theme.get(choice, 0) + 1
            p["bottom_theme"] = choice
        else:
            # Round-robin the gameplay pool for maximum spread across a batch.
            tag = tags[gi % len(tags)]
            gi += 1
            used_tag[tag] = used_tag.get(tag, 0) + 1
            p["_gameplay_tag"] = tag
    print(f"[bottom] gameplay tags: {dict(used_tag)}"
          + (f" | procedural: {dict(used_theme)}" if used_theme else ""),
          flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6,
                    help="how many shorts to produce + post")
    ap.add_argument("--dry-run", action="store_true",
                    help="render but don't upload")
    ap.add_argument("--only", default="",
                    help="render only packages whose slug/path/title contains "
                         "this substring (case-insensitive) — e.g. --only "
                         "wellington to preview one specific package")
    ap.add_argument("--no-schedule", action="store_true",
                    help="upload immediately instead of scheduling slots")
    ap.add_argument("--top-k-buffer", type=int, default=3,
                    help="ask the ranker for N+buffer picks so failures "
                         "don't drop us below count (LLM fallback only)")
    ap.add_argument("--force-llm", action="store_true",
                    help="ignore pre-written packages, force Groq fallback")
    ap.add_argument("--force-rerun", action="store_true",
                    help="bypass the 6-hour duplicate-trigger guard. Use when "
                         "you want to re-publish a fresh package slate the "
                         "same day (e.g. the morning batch was bad and you "
                         "just swapped in new packages).")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Skip if we already posted in the last 6 hours. Multiple triggers
    # can fire daily.yml in quick succession (workflow_run from auto-
    # merge AND push-paths AND manual dispatch) — without this guard
    # we'd double-post the same packages. Using a 6-hour rolling window
    # instead of "today" handles the edge case where yesterday's batch
    # logged itself just after midnight UTC and today's intended run
    # would get blocked all day.
    if not args.dry_run:
        log = load_log()
        now_dt = datetime.now(timezone.utc)
        cutoff = now_dt - timedelta(hours=6)
        recent = []
        for e in log.get("posted", []):
            ts = e.get("posted_at") or ""
            try:
                posted_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if posted_dt > cutoff:
                recent.append(e)
        if recent and not (args.force_llm or args.force_rerun):
            print(f"[run_trending_daily] {len(recent)} short(s) posted in the "
                  f"last 6 hours; skipping. Use --force-rerun (or "
                  f"--force-llm) to override.",
                  flush=True)
            today_str = now_dt.strftime("%Y-%m-%d")
            REPORT_PATH.write_text(
                f"# Daily Trending Shorts — {today_str}\n\n"
                f"Already posted {len(recent)} short(s) in the last 6 hours; "
                f"skipped duplicate trigger.\n"
            )
            REPORT_JSON.write_text(json.dumps({"skipped": True,
                                                "recent_posts": len(recent)},
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
    if prewritten and args.only:
        needle = args.only.lower()
        prewritten = [
            p for p in prewritten
            if needle in (p.get("_path", "") + " " + p.get("slug", "")
                          + " " + p.get("title", "")).lower()
        ]
        print(f"=== --only {args.only!r}: {len(prewritten)} package(s) match ===",
              flush=True)
    if prewritten:
        rel = src_dir.relative_to(REPO) if src_dir else "(unknown)"
        print(f"=== using {len(prewritten)} pre-written packages from "
              f"{rel} ===", flush=True)
        # Tailor + diversify the bottom games across the batch (>=2 distinct
        # per 3; a distinct reskin seed per video).
        _assign_bottom_diversity(prewritten)
        # Optional per-day schedule override: state/.../_schedule.json with
        # {"per_slot": N} places N videos at each default time slot (e.g.
        # 2 means two posts share each 2-hour slot). Defaults to 1.
        per_slot = 1
        if src_dir is not None and (src_dir / "_schedule.json").exists():
            try:
                cfg = json.loads((src_dir / "_schedule.json").read_text())
                per_slot = max(1, int(cfg.get("per_slot", 1)))
                print(f"[schedule] override: {per_slot} video(s) per slot",
                      flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[schedule] bad _schedule.json ignored: {e}", flush=True)
        import math
        eff = min(args.count, len(prewritten))
        sched = schedule_times(
            now, max(1, math.ceil(eff / per_slot)), DEFAULT_PUBLISH_HOURS_UTC)
        results: list[dict] = []
        sched_idx = 0
        for pkg in prewritten[:args.count]:
            slot = sched_idx // per_slot
            publish_at = sched[slot] if slot < len(sched) else None
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

    # Exit non-zero if anything genuinely FAILED so the workflow's
    # failure counter bumps and we get a real notification. A
    # quarantine is an intentional skip (off-topic imagery), not a
    # crash — it must NOT bump the auto-pause counter, or a few
    # un-illustratable packages would silence the whole pipeline.
    quarantined = [r for r in results if r.get("quarantined")]
    failed = [r for r in results if not r["ok"] and not r.get("quarantined")]
    if quarantined:
        print(f"[run_trending_daily] {len(quarantined)} package(s) "
              f"quarantined for off-topic imagery (slate shipped without "
              f"them)", file=sys.stderr)
    if failed:
        print(f"[run_trending_daily] {len(failed)} of {len(results)} failed",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
