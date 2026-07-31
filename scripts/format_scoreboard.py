#!/usr/bin/env python3
"""A/B/C format scoreboard for the trending channel.

The channel's daily mix lives in config/channel_registry.json. This joins the authored packages (title -> format) with the
analytics snapshot (title -> views/engagement) and rolls up per-format
performance, so the daily report shows WHICH FORMAT IS WINNING instead of
per-video noise. Runs best-effort in CI right after the analytics fetch.

Outputs: state/format_scoreboard.json + state/format_scoreboard.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_ROOT = ROOT / "state" / "trending_packages"
ANALYTICS = ROOT / "state" / "analytics" / "latest.json"
OUT_JSON = ROOT / "state" / "format_scoreboard.json"
OUT_MD = ROOT / "state" / "format_scoreboard.md"

def _formats() -> tuple[str, ...]:
    """Every format the scoreboard buckets by — from the registry, INCLUDING
    retired ones. A retired format still has months of posted videos behind
    it, and dropping it from the scoreboard would erase the evidence that
    justified retiring it."""
    try:
        from shared import channel_registry as _reg
        known = set()
        for cid in _reg.channel_ids(enabled_only=False):
            known |= set(_reg.formats(cid, state=None))
        return tuple(sorted(known | {"explainer"}))
    except Exception:                                # noqa: BLE001
        # Analytics must never take the pipeline down. A scoreboard that
        # buckets nothing is a bad report, not a lost day.
        return ("reddit_story", "text_card", "graph_race", "explainer")


FORMATS = _formats()


def _norm(t: str) -> str:
    return " ".join((t or "").casefold().split())


def package_formats() -> dict[str, str]:
    """Map normalized title -> format for every authored package."""
    out: dict[str, str] = {}
    if not PKG_ROOT.exists():
        return out
    for p in sorted(PKG_ROOT.glob("*/*.json")):
        try:
            pkg = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        fmt = pkg.get("format") or (
            "reddit" if pkg.get("subreddit") else "explainer")
        title = pkg.get("title") or pkg.get("topic") or ""
        if title:
            out[_norm(title)] = fmt
    return out


def build() -> dict:
    fmt_by_title = package_formats()
    try:
        videos = json.loads(ANALYTICS.read_text()).get("videos", [])
    except Exception:  # noqa: BLE001
        videos = []

    rows = {f: {"format": f, "videos": 0, "views": 0, "engaged_views": 0,
                "likes": 0, "shares": 0, "subs_gained": 0,
                "vph_sum": 0.0, "avp_sum": 0.0, "avp_n": 0}
            for f in FORMATS}
    unmatched = 0
    for v in videos:
        fmt = fmt_by_title.get(_norm(v.get("title", "")))
        if fmt is None:
            unmatched += 1
            continue
        r = rows[fmt]
        r["videos"] += 1
        r["views"] += v.get("views") or 0
        r["engaged_views"] += v.get("engaged_views") or 0
        r["likes"] += v.get("likes") or 0
        r["shares"] += v.get("shares") or 0
        r["subs_gained"] += v.get("subscribers_gained") or 0
        r["vph_sum"] += v.get("views_per_hour") or 0.0
        if v.get("average_view_percentage") is not None:
            r["avp_sum"] += v["average_view_percentage"]
            r["avp_n"] += 1

    out = []
    for f in FORMATS:
        r = rows[f]
        if not r["videos"]:
            continue
        n = r["videos"]
        out.append({
            "format": f, "videos": n, "views": r["views"],
            "views_per_video": round(r["views"] / n, 1),
            "avg_views_per_hour": round(r["vph_sum"] / n, 2),
            "engaged_views": r["engaged_views"],
            "avg_view_pct": round(r["avp_sum"] / r["avp_n"], 1)
            if r["avp_n"] else None,
            "likes": r["likes"], "shares": r["shares"],
            "subs_gained": r["subs_gained"],
        })
    out.sort(key=lambda r: -r["views_per_video"])
    return {"formats": out, "matched": sum(r["videos"] for r in out),
            "unmatched": unmatched}


def to_md(sb: dict) -> str:
    lines = ["## Format scoreboard (A/B/C test)", "",
             "| format | videos | views | views/video | avg vph | "
             "avg view % | likes | shares | subs |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in sb["formats"]:
        lines.append(
            f"| {r['format']} | {r['videos']} | {r['views']} | "
            f"{r['views_per_video']} | {r['avg_views_per_hour']} | "
            f"{r['avg_view_pct'] if r['avg_view_pct'] is not None else '—'} | "
            f"{r['likes']} | {r['shares']} | {r['subs_gained']} |")
    lines.append("")
    lines.append(f"matched {sb['matched']} videos to packages, "
                 f"{sb['unmatched']} unmatched (pre-A/B/C uploads)")
    return "\n".join(lines) + "\n"


def main() -> int:
    sb = build()
    OUT_JSON.write_text(json.dumps(sb, indent=2) + "\n")
    md = to_md(sb)
    OUT_MD.write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
