#!/usr/bin/env python3
"""Third-channel series/mix audit — doctor finding 2127c6395c2c.

The channel's content taxonomy (`series`: drama/beef/rage/fail/wholesome/
chaos/...) is assigned per-clip by the author brain and stored on every
posted-log + analytics entry. Comparing raw VPH across series told a
misleading story while `third_capture/author.py` silently folded every
clip the author couldn't (or didn't) classify into "chaos" — the channel's
biggest bucket looked like its weakest-performing REAL series when part of
it was actually "unclassified". That defaulting is fixed (author.py now
returns "unknown" for anything outside its documented enum), but nothing
told a reader the two apart. This does.

Reads a fetch_analytics.py snapshot (state/analytics_third/latest.json by
default) and reports, PER SERIES, the count and median views-per-hour among
videos mature enough to judge (>=72h old, the same floor retro/ uses),
keeping "unknown" and "story" (compiled multi-clip stories, not a content
series) out of the content-mix comparison so a stale audit can't smuggle
unclassified or structurally-different videos into a "chaos underperforms"
claim.

Outputs: state/third_series_audit.json + state/third_series_audit.md
Best-effort: a missing/malformed snapshot produces an empty report, never
a crash — analytics tooling must never take the pipeline down.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYTICS = ROOT / "state" / "analytics_third" / "latest.json"
OUT_JSON = ROOT / "state" / "third_series_audit.json"
OUT_MD = ROOT / "state" / "third_series_audit.md"

MATURE_HOURS = 72.0
# Not content-mix decisions: "unknown" means the author didn't classify the
# clip (see third_capture/author.py's _VALID_SERIES gate); "story" is a
# compiled multi-clip structure, not a series. Both are reported separately
# so they never get read as "the chaos series is weak" or vice versa.
NON_CONTENT_SERIES = {"unknown", "story"}


def load_videos(path: Path = ANALYTICS) -> list[dict]:
    try:
        data = json.loads(path.read_text())
    except Exception:                                # noqa: BLE001
        return []
    videos = data.get("videos") if isinstance(data, dict) else None
    return videos if isinstance(videos, list) else []


def audit(videos: list[dict], mature_hours: float = MATURE_HOURS) -> dict:
    """Group mature videos by series, report n + median views_per_hour.

    Returns {"mature_hours": ..., "content_series": {name: {n, median_vph}},
    "excluded": {name: {n, median_vph}}} -- `excluded` holds "unknown" and
    "story" so they stay visible without polluting the content comparison.
    """
    buckets: dict[str, list[float]] = {}
    for v in videos:
        try:
            age = float(v.get("age_hours"))
            vph = float(v.get("views_per_hour"))
        except (TypeError, ValueError):
            continue
        if age < mature_hours:
            continue
        series = str(v.get("series") or "unknown")
        buckets.setdefault(series, []).append(vph)

    def _stats(vphs: list[float]) -> dict:
        return {"n": len(vphs), "median_vph": round(statistics.median(vphs), 4)}

    content = {name: _stats(vphs) for name, vphs in buckets.items()
               if name not in NON_CONTENT_SERIES}
    excluded = {name: _stats(vphs) for name, vphs in buckets.items()
                if name in NON_CONTENT_SERIES}
    return {
        "mature_hours": mature_hours,
        "content_series": dict(sorted(
            content.items(), key=lambda kv: -kv[1]["n"])),
        "excluded": dict(sorted(
            excluded.items(), key=lambda kv: -kv[1]["n"])),
    }


def render_md(report: dict) -> str:
    lines = [
        f"### Third series audit (mature >= {report['mature_hours']:.0f}h)",
        "",
        "| series | n | median VPH |",
        "|---|---|---|",
    ]
    for name, s in report["content_series"].items():
        lines.append(f"| {name} | {s['n']} | {s['median_vph']} |")
    if report["excluded"]:
        lines.append("")
        lines.append("Excluded from the content-mix comparison "
                      "(unclassified / non-series structure):")
        lines.append("")
        lines.append("| label | n | median VPH |")
        lines.append("|---|---|---|")
        for name, s in report["excluded"].items():
            lines.append(f"| {name} | {s['n']} | {s['median_vph']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    videos = load_videos()
    report = audit(videos)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    OUT_MD.write_text(render_md(report))
    print(f"[third_series_audit] {len(videos)} videos read, "
          f"{sum(s['n'] for s in report['content_series'].values())} mature "
          f"content-series, {sum(s['n'] for s in report['excluded'].values())}"
          " excluded (unknown/story)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
