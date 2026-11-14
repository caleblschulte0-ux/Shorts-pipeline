"""Is the Twitch channel still making videos? (operator, 2026-11-14: "learn
from this and expand 10 times in every direction on every problem").

What its own records showed, days before anyone looked:

- 2026-11-08..10: 64 slots in a row skipped as "quality floor: best banger
  0.20" — a fallback judge gave every candidate the same score and nothing
  was ever downloaded. Three days, zero posts, every run green.
- 2026-11-11..13: 12 failed renders "self-healed" into the identical blur
  fill and 10 were rejected again for the same thin strip.
- 2026-11-11..13: one 21s story cut rendered, judged and dropped for its
  length in five runs running.

This reads `state/third_qa_stats.json` (this run is already in it — the
render step writes it) and FAILS the run (exit 1, reason in the step
summary) when, over the last `DAYS` days of live runs:

- a slot or a story died on an exception that is not a gate's verdict;
- `MIN_RUNS` or more runs tried fresh slots and not one video shipped;
- `SKIP_MIN` or more slots, over `SHARE` of those tried, were skipped by
  the title judge before any clip was watched;
- `QA_MIN` or more clips were rendered and over `SHARE` were refused by QA;
- the same story was rendered and refused `REPEAT_MIN` times.

    python scripts/third_health.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared import channel_health  # noqa: E402

STATS = ROOT / "state" / "third_qa_stats.json"
DAYS = 3
MIN_RUNS = 2
SKIP_MIN = 4
QA_MIN = 3
SHARE = 2 / 3
REPEAT_MIN = 3
# a story outcome that cost a render, so a repeat of it is waste
RENDERED = ("duration", "qa_failed", "narrative_failed", "render_failed",
            "table_read_failed")
# an exception a gate raises to say no; anything else is a crash
VERDICT_ERRORS = ("RuntimeError",)


def _crash(error: str) -> bool:
    m = re.match(r"([A-Za-z_][\w.]*)(?::|$)", str(error or ""))
    return bool(m) and m.group(1) not in VERDICT_ERRORS


def _tried(slot: dict) -> bool:
    return slot.get("skipped") != "already posted"


def _shipped(slot: dict) -> bool:
    return bool(slot.get("ok")) and not slot.get("skipped")


def _clusters(slot: dict) -> list[dict]:
    return (((slot.get("judges") or {}).get("story_director") or {})
            .get("clusters") or [])


def problems(runs: list[dict]) -> list[str]:
    """What is wrong across these runs, in words; [] when nothing is."""
    runs = [r for r in runs if not r.get("dry_run")]
    slots = [s for r in runs for s in r.get("clips") or []]
    out = []

    crashed = [s["error"] for s in slots if _crash(s.get("error"))]
    crashed += [c.get("why") for s in slots for c in _clusters(s)
                if c.get("outcome") == "render_failed"
                and _crash(c.get("why"))]
    if crashed:
        out.append(f"{len(crashed)} slot(s) or stories crashed, e.g. "
                   f"{str(crashed[0])[:160]!r}")

    trying = [r for r in runs if any(_tried(s) for s in r.get("clips") or [])]
    tried = [s for s in slots if _tried(s)]
    if len(trying) >= MIN_RUNS and not any(_shipped(s) for s in tried):
        limited = sum(1 for r in trying if (r.get("brain") or {})
                      .get("limited_at"))
        why = channel_health.top(s.get("skipped") or s.get("error")
                                 for s in tried)
        out.append(f"{len(trying)} runs tried {len(tried)} slots and not "
                   f"one video shipped"
                   + (f" (Claude at its usage limit in {limited})"
                      if limited else "") + f": {why}")

    floor = [s for s in tried
             if str(s.get("skipped") or "").startswith("quality floor")]
    if len(floor) >= SKIP_MIN and len(floor) > SHARE * len(tried):
        out.append(f"{len(floor)} of {len(tried)} slots were skipped by the "
                   "title judge before a clip was watched: "
                   + channel_health.top(s["skipped"] for s in floor))

    rendered = [s for s in slots if s.get("render_level")]
    refused = [s for s in rendered
               if "qa_rejected" in str(s.get("error") or "")]
    if len(rendered) >= QA_MIN and len(refused) > SHARE * len(rendered):
        out.append(f"{len(refused)} of {len(rendered)} rendered clips were "
                   "refused by QA: " + channel_health.top(
                       re.sub(r"^RuntimeError: qa_rejected: ", "",
                              s["error"])[:80] for s in refused))

    again = Counter((c.get("cluster"), c.get("outcome"))
                    for s in slots for c in _clusters(s)
                    if c.get("outcome") in RENDERED)
    for (cluster, outcome), n in again.most_common():
        if n < REPEAT_MIN:
            break
        out.append(f"the story {cluster!r} was rendered and refused "
                   f"({outcome}) {n} times — a refusal nobody remembered")
    return out


def main() -> int:
    try:
        runs = json.loads(STATS.read_text()).get("runs", [])
    except (OSError, ValueError) as e:
        print(f"::warning::[health] no run records ({e})", flush=True)
        runs = []
    found = problems(channel_health.window(runs, DAYS))
    return channel_health.emit(
        "Twitch channel health", found,
        "clips are being picked, rendered and posted")


if __name__ == "__main__":
    sys.exit(main())
