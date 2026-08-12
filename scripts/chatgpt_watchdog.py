#!/usr/bin/env python3
"""Did the ChatGPT scheduled task actually LEAVE ITS ARTIFACT? Answered by us.

WHY THIS EXISTS
---------------
On 2026-08-12 all three ChatGPT scheduled tasks fired on time and left
NOTHING in the repo: no `media-progress/STARTED.json`, no `response.json`,
no `DONE`, no `doctor/reports/20260812.json`. The same tasks had committed
normally the previous morning (checkpoints at 06:15 CT, response at 07:06,
DONE at 07:07), so the contract and the bundle were fine — today's bundle is
structurally identical to yesterday's and carried 13 well-formed requests
when the media worker fired.

The decisive observation is STEP 0. The media worker's first instruction is
a heartbeat: one small JSON file, committed before any real work. It needs
no Drive, no image generation, no bundle parsing — it depends on exactly ONE
capability, the ability to write to the repo. It did not land, and neither
did the other two tasks' artifacts, on the same day. The only thing all
three share is that capability.

So the failing component is not the instructions, the bundle, or the work:
it is ChatGPT's ability to COMMIT from a scheduled session. The repo cannot
grant that. What the repo can stop doing is *depending on it silently*.

Before this, a no-show was indistinguishable from idle:

  * `daily_alarm` runs at 01:15 UTC — a 06:03 CT failure went unreported for
    nearly twenty hours, long past the point where the operator could have
    re-fired the task and still had the day ship properly.
  * an empty `media-progress/` reads the same whether the worker failed or
    the day legitimately had no media requests.
  * an empty doctor backlog reads the same whether every finding was ruled
    or nobody filed one.

This script is the deterministic half of the boundary the operator asked
for: ChatGPT supplies judgment and content; WE verify, record and shout.
It runs on a cron shortly after each task's deadline, decides on evidence
whether the artifact is present, and writes a machine-readable outcome to
`state/chatgpt_tasks/<date>/<task>.json`. A missing artifact is recorded as
CHATGPT TASK FAILED / NO ARTIFACT and exits non-zero, so the run is RED.

It never renders, never publishes and never touches a quality gate. It only
answers one question honestly.

    python scripts/chatgpt_watchdog.py --task media --date 20260812
    python scripts/chatgpt_watchdog.py --all --date 20260812
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIRNAME = "chatgpt_tasks"
SCHEMA = "chatgpt-task-outcome/v1"

# Deadline in CENTRAL time, per task — the hour by which the artifact must
# exist. The workers fire at 06:00 and 07:00 CT. The doctor is a NIGHTLY
# read and has historically filed around 23:00 CT (20260810.json landed
# 23:09), so today's doctor cannot be judged during the morning at all —
# which is why the workflow also runs over YESTERDAY, where every task is
# definitively judgeable.
DEADLINE_CENTRAL = {"media": 7, "finalizer": 8, "doctor": 23}

TASKS = ("media", "finalizer", "doctor")


def _bundle_dir(date: str) -> Path:
    return ROOT / "exchange" / "bundles" / str(date)


def _load(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:                                    # noqa: BLE001
        return None


def media_expectation(date: str) -> tuple[bool, str]:
    """Is the 06:00 media worker REQUIRED to have left something today?

    Only when the day's bundle actually asks for images. A day with no media
    requests is not a failed worker, and calling it one trains the operator
    to ignore this alarm.
    """
    bundle = _load(_bundle_dir(date) / "bundle.json")
    if not isinstance(bundle, dict):
        return False, "no bundle.json for this date — Phase A has not run"
    n = len(bundle.get("requests") or [])
    if not n:
        return False, "the bundle asks for 0 images"
    return True, f"the bundle asks for {n} image(s)"


def check_media(date: str) -> dict:
    required, why = media_expectation(date)
    prog = _bundle_dir(date) / "media-progress"
    found = sorted(p.name for p in prog.glob("*.json")) if prog.is_dir() else []
    # A FAILED-*.json note is a SUCCESSFUL heartbeat: the worker showed up and
    # said what blocked it. That is the contract working, not a no-show.
    return {
        "task": "media", "required": required, "why_required": why,
        "expected": [f"exchange/bundles/{date}/media-progress/STARTED.json",
                     "…/<safe_request_id>.json", "…/FAILED-<id>.json"],
        "found": found,
        "ok": bool(found) or not required,
    }


def check_finalizer(date: str) -> dict:
    d = _bundle_dir(date)
    bundle = _load(d / "bundle.json")
    required = isinstance(bundle, dict)
    resp, done = d / "response.json", d / "DONE"
    found = [p.name for p in (resp, done) if p.exists()]
    # response.json WITHOUT DONE is a real, distinct state: the finalizer got
    # its content down and could not close. The contract explicitly allows it
    # (a "blocked" field), so it is reported as partial, never as success —
    # nothing renders without DONE.
    return {
        "task": "finalizer", "required": required,
        "why_required": ("a bundle exists for this date" if required
                         else "no bundle.json — nothing was asked for"),
        "expected": [f"exchange/bundles/{date}/response.json",
                     f"exchange/bundles/{date}/DONE"],
        "found": found,
        "partial": bool(resp.exists() and not done.exists()),
        "ok": bool(resp.exists() and done.exists()) or not required,
    }


def check_doctor(date: str) -> dict:
    rep = ROOT / "doctor" / "reports" / f"{date}.json"
    return {
        "task": "doctor", "required": True,
        "why_required": "the doctor is a daily read",
        "expected": [f"doctor/reports/{date}.json"],
        "found": [rep.name] if rep.exists() else [],
        "ok": rep.exists(),
    }


CHECKS = {"media": check_media, "finalizer": check_finalizer,
          "doctor": check_doctor}


def _deadline_passed(task: str, date: str, now=None) -> bool:
    """Has this task's Central-time deadline gone by for `date`?

    Anything scheduled in local time has to be judged in local time — the
    crons that fire this run at fixed UTC hours and drift an hour at DST,
    which is the same trap that put Phase B's backstop fifteen minutes
    before the finalizer for half of every year.
    """
    now = now or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        now = now.astimezone(ZoneInfo("America/Chicago"))
    except Exception:                                    # noqa: BLE001
        pass
    try:
        day = datetime.strptime(str(date), "%Y%m%d").date()
    except ValueError:
        return True
    if now.date() > day:
        return True                      # the day is over; judge it
    if now.date() < day:
        return False
    return now.hour >= DEADLINE_CENTRAL.get(task, 9)


def evaluate(task: str, date: str, now=None) -> dict:
    res = CHECKS[task](date)
    now = now or datetime.now(timezone.utc)
    passed = _deadline_passed(task, date, now)
    if res["ok"]:
        status = "ok" if res["required"] else "not_required"
    elif not passed:
        # Not late yet. Calling a task failed before its deadline is how an
        # alarm earns a reputation for lying.
        status = "pending"
    else:
        status = "FAILED_NO_ARTIFACT"
    res.update({
        "schema": SCHEMA, "date": str(date), "status": status,
        "checked_at": now.replace(microsecond=0).isoformat(),
        # The one sentence a human should need. Deliberately blunt: this
        # exists because "nothing here" used to read as "nothing to do".
        "deadline_central": DEADLINE_CENTRAL.get(task),
        "deadline_passed": passed,
        "headline": (
            f"CHATGPT TASK FAILED / NO ARTIFACT — the {task} task left "
            f"nothing in the repo for {date} ({res['why_required']})."
            if status == "FAILED_NO_ARTIFACT" else
            f"{task}: {status}"),
    })
    return res


def record(res: dict) -> Path:
    d = ROOT / "state" / OUT_DIRNAME / str(res["date"])
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{res['task']}.json"
    p.write_text(json.dumps(res, indent=1, sort_keys=True))
    return p


def outcomes(date: str) -> dict[str, dict]:
    """Every recorded outcome for a date — what the alarm reads."""
    d = ROOT / "state" / OUT_DIRNAME / str(date)
    out: dict[str, dict] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        obj = _load(p)
        if isinstance(obj, dict) and obj.get("task"):
            out[str(obj["task"])] = obj
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", choices=TASKS)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--date", default=datetime.now(timezone.utc)
                    .strftime("%Y%m%d"))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the verdict, write nothing")
    args = ap.parse_args()
    if not args.task and not args.all:
        ap.error("give --task or --all")
    tasks = TASKS if args.all else (args.task,)

    failed = 0
    for t in tasks:
        res = evaluate(t, args.date)
        if not args.dry_run:
            record(res)
        mark = {"ok": "OK", "not_required": "n/a", "pending": "pending",
                "FAILED_NO_ARTIFACT": "FAILED"}[res["status"]]
        print(f"[watchdog] {t:<10} {mark:<7} found={res['found'] or '[]'}")
        if res["status"] == "FAILED_NO_ARTIFACT":
            failed += 1
            print(f"::error title=chatgpt-{t}-no-artifact::{res['headline']}")
        elif res.get("partial"):
            print(f"::warning title=chatgpt-{t}-partial::response.json landed "
                  f"but DONE did not — nothing renders without DONE.")
    if failed:
        print(f"[watchdog] {failed} ChatGPT task(s) left no artifact for "
              f"{args.date}. This is a REPORTED FAILURE, not an idle day.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
