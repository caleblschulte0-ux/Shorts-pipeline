#!/usr/bin/env python3
"""WHAT ACTUALLY RETAINS — attribution, not vibes.

The channel has been recording its creative decisions for months
(state/video_ledger.json: hook_type, ending_type, words_first_10s,
scene_changes_before_5s, depictions) and measuring its outcomes separately
(state/analytics_explainer/*.json: views, average_view_percentage, the early
retention curve). The two were never joined — every ledger row carries
`video_id: null` — so nobody could answer the only question that matters:

    which of the choices we make on purpose actually keep people watching?

`post_stories._creative_facts` now writes those facts into the posted-log entry
at upload time, and fetch_analytics carries them through. This reads the joined
result and reports retention BY CHOICE.

    python3 scripts/what_works.py                    # the report
    python3 scripts/what_works.py --min-views 100    # stricter evidence floor
    python3 scripts/what_works.py --json             # machine-readable

HONESTY RULES, because this is the file most likely to be used to justify a
change:

  * A group with fewer than `--min-group` videos is REPORTED BUT MARKED thin,
    never presented as a finding. Two videos is an anecdote.
  * Percentages over 100 (loops) and videos under the view floor are excluded
    from medians — a Short that loops can read as 400% and would swamp any
    group it lands in.
  * The report says what it CANNOT yet tell you. A channel this size has weeks
    where the honest answer is "not enough evidence", and printing that is the
    point: the retro loop's own doctrine is that laundering noise into a
    mandate is worse than no analysis.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANALYTICS = REPO / "state" / "analytics_explainer"

# The choices a director actually makes, and where each lives on a video row.
DIMENSIONS = {
    "hook": "hook type",
    "ending_type": "ending type",
    "story_structure": "chart structure",
    "topic_category": "topic",
    "n_beats": "number of beats",
    "scene_changes_before_5s": "cuts in the first 5s",
}


LEDGER = REPO / "state" / "video_ledger.json"


def _ledger_by_slug() -> dict:
    """The director's own record of each video, keyed by slug.

    92 rows of it existed before any of this could be used, because the join
    key everyone reached for was `video_id` — which the ledger never learned.
    The analytics rows carry `catalog_id`, which IS the slug, so the history
    joins today rather than starting from scratch at the next upload.
    """
    try:
        rows = json.loads(LEDGER.read_text()).get("videos", [])
    except Exception:  # noqa: BLE001 — the report must survive a missing ledger
        return {}
    out: dict = {}
    for row in rows:                       # later rows win: a re-direct is newer
        if row.get("slug"):
            out[row["slug"]] = row
    return out


def _enrich(videos: list[dict]) -> list[dict]:
    """Fill a video's creative facts from the ledger when the posted log
    predates `_creative_facts` (everything before 2026-09-04)."""
    led = _ledger_by_slug()
    if not led:
        return videos
    for v in videos:
        row = led.get(v.get("catalog_id") or "")
        if not row:
            continue
        v.setdefault("hook", None)
        v["hook"] = v.get("hook") or row.get("hook_type")
        v["ending_type"] = v.get("ending_type") or row.get("ending_type")
        v["topic_category"] = (v.get("topic_category")
                               or row.get("topic_category"))
        v["depictions"] = v.get("depictions") or row.get("depictions")
        v["words_first_10s"] = (v.get("words_first_10s")
                                if v.get("words_first_10s") is not None
                                else row.get("words_first_10s"))
        v["scene_changes_before_5s"] = (
            v.get("scene_changes_before_5s")
            if v.get("scene_changes_before_5s") is not None
            else row.get("scene_changes_before_5s"))
    return videos


def _load(path: Path | None = None) -> dict:
    p = path or (ANALYTICS / "latest.json")
    if not p.exists():
        raise SystemExit(f"no analytics at {p} — run scripts/fetch_analytics.py")
    data = json.loads(p.read_text())
    data["videos"] = _enrich(data.get("videos", []))
    return data


def usable(videos: list[dict], min_views: int) -> list[dict]:
    """Rows with a trustworthy retention number.

    `average_view_percentage` above 100 means the Short looped; those are real
    but they are a different phenomenon and they dominate any median they touch.
    """
    out = []
    for v in videos:
        pct = v.get("average_view_percentage")
        if pct is None or pct <= 0 or pct > 100:
            continue
        if (v.get("views") or 0) < min_views:
            continue
        out.append(v)
    return out


def group_by(videos: list[dict], field: str) -> dict:
    groups: dict = {}
    for v in videos:
        key = v.get(field)
        if key is None or key == "":
            continue
        if isinstance(key, list):
            key = "+".join(str(k) for k in key[:3])
        groups.setdefault(str(key), []).append(v)
    return groups


def summarise(rows: list[dict]) -> dict:
    pct = [r["average_view_percentage"] for r in rows]
    views = [r.get("views") or 0 for r in rows]
    return {"n": len(rows),
            "median_view_pct": round(st.median(pct), 1),
            "median_views": int(st.median(views))}


def report(data: dict, min_views: int, min_group: int) -> dict:
    vids = usable(data.get("videos", []), min_views)
    out: dict = {"videos_considered": len(vids), "min_views": min_views,
                 "dimensions": {}, "not_yet_answerable": []}
    if not vids:
        out["not_yet_answerable"].append(
            f"no video has >= {min_views} views AND a usable view percentage")
        return out

    baseline = round(st.median([v["average_view_percentage"] for v in vids]), 1)
    out["baseline_median_view_pct"] = baseline

    for field, label in DIMENSIONS.items():
        groups = group_by(vids, field)
        if not groups:
            out["not_yet_answerable"].append(
                f"{label}: not recorded on any video yet — it starts being "
                f"recorded at upload from 2026-09-04")
            continue
        rows = {k: summarise(v) for k, v in groups.items()}
        solid = {k: r for k, r in rows.items() if r["n"] >= min_group}
        out["dimensions"][field] = {
            "label": label,
            "groups": dict(sorted(rows.items(),
                                  key=lambda kv: -kv[1]["median_view_pct"])),
            "thin": sorted(k for k, r in rows.items() if r["n"] < min_group),
        }
        if not solid:
            out["not_yet_answerable"].append(
                f"{label}: every group has fewer than {min_group} videos — "
                f"anecdote, not evidence")
    return out


def _print(rep: dict) -> None:
    print(f"WHAT WORKS — {rep['videos_considered']} videos with >= "
          f"{rep['min_views']} views and a usable retention number")
    if "baseline_median_view_pct" in rep:
        print(f"channel baseline: {rep['baseline_median_view_pct']}% median "
              f"view percentage\n")
    for field, blk in rep["dimensions"].items():
        print(f"  {blk['label'].upper()}")
        for key, r in blk["groups"].items():
            thin = "  (thin — anecdote)" if key in blk["thin"] else ""
            delta = r["median_view_pct"] - rep.get("baseline_median_view_pct", 0)
            print(f"    {key[:34]:34} n={r['n']:<3} "
                  f"view% {r['median_view_pct']:>5}  "
                  f"({delta:+.1f} vs baseline)  "
                  f"views {r['median_views']:>4}{thin}")
        print()
    if rep["not_yet_answerable"]:
        print("  NOT YET ANSWERABLE — say this out loud instead of guessing:")
        for line in rep["not_yet_answerable"]:
            print(f"    - {line}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-views", type=int, default=50,
                    help="view floor for a video to count as evidence")
    ap.add_argument("--min-group", type=int, default=4,
                    help="videos a group needs before it is a finding")
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = report(_load(a.file), a.min_views, a.min_group)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        _print(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
