#!/usr/bin/env python3
"""Daily run orchestrator.

Picks N catalog entries we haven't posted yet, stages them across the
workday, builds + uploads each via make_short.py, writes a posted log and
a markdown report.

Usage:
    python scripts/run_daily.py                # 6 posts, scheduled
    python scripts/run_daily.py --count 3      # fewer
    python scripts/run_daily.py --dry-run      # build but don't post
    python scripts/run_daily.py --no-schedule  # post immediately
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from catalog import CATALOG, by_id  # noqa: E402

STATE_DIR = REPO / "state"
LOG_PATH = STATE_DIR / "posted_log.json"
REPORT_PATH = REPO / "daily_report.md"
REPORT_JSON = REPO / "daily_report.json"

# 6 publish slots in UTC. Maps to 9am, 11am, 1pm, 3pm, 5pm, 7pm EDT (UTC-4)
# or 8am, 10am, noon, 2pm, 4pm, 6pm EST (UTC-5). Close enough to "work hours".
DEFAULT_PUBLISH_HOURS_UTC = [13, 15, 17, 19, 21, 23]

URL_RE = re.compile(r"\[upload\] youtube: (https://\S+)")


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


def pick_topics(log: dict, n: int) -> list[dict]:
    posted_ids = {e["catalog_id"] for e in log.get("posted", [])}
    unposted = [c for c in CATALOG if c["id"] not in posted_ids]
    if len(unposted) >= n:
        return unposted[:n]
    # Catalog exhausted — fall back to oldest-posted entries first
    posted_sorted = sorted(
        log.get("posted", []), key=lambda e: e.get("posted_at", "")
    )
    seen = {c["id"] for c in unposted}
    fallback: list[dict] = []
    for entry in posted_sorted:
        cid = entry["catalog_id"]
        if cid in seen:
            continue
        seen.add(cid)
        c = by_id(cid)
        if c:
            fallback.append(c)
        if len(unposted) + len(fallback) >= n:
            break
    return (unposted + fallback)[:n]


def schedule_publish_times(now_utc: datetime, n: int, hours: list[int]) -> list[str]:
    """Pick the next n hour-slots ≥5 min in the future, walking into tomorrow if needed."""
    base = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff = now_utc + timedelta(minutes=5)
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


def run_one(item: dict, publish_at: str | None, dry_run: bool) -> dict:
    cmd = [
        sys.executable, str(REPO / "make_short.py"),
        item["source_url"],
        "--start", str(item.get("start", 0)),
        "--duration", str(item.get("duration", 22)),
        "--gameplay", item.get("gameplay", "random"),
        "--script", item["script"],
        "--title", item["title"],
        "--tags", ",".join(item.get("tags", [])),
    ]
    if not dry_run:
        cmd += ["--upload", "youtube"]
        if publish_at:
            cmd += ["--publish-at", publish_at]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    elapsed = round(time.time() - start, 1)
    url_match = URL_RE.search(proc.stdout)
    ok = proc.returncode == 0 and (url_match is not None or dry_run)
    result = {
        "catalog_id": item["id"],
        "topic": item["topic"],
        "title": item["title"],
        "publish_at": publish_at,
        "elapsed_seconds": elapsed,
        "ok": ok,
        "video_url": url_match.group(1) if url_match else None,
        "exit_code": proc.returncode,
    }
    if not ok:
        result["stdout_tail"] = (proc.stdout or "")[-1500:]
        result["stderr_tail"] = (proc.stderr or "")[-1500:]
    return result


def format_report(date_str: str, results: list[dict]) -> str:
    success = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    lines = [
        f"# Daily Shorts Report — {date_str}",
        "",
        f"- queued: **{len(results)}**",
        f"- succeeded: **{len(success)}**",
        f"- failed: **{len(failed)}**",
        "",
    ]
    if success:
        lines.append("## Posted")
        for r in success:
            t = r.get("publish_at") or "now"
            lines.append(f"- **{r['topic']}** — {r['title']}")
            lines.append(f"  - publishes: `{t}`")
            if r["video_url"]:
                lines.append(f"  - {r['video_url']}")
            lines.append(f"  - took: {r['elapsed_seconds']}s")
        lines.append("")
    if failed:
        lines.append("## Failed")
        for r in failed:
            lines.append(f"- **{r['topic']}** — {r['title']} (exit {r['exit_code']})")
            tail = (r.get("stderr_tail") or r.get("stdout_tail") or "").strip()
            if tail:
                lines.append("  ```")
                for line in tail.splitlines()[-12:]:
                    lines.append(f"  {line}")
                lines.append("  ```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true",
                    help="build the shorts but don't upload to YouTube")
    ap.add_argument("--no-schedule", action="store_true",
                    help="post immediately instead of scheduling across the workday")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    log = load_log()
    picks = pick_topics(log, args.count)
    if not picks:
        print("No catalog entries available — catalog empty or all fallbacks exhausted.")
        return 1

    if args.no_schedule:
        schedule: list[str | None] = [None] * len(picks)
    else:
        schedule = schedule_publish_times(now, len(picks), DEFAULT_PUBLISH_HOURS_UTC)
    print(f"Picked {len(picks)} entries.")
    for item, pa in zip(picks, schedule):
        print(f"  {item['id']:32s} -> {pa or 'now'}")

    results: list[dict] = []
    for item, publish_at in zip(picks, schedule):
        print(f"\n--- {item['id']} ({item['topic']}) -> {publish_at or 'now'} ---")
        r = run_one(item, publish_at, args.dry_run)
        results.append(r)
        if r["ok"] and not args.dry_run:
            log["posted"].append({
                "catalog_id": r["catalog_id"],
                "posted_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publish_at": r["publish_at"],
                "video_url": r["video_url"],
            })
            save_log(log)

    today_str = now.strftime("%Y-%m-%d")
    REPORT_PATH.write_text(format_report(today_str, results))
    REPORT_JSON.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nReport: {REPORT_PATH}")

    return 0 if any(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
