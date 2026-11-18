"""Calibrate the story-first scorecard against what the channel's viewers did.

Blind-scores the N most-watched and N least-watched posted illustrated
stories (older than three days, so a young video is not called weak) with
the SAME `shared.story_brief.scorecard` the posting run uses, in shuffled
order and never told the views, then prints how well the card separates
them. The bands in the registry (`explainer.formats.data_story.story_gate`)
are set from this; re-run it before moving them.

    python scripts/calibrate_story_gate.py --n 10 --out /tmp/cal.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shared import story_brief as sb  # noqa: E402


def pick(n: int) -> list[tuple[str, dict, dict]]:
    a = json.loads((REPO / "state/analytics_explainer/latest.json").read_text())
    cfg = json.loads((REPO / "data_learning/niche.config.json").read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    rows = [x for x in a["videos"] if x.get("catalog_id") in stories
            and "3d" not in x["catalog_id"] and x.get("views") is not None
            and (x.get("age_hours") or 0) > 72]
    rows.sort(key=lambda x: (x["views"], x.get("average_view_percentage") or 0),
              reverse=True)
    pool = ([("strong", x, stories[x["catalog_id"]]) for x in rows[:n]]
            + [("weak", x, stories[x["catalog_id"]]) for x in rows[-n:]])
    random.Random(7).shuffle(pool)
    return pool


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    pool = pick(args.n)

    def one(item):
        band, x, sc = item
        return {"band": band, "slug": x["catalog_id"], "views": x["views"],
                "card": sb.scorecard(sc)}

    with cf.ThreadPoolExecutor(4) as ex:
        out = list(ex.map(one, pool))
    s = [r["card"]["total"] for r in out if r["band"] == "strong" and r["card"]]
    w = [r["card"]["total"] for r in out if r["band"] == "weak" and r["card"]]
    auc = (sum((a > b) + 0.5 * (a == b) for a in s for b in w)
           / max(1, len(s) * len(w)))
    summary = {"strong": sorted(s), "weak": sorted(w),
               "strong_mean": round(st.mean(s), 1) if s else None,
               "weak_mean": round(st.mean(w), 1) if w else None,
               "auc": round(auc, 3),
               "fatal": {b: sum(1 for r in out if r["band"] == b and r["card"]
                                and r["card"]["fatal"])
                         for b in ("strong", "weak")}}
    print(json.dumps(summary, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": out},
                                             indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
