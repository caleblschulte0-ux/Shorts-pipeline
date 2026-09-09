#!/usr/bin/env python3
"""Did the retro loop actually produce the day's review?

`retro.yml` marks the analytics refresh, the experiment advance, the failure
census, the brief build and the triage `continue-on-error: true` — correctly,
for the first three: a failed analytics call must not stop the loop, and a
stale brief still beats no brief. But the commit step that follows was
fail-closed only around whatever files happened to exist, so
`build_retro.py` and `review_proposals.py` could BOTH fail while
`ci_commit_state.sh` found older state to commit and the workflow finished
green (doctor finding 694ab7c3e1d4).

A missing daily review then looks exactly like a quiet day. That is the
failure mode this whole repo keeps relearning: a workflow reporting on the
steps it ran rather than the outcome it produced.

So the outputs are checked, by name, for the resolved date:

    nightly   retro/<date>/brief.json + brief.md + triage.json
    triage    retro/<date>/triage.json

`--mode nightly` is what the schedule runs; `--mode triage` is the
proposals-push path, which deliberately does not rebuild the brief (that
would move the evidence out from under the proposals just written against
it), so it requires only the triage.

Exits 1 and names what is missing. The workflow runs this AFTER the commit
step so the diagnostics that do exist are preserved and the run is
retryable — a red run with its evidence committed is worth far more than a
red run that threw the evidence away.

    python3 scripts/retro_gate.py --date 20260909 --mode nightly
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETRO_ROOT = ROOT / "retro"

REQUIRED = {
    "nightly": ("brief.json", "brief.md", "triage.json"),
    "triage": ("triage.json",),
}


def _problems(date: str, mode: str, root: Path | None = None) -> list[str]:
    out: list[str] = []
    base = (root or RETRO_ROOT) / str(date)
    if not base.is_dir():
        return [f"retro/{date}/ does not exist — the day produced nothing"]
    for name in REQUIRED[mode]:
        p = base / name
        if not p.exists():
            out.append(f"missing retro/{date}/{name}")
            continue
        if p.stat().st_size == 0:
            out.append(f"retro/{date}/{name} is empty")
            continue
        if not name.endswith(".json"):
            continue
        try:
            doc = json.loads(p.read_text())
        except Exception as exc:                         # noqa: BLE001
            out.append(f"retro/{date}/{name} is not valid JSON: {exc}")
            continue
        if not isinstance(doc, dict):
            out.append(f"retro/{date}/{name} is not an object")
            continue
        # The date INSIDE the file, not just the folder it landed in: a
        # rerun that resolved a different date and wrote elsewhere would
        # otherwise be indistinguishable from success.
        stamped = str(doc.get("date") or "")
        if stamped and stamped != str(date):
            out.append(f"retro/{date}/{name} is stamped {stamped!r}, "
                       f"not {date} — this is another day's file")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True)
    ap.add_argument("--mode", choices=sorted(REQUIRED), default="nightly")
    args = ap.parse_args(argv)

    problems = _problems(args.date, args.mode)
    if problems:
        for p in problems:
            print(f"::error::retro {args.mode} produced no review: {p}")
        print(f"[retro-gate] FAILED for {args.date} ({args.mode}) — "
              f"{len(problems)} problem(s). Whatever the run did produce has "
              f"already been committed; rerun once the cause is fixed.")
        return 1
    print(f"[retro-gate] ok — {args.date} ({args.mode}) has "
          f"{', '.join(REQUIRED[args.mode])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
