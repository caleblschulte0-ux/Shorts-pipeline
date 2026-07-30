#!/usr/bin/env python3
"""Recount every running experiment against the live analytics.

This is the step that was missing entirely: `bump_samples` existed but
nothing ever called it, so an experiment's `samples_seen` sat at 0 forever
and `readout_ready` could never pass its sample floor. Experiments started,
and then ran until the heat death of the channel.

Counts only videos that ACTUALLY RAN under the experiment — published after
it started, on its channel, in its format. Recounts from scratch every time
rather than incrementing, so re-running is idempotent and a retried workflow
cannot inflate the number.

    python scripts/advance_experiments.py
    python scripts/advance_experiments.py --json

Never raises into CI: the review loop must not be able to block production.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CHANNEL_ANALYTICS = {
    "trending": "state/analytics/latest.json",
    "explainer": "state/analytics_explainer/latest.json",
    "curiosity": "state/analytics_curiosity/latest.json",
    "third": "state/analytics_third/latest.json",
}


def videos_by_channel() -> dict:
    out = {}
    for name, path in CHANNEL_ANALYTICS.items():
        try:
            data = json.loads((ROOT / path).read_text())
            out[name] = [v for v in data.get("videos") or []
                         if isinstance(v, dict)]
        except Exception:                            # noqa: BLE001
            out[name] = []
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        from shared import experiments as ex
        pool = videos_by_channel()
        due = ex.advance(pool)
        stale = ex.stale()
        summary = ex.summary()
    except Exception as exc:                         # noqa: BLE001
        print(f"::warning::advance_experiments failed ({exc}) — the loop "
              f"retries tomorrow; production is unaffected")
        return 0

    if args.json:
        print(json.dumps({"due": [e["id"] for e in due],
                          "stale": [e["id"] for e in stale],
                          "summary": summary}, indent=2))
        return 0

    for e in summary.get("running") or []:
        print(f"  {e['id']}: {e['samples']} samples, {e['days']}d "
              f"— {e['blocked_by']}")
    for e in due:
        print(f"::notice::experiment {e['id']} is READY FOR READOUT "
              f"({e['samples_seen']} samples, needs {e['min_samples']})")
    for e in stale:
        print(f"::warning::experiment {e['id']} has been open "
              f"{ex.days_elapsed(e):.0f} days with no verdict — it is "
              f"holding a channel's experiment slot. Read it out or abandon it.")
    if not summary.get("running"):
        print("  no experiments running")
    return 0


if __name__ == "__main__":
    sys.exit(main())
