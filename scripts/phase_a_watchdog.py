#!/usr/bin/env python3
"""IS THE DAY'S BUNDLE THERE BEFORE CHATGPT NEEDS IT? We answer, not it.

Doctor finding 5187e34e11f3. Phase A has three triggers and only ONE of them
is independent of upstream authoring having already happened: the 09:45 UTC
cron. Its own comments record GitHub cron drift measured in hours. On both
2026-08-29 and 2026-08-30 the 06:00 Central media worker reached the handoff
with no bundle and no package slate; the 08-30 artifact says outright that
no current-date Phase A artifact or commit existed.

Worse, nothing went red. `chatgpt_watchdog.media_expectation` reads a
missing bundle as "the bundle asks for 0 images" -> not_required -> ok. The
one check pointed at that morning EXCUSED the failure, which is the precise
trap CLAUDE.md names: "nothing here" reading as "nothing to do".

So this runs BEFORE the media worker, judges whether the bundle exists, and
records a durable verdict either way. The workflow acts on the verdict
(dispatch Phase A, wait, re-check); the judging lives here so it is testable
offline with no network and no clock games.

    python scripts/phase_a_watchdog.py                 # judge today
    python scripts/phase_a_watchdog.py --date 20260909
    python scripts/phase_a_watchdog.py --record        # write the verdict

Exit 0 = ready (or too early to say). Exit 1 = the bundle is missing past
its deadline — fail CLOSED so the run goes red and the alarm reads a
verdict somebody actually took, at a known time.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import centraltime  # noqa: E402

SCHEMA = "phase-a-readiness/v1"
OUT_DIRNAME = "phase_a_readiness"

# The media worker starts at 06:00 Central (shared/media_checkpoint.py's own
# runs_at). Judge at 05:00 so there is an hour to dispatch Phase A and let it
# finish before ChatGPT looks.
DEADLINE_CENTRAL = 5
MEDIA_WORKER_CENTRAL = 6


def bundle_dir(date: str) -> Path:
    return ROOT / "exchange" / "bundles" / str(date)


def _load(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def bundle_state(date: str) -> dict:
    """What actually exists for `date`, as facts rather than a verdict."""
    d = bundle_dir(date)
    bundle = _load(d / "bundle.json")
    ok = isinstance(bundle, dict)
    return {
        "bundle_path": str((d / "bundle.json").relative_to(ROOT)),
        "bundle_present": ok,
        # A bundle that exists but carries no plan is not a usable handoff.
        # Phase A writing an empty shell is a different failure from Phase A
        # never running, and the fix differs, so keep them distinguishable.
        "bundle_id": (bundle or {}).get("bundle_id") or "",
        "n_requests": len((bundle or {}).get("requests") or []) if ok else 0,
        "has_contract": (d / "bundle.json.contract").exists(),
    }


def evaluate(date: str, now=None) -> dict:
    """ready | pending | MISSING, with the facts that decided it."""
    st = bundle_state(date)
    now = now or datetime.now(timezone.utc)
    passed = centraltime.deadline_passed(date, DEADLINE_CENTRAL, now)
    if st["bundle_present"]:
        status = "ready"
        headline = (f"bundle present for {date} "
                    f"({st['n_requests']} media request(s))")
    elif not passed:
        # Calling it missing before the deadline is how an alarm earns a
        # reputation for lying.
        status = "pending"
        headline = (f"no bundle yet for {date}, but it is not "
                    f"{DEADLINE_CENTRAL:02d}:00 Central yet")
    else:
        status = "MISSING"
        headline = (
            f"PHASE A HAS NOT RUN FOR {date} — no bundle exists and the "
            f"{DEADLINE_CENTRAL:02d}:00 Central deadline has passed. The "
            f"{MEDIA_WORKER_CENTRAL:02d}:00 media worker is about to start "
            f"with nothing to work from.")
    return {
        "schema": SCHEMA, "date": str(date), "status": status,
        "ok": status in ("ready", "pending"),
        "deadline_central": DEADLINE_CENTRAL,
        "deadline_passed": passed,
        "checked_at": now.replace(microsecond=0).isoformat(),
        "headline": headline,
        **st,
    }


def record(res: dict) -> Path:
    d = ROOT / "state" / OUT_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{res['date']}.json"
    p.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    return p


def verdict(date: str) -> dict | None:
    """The recorded verdict for a date, for anything downstream that wants
    to know whether the day ever had a bundle."""
    return _load(ROOT / "state" / OUT_DIRNAME / f"{date}.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--record", action="store_true",
                    help="write the verdict to state/ (CI commits it)")
    a = ap.parse_args()
    date = a.date or datetime.now(timezone.utc).strftime("%Y%m%d")
    res = evaluate(date)
    print(json.dumps(res, indent=1, sort_keys=True))
    if a.record:
        print(f"[phase-a-watchdog] wrote {record(res).relative_to(ROOT)}")
    if res["status"] == "MISSING":
        print(f"::error::{res['headline']}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
