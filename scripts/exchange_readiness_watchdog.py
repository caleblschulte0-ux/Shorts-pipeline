#!/usr/bin/env python3
"""Phase A readiness watchdog — force a bundle to exist, don't hope for one.

Doctor finding 5187e34e11f3: `exchange_phase_a.yml` has exactly one trigger
independent of upstream authoring activity — `workflow_run` and `push` both
require something upstream to have already run — a single
`schedule: cron: '45 9 * * *'`. That file's own comments record GitHub cron
drift measured in HOURS, and on 2026-08-29 and 2026-08-30 the ChatGPT media
worker reached its handoff with no bundle and no Phase A artifact at all for
the day. A `schedule:` trigger is subject to GitHub's cron-scan delay; a
`workflow_dispatch` REST call is not — it is an ordinary API call that starts
a run immediately. This watchdog is woken by its own schedule (so it can
itself drift), but the moment it runs it does the one thing a passive cron
cannot: check whether a bundle exists, and if not, DISPATCH Phase A directly
and WAIT for that run to finish, instead of hoping the next cron scan lands
on time.

Fail-closed and idempotent:
  * a bundle already present is a silent no-op (the common case, every day
    Phase A ran on time) — nothing is written, nothing is committed;
  * anything else (dispatch rejected, the dispatched run never found, it
    times out, or it completes without success) is written as a durable,
    named refusal to exchange/bundles/<date>/PHASE_A_WATCHDOG.json and the
    script exits 1, so the day is visibly red in Actions instead of the
    silent green exit that made 2026-08-29/30 invisible there;
  * a dispatched run that completes successfully is ALSO recorded (status
    "recovered" or "run_succeeded_no_bundle") — a day the watchdog had to
    save is worth a record even when it worked.

    python scripts/exchange_readiness_watchdog.py --date 20260830 \\
        --repo owner/repo --token $GH_TOKEN
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import exchange_bundle as xb              # noqa: E402
from shared.fsutil import atomic_write_json           # noqa: E402

API = "https://api.github.com"
PHASE_A_WORKFLOW = "exchange_phase_a.yml"
OUTCOME_FILENAME = "PHASE_A_WATCHDOG.json"

# Statuses that mean "the day is fine" — no durable refusal, exit 0.
OK_STATUSES = {"already_ready", "recovered", "run_succeeded_no_bundle"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def bundle_ready(date: str) -> bool:
    """True once Phase A has actually produced a bundle for this date."""
    return xb.read_bundle(date) is not None


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"}


def dispatch_phase_a(repo: str, token: str, date: str, channel: str,
                     *, session) -> tuple[bool, str]:
    """POST workflow_dispatch for Phase A. Returns (ok, detail)."""
    url = f"{API}/repos/{repo}/actions/workflows/{PHASE_A_WORKFLOW}/dispatches"
    body = {"ref": "main",
            "inputs": {"date": str(date), "channel": channel}}
    try:
        resp = session.post(url, headers=_headers(token), json=body, timeout=30)
    except Exception as exc:                              # noqa: BLE001
        return False, f"dispatch request raised: {exc}"
    if resp.status_code != 204:
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    return True, "dispatched"


def _find_dispatched_run(repo: str, token: str, dispatched_at: str,
                         *, session) -> dict | None:
    """Best-effort: the newest workflow_dispatch run for Phase A created at
    or after `dispatched_at`. None if nothing matching has shown up yet —
    GitHub's runs list can lag a live dispatch by a few seconds."""
    url = (f"{API}/repos/{repo}/actions/workflows/{PHASE_A_WORKFLOW}/runs"
           f"?event=workflow_dispatch&per_page=10")
    try:
        resp = session.get(url, headers=_headers(token), timeout=30)
    except Exception:                                     # noqa: BLE001
        return None
    if resp.status_code != 200:
        return None
    since = _parse_iso(dispatched_at)
    runs = (resp.json() or {}).get("workflow_runs") or []
    candidates = []
    for run in runs:
        created = run.get("created_at")
        if not created:
            continue
        try:
            if _parse_iso(created.replace("+00:00", "Z")) >= since:
                candidates.append(run)
        except Exception:                                  # noqa: BLE001
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("created_at") or "")
    return candidates[0]


def _get_run(repo: str, token: str, run_id: int, *, session) -> dict | None:
    url = f"{API}/repos/{repo}/actions/runs/{run_id}"
    try:
        resp = session.get(url, headers=_headers(token), timeout=30)
    except Exception:                                      # noqa: BLE001
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


def _await_dispatched_run(repo: str, token: str, dispatched_at: str, *,
                          session, timeout_s: int, poll_interval_s: int,
                          sleep_fn=time.sleep, clock=time.monotonic) -> dict:
    """Poll until the dispatched run is found and completed, or `timeout_s`
    elapses. Returns a dict; {"status": "timeout"} on expiry, {"status":
    "not_found"} if the run itself never showed up in time, otherwise the
    run resource with an added "status" key mirroring GitHub's own
    (queued/in_progress/completed)."""
    deadline = clock() + timeout_s
    run = None
    while clock() < deadline:
        if run is None:
            run = _find_dispatched_run(repo, token, dispatched_at,
                                       session=session)
            if run is None:
                sleep_fn(poll_interval_s)
                continue
        fresh = _get_run(repo, token, run["id"], session=session) or run
        if fresh.get("status") == "completed":
            return fresh
        run = fresh
        sleep_fn(poll_interval_s)
    if run is None:
        return {"status": "not_found"}
    return {"status": "timeout", "id": run.get("id"),
            "html_url": run.get("html_url")}


def run_watchdog(date: str, channel: str, repo: str, token: str, *,
                 session, timeout_s: int = 1800, poll_interval_s: int = 20,
                 sleep_fn=time.sleep, clock=time.monotonic) -> dict:
    """The full decision. Pure aside from the injected `session`/`sleep_fn`/
    `clock`, so the branches are testable without a real network or a real
    30-minute wait."""
    if bundle_ready(date):
        return {"status": "already_ready", "date": date}

    dispatched_at = _utcnow_iso()
    ok, detail = dispatch_phase_a(repo, token, date, channel, session=session)
    if not ok:
        return {"status": "dispatch_failed", "date": date, "detail": detail}

    result = _await_dispatched_run(
        repo, token, dispatched_at, session=session, timeout_s=timeout_s,
        poll_interval_s=poll_interval_s, sleep_fn=sleep_fn, clock=clock)

    if result.get("status") == "not_found":
        return {"status": "run_not_found", "date": date}
    if result.get("status") == "timeout":
        return {"status": "timeout", "date": date, "run_id": result.get("id"),
                "run_url": result.get("html_url")}

    conclusion = result.get("conclusion")
    run_id, run_url = result.get("id"), result.get("html_url")
    if conclusion != "success":
        return {"status": "run_failed", "date": date, "run_id": run_id,
                "run_url": run_url, "conclusion": conclusion}

    if bundle_ready(date):
        return {"status": "recovered", "date": date, "run_id": run_id,
                "run_url": run_url}
    # A successful Phase A run can legitimately write no bundle when there is
    # genuinely nothing to ask any channel for — that is documented as a
    # valid, successful outcome in exchange_phase_a.py's own docstring, not a
    # failure this watchdog should manufacture.
    return {"status": "run_succeeded_no_bundle", "date": date,
            "run_id": run_id, "run_url": run_url}


def write_outcome(date: str, outcome: dict) -> Path:
    path = xb.bundle_dir(date) / OUTCOME_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, {**outcome, "checked_at": _utcnow_iso()})
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True)
    ap.add_argument("--channel", default="trending")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--token", default=os.environ.get("GH_TOKEN", ""))
    ap.add_argument("--timeout", type=int, default=1800,
                    help="seconds to wait for a dispatched Phase A run")
    ap.add_argument("--poll-interval", type=int, default=20)
    args = ap.parse_args()

    if bundle_ready(args.date):
        print(f"[watchdog] bundle already exists for {args.date} — no action")
        return 0

    if not args.repo or not args.token:
        print("::error::--repo/--token (or GITHUB_REPOSITORY/GH_TOKEN) "
              "required to dispatch Phase A")
        outcome = {"status": "dispatch_failed", "date": args.date,
                   "detail": "no repo/token available to the watchdog"}
        path = write_outcome(args.date, outcome)
        print(f"[watchdog] wrote {path.relative_to(ROOT)}: {outcome['status']}")
        return 1

    import requests
    session = requests.Session()

    print(f"[watchdog] no bundle for {args.date} — dispatching Phase A "
          f"and waiting up to {args.timeout}s")
    outcome = run_watchdog(args.date, args.channel, args.repo, args.token,
                           session=session, timeout_s=args.timeout,
                           poll_interval_s=args.poll_interval)

    path = write_outcome(args.date, outcome)
    print(f"[watchdog] wrote {path.relative_to(ROOT)}: {outcome['status']}")

    if outcome["status"] not in OK_STATUSES:
        print(f"::error::Phase A readiness watchdog failed for {args.date}: "
              f"{outcome['status']} — {json.dumps(outcome)}")
        return 1
    print(f"[watchdog] {args.date} is ready ({outcome['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
