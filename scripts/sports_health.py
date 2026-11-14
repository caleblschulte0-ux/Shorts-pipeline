"""Is Baller Bro still making what makes it? (operator, 2026-11-14: "what
can we double check to make sure isn't going to be wrong again?")

From 2026-10-20 to 2026-11-13 the channel posted bare clips while every
part of the cut-in/montage path looked fine one run at a time: downloads
died after one reset, the footage played tiny and the judge held every
post that had it, and a parse error killed one to three posts a run. Each
was plain in the run reports, days before anyone saw it on the channel.

This reads this run's `sports_report.json` and the last `DAYS` days of
live reports on the preview-renders branch, and FAILS the run (exit 1,
with the reason in the step summary) when:

- a render crashed (`render failed: ...`): a bug, never a judgement;
- `MIN_POSTS` or more posts went out and none had a cut-in or montage;
- `HELD_MIN` or more cuts carried a cut-in or montage and over
  `HELD_SHARE` of them were held: something about the footage is wrong.

    python scripts/sports_health.py            # this run + recent runs
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "sports_report.json"
DAYS = 3
MIN_POSTS = 4
HELD_MIN = 3
HELD_SHARE = 2 / 3
# Runs before the 2026-11-14 fixes (PRs 754-756) are the problems this
# check was written from; counting them would keep it red for days after.
FLOOR = "2026-11-14"


def _rich(slot: dict) -> bool:
    led = slot.get("ledger") or {}
    return bool(led.get("cut_in")) or bool(led.get("outro"))


def problems(reports: list[dict]) -> list[str]:
    """What is wrong across `reports`, in words; [] when nothing is."""
    slots = [s for r in reports for s in r.get("slots") or []]
    out = []
    crashed = [s for s in slots
               if str(s.get("skipped") or "").startswith("render failed")]
    if crashed:
        out.append(f"{len(crashed)} render(s) crashed, e.g. "
                   f"{crashed[0]['skipped'][:160]!r}")
    made = [s for s in slots if "ledger" in s]
    posted = [s for s in made if not s.get("skipped")]
    if len(posted) >= MIN_POSTS and not any(_rich(s) for s in posted):
        out.append(f"{len(posted)} posts in {DAYS} days and not one had a "
                   "cut-in or a montage")
    rich = [s for s in made if _rich(s)]
    held = [s for s in rich if s.get("skipped")]
    if len(rich) >= HELD_MIN and len(held) > HELD_SHARE * len(rich):
        why = "; ".join(str(s["skipped"])[:120] for s in held[:3])
        out.append(f"{len(held)} of {len(rich)} cuts with a cut-in or "
                   f"montage were held: {why}")
    return out


def recent(days: int = DAYS) -> list[dict]:
    """Live reports from the last `days` days on preview-renders."""
    try:
        subprocess.run(["git", "fetch", "-q", "--depth=1", "origin",
                        "preview-renders"], cwd=ROOT, timeout=120,
                       check=True)
        names = subprocess.run(
            ["git", "ls-tree", "--name-only", "FETCH_HEAD", "sports-live/"],
            cwd=ROOT, capture_output=True, text=True, timeout=60
        ).stdout.split()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[health] no earlier reports ({e})", flush=True)
        return []
    since = max(FLOOR, (dt.date.today()
                        - dt.timedelta(days=days)).isoformat())
    out = []
    for d in names:
        day = d.split("/")[-1][:10]
        if day < since:
            continue
        try:
            out.append(json.loads(subprocess.run(
                ["git", "show", f"FETCH_HEAD:{d}/sports_report.json"],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
                check=True).stdout))
        except Exception:  # noqa: BLE001
            continue
    return out


def main() -> int:
    reports = recent()
    if REPORT.exists():
        try:
            reports.append(json.loads(REPORT.read_text()))
        except ValueError:
            pass
    found = problems(reports)
    lines = ([f"- {p}" for p in found] if found
             else ["- cut-ins and montages are being made and posted"])
    text = "### Baller Bro health\n" + "\n".join(lines) + "\n"
    print(text, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(text)
    for p in found:
        print(f"::error::[health] {p}", flush=True)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
