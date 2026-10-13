#!/usr/bin/env python3
"""When will the next video be up? Reads what the posting run reports.

    python scripts/run_eta.py              # explainer
    python scripts/run_eta.py --channel explainer --json

The run writes its progress to the `run-progress` branch at every step
(`shared/run_progress.py`); this prints it in Central time, with the run's
hard stop from the workflow's own `timeout-minutes`. Read-only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from shared import run_progress  # noqa: E402

CENTRAL = ZoneInfo("America/Chicago")
WORKFLOW = {"explainer": "explainer.yml"}
PHASE_WORDS = {"prep": "checking the script", "render": "drawing and rendering",
               "review": "being reviewed", "upload": "uploading"}


def _clock(t: datetime) -> str:
    return t.astimezone(CENTRAL).strftime("%-I:%M %p")


def _timeout_min(workflow: str) -> int | None:
    try:
        txt = (REPO / ".github" / "workflows" / workflow).read_text()
        m = re.search(r"timeout-minutes:\s*(\d+)", txt)
        return int(m.group(1)) if m else None
    except OSError:
        return None


def _gh(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                       timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else None


def _job_started(run_id: str) -> tuple[str | None, datetime | None]:
    run = _gh(f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}")
    jobs = _gh(f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs") or {}
    starts = [j.get("started_at") for j in jobs.get("jobs", [])
              if j.get("started_at") and j.get("status") == "in_progress"]
    st = max(starts) if starts else None
    return ((run or {}).get("status"),
            datetime.fromisoformat(st.replace("Z", "+00:00")) if st else None)


def describe(state: dict, *, now: float | None = None,
             run_status: str | None = None,
             hard_stop: datetime | None = None) -> str:
    now = time.time() if now is None else now
    nowdt = datetime.fromtimestamp(now, timezone.utc)
    if not state:
        return "No posting run has reported progress yet."
    posted = [d for d in state.get("done", []) if d.get("outcome") == "posted"]
    held = [d for d in state.get("done", []) if d.get("outcome") != "posted"
            and "render" in (d.get("phases") or {})]
    lines = []
    if state.get("ended") or run_status == "completed":
        lines.append(f"The last run has finished: {len(posted)} posted, "
                     f"{len(held)} held.")
        for d in posted:
            lines.append(f"  posted {d['slug']}: {d.get('url')}")
        return "\n".join(lines)
    eta = run_progress.estimate(state, now)
    cur = state.get("current") or {}
    lines.append(f"Running since {_clock(datetime.fromisoformat(state['run_started']))}"
                 f" Central: {len(posted)} posted, {len(held)} held so far.")
    if cur.get("slug"):
        mins = (now - cur.get("phase_since", now)) / 60
        lines.append(f"Now: {cur['slug']} is {PHASE_WORDS.get(cur.get('phase'), cur.get('phase'))}"
                     f" ({mins:.0f} min so far).")
        done_at = nowdt + timedelta(minutes=eta["this_story_min"])
        lines.append(f"If it passes, it's up around {_clock(done_at)}.")
    nxt = nowdt + timedelta(minutes=eta["next_post_min"])
    lines.append(f"Best guess for the next post: {_clock(nxt)} "
                 f"(about {eta['post_rate']:.0%} of stories pass review; "
                 f"a full story takes about {eta['full_story_min']} min).")
    if hard_stop:
        lines.append(f"The run stops by {_clock(hard_stop)} at the latest.")
        if nxt > hard_stop:
            lines.append("The guess is past the stop, so the next video may "
                         "come from the next run.")
    for d in posted:
        lines.append(f"  posted {d['slug']}: {d.get('url')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="explainer")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    state = run_progress._read_remote(f"{a.channel}.json")
    status = stop = None
    if state.get("run_id"):
        status, started = _job_started(state["run_id"])
        tmo = _timeout_min(WORKFLOW.get(a.channel, ""))
        if started and tmo:
            stop = started + timedelta(minutes=tmo)
    if a.json:
        print(json.dumps({"state": state, "run_status": status,
                          "hard_stop": stop.isoformat() if stop else None,
                          "eta": run_progress.estimate(state)}, indent=1))
    else:
        print(describe(state, run_status=status, hard_stop=stop))
    return 0


if __name__ == "__main__":
    sys.exit(main())
