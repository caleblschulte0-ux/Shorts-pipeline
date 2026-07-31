#!/usr/bin/env python3
"""My half of the conversation — verdicts back to the reviewer, with reasons.

The retro loop is a collaboration, not a suggestion box. The reviewer reads
the evidence and proposes; I decide, implement what I agree with, and write
back WHY — including why I declined the rest. Tomorrow's brief opens with
those verdicts, so the reviewer starts from what we settled instead of
re-litigating it.

A one-way loop degrades fast: unanswered proposals get repeated, declined
ideas come back in new clothes, and the reviewer never learns the channel's
actual constraints. The ledger is the memory that stops that.

    # what did it send me?
    python scripts/retro_reply.py --date 20260731 --list

    # decide, with reasoning it will read tomorrow
    python scripts/retro_reply.py --date 20260731 --file 01-graph-hook.json \
        --verdict adopt --because "Shipped at 0.9s not 0.8 — 0.8 clipped the
        second line on 3 of 6 test renders." --shipped make_graph_race.py \
        --experiment "Shorter graph hooks hold better" \
        --metric graph_race.avg_view_pct --direction up --baseline 81.5

    python scripts/retro_reply.py --date 20260731 --file 04-vague.json \
        --verdict decline --because "No numbers. Re-propose with a
        percentile from the brief and I will look again."

Verdicts: adopt | revise | decline | needs_evidence | deferred

Writes:
    retro/state/ledger.jsonl     append-only; every verdict ever
    retro/state/agenda.json      carried-forward open items
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RETRO_ROOT = ROOT / "retro"
STATE = RETRO_ROOT / "state"
LEDGER = STATE / "ledger.jsonl"
AGENDA = STATE / "agenda.json"

VERDICTS = ("adopt", "revise", "decline", "needs_evidence", "deferred",
            "rollback")
# Verdicts that leave something open for the reviewer to pick up tomorrow.
KEEPS_AGENDA = ("revise", "needs_evidence", "deferred")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _head_sha() -> str:
    """The commit the decision was recorded at. Without this, "adopted" is
    an assertion; with it, the change is findable."""
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              timeout=10).stdout.strip()[:12]
    except Exception:                                # noqa: BLE001
        return ""


def _signature(p: dict) -> str:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from review_proposals import signature
        return signature(p)
    except Exception:                                # noqa: BLE001
        return ""


def read_ledger(limit: int | None = None) -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:                        # noqa: BLE001
                continue
    return rows[-limit:] if limit else rows


def append_ledger(entry: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def read_agenda() -> dict:
    try:
        return json.loads(AGENDA.read_text())
    except Exception:                                # noqa: BLE001
        return {"open": []}


def write_agenda(a: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = AGENDA.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(a, indent=2) + "\n")
    tmp.replace(AGENDA)


def cmd_list(args) -> int:
    pdir = RETRO_ROOT / args.date / "proposals"
    if not pdir.is_dir():
        print(f"no proposals for {args.date}")
        return 0
    answered = {r.get("proposal_file") for r in read_ledger()
                if r.get("date") == args.date}
    for f in sorted(pdir.glob("*.json")):
        try:
            p = json.loads(f.read_text())
        except Exception:                            # noqa: BLE001
            print(f"  [unreadable] {f.name}")
            continue
        mark = "answered" if f.name in answered else "OPEN    "
        print(f"  {mark}  {f.name}")
        print(f"            {p.get('title')}")
        print(f"            {str(p.get('proposal') or '')[:110]}")
    return 0


def cmd_reply(args) -> int:
    pdir = RETRO_ROOT / args.date / "proposals"
    path = pdir / args.file
    proposal = {}
    if path.exists():
        try:
            proposal = json.loads(path.read_text())
        except Exception:                            # noqa: BLE001
            pass
    elif not args.force:
        print(f"ERROR: {path} does not exist (use --force to reply anyway)",
              file=sys.stderr)
        return 2

    # A DURABLE DECISION RECORD, not just a verdict. Everything needed to
    # reconstruct what was decided, what actually shipped, and how to undo
    # it — six months from now, by someone who was not here.
    entry = {
        "at": _now(), "date": args.date, "proposal_file": args.file,
        "proposal_id": proposal.get("proposal_id"),
        "signature": proposal.get("signature") or _signature(proposal),
        "title": proposal.get("title") or args.file,
        "category": proposal.get("category"),
        "channel": args.channel or proposal.get("channel"),
        "format": args.format or proposal.get("format"),
        "verdict": args.verdict,
        "because": args.because,
        "shipped": args.shipped or [],
        "commit": args.commit or _head_sha(),
        "modified_from_proposal": args.modified,
        "rollback": args.rollback or proposal.get("rollback"),
        "experiment_id": None,
    }

    # An adopted change that claims a measurable effect becomes a REGISTERED
    # EXPERIMENT, not a fire-and-forget edit. That is what makes the loop
    # accumulate: in a week the register demands a readout whether or not
    # anyone remembers this conversation.
    if args.experiment:
        if args.baseline is None or not args.metric:
            print("ERROR: --experiment needs --metric and --baseline",
                  file=sys.stderr)
            return 2
        from shared import experiments as ex
        e = ex.register(
            args.experiment, change=args.because or "(see ledger)",
            metric=args.metric, direction=args.direction,
            baseline=args.baseline, files=args.shipped or [],
            guardrail=args.guardrail or "",
            guardrail_baseline=args.guardrail_baseline,
            min_days=args.min_days, min_samples=args.min_samples,
            proposal_file=args.file,
            channel=args.channel or proposal.get("channel") or "",
            format=args.format or proposal.get("format") or "")
        entry["experiment_id"] = e["id"]
        print(f"[reply] registered experiment {e['id']} — readout in "
              f"{args.min_days}d / {args.min_samples} samples")

    append_ledger(entry)

    agenda = read_agenda()
    agenda.setdefault("open", [])
    agenda["open"] = [i for i in agenda["open"]
                      if i.get("proposal_file") != args.file]
    if args.verdict in KEEPS_AGENDA:
        agenda["open"].append({
            "raised": args.date, "proposal_file": args.file,
            "title": entry["title"], "verdict": args.verdict,
            "what_i_need": args.because})
    write_agenda(agenda)

    print(f"[reply] {args.verdict.upper()} — {entry['title']}")
    print(f"[reply] the reviewer reads this in tomorrow's brief")
    return 0


def cmd_agenda(args) -> int:
    a = read_agenda()
    if args.add:
        a.setdefault("open", []).append(
            {"raised": args.date, "title": args.add,
             "verdict": "operator_item", "what_i_need": args.because or ""})
        write_agenda(a)
        print(f"[agenda] added: {args.add}")
        return 0
    if not a.get("open"):
        print("agenda is empty — a `watch`-only retro is legitimate today")
        return 0
    for i in a["open"]:
        print(f"  [{i.get('verdict')}] {i.get('title')}")
        if i.get("what_i_need"):
            print(f"      needs: {i['what_i_need']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default=datetime.now(timezone.utc)
                    .strftime("%Y%m%d"))
    ap.add_argument("--list", action="store_true",
                    help="show the day's proposals and which are unanswered")
    ap.add_argument("--agenda", action="store_true",
                    help="show carried-forward open items")
    ap.add_argument("--add", help="add an operator item to the agenda")
    ap.add_argument("--file", help="proposal filename to answer")
    ap.add_argument("--verdict", choices=VERDICTS)
    ap.add_argument("--because", default="",
                    help="your reasoning — the reviewer reads this verbatim")
    ap.add_argument("--shipped", nargs="*", help="files you actually changed")
    ap.add_argument("--commit", default="",
                    help="implementation SHA (default: current HEAD)")
    ap.add_argument("--modified", default="",
                    help="how your implementation differs from what was "
                         "proposed — the reviewer learns most from this")
    ap.add_argument("--rollback", default="",
                    help="how to undo it")
    ap.add_argument("--channel", default="")
    ap.add_argument("--format", default="")
    ap.add_argument("--force", action="store_true")
    # experiment registration
    ap.add_argument("--experiment", help="hypothesis; registers a timed test")
    ap.add_argument("--metric", help="metric the experiment moves")
    ap.add_argument("--direction", default="up", choices=("up", "down"))
    ap.add_argument("--baseline", type=float)
    ap.add_argument("--guardrail", default="")
    ap.add_argument("--guardrail-baseline", type=float)
    ap.add_argument("--min-days", type=int, default=7)
    ap.add_argument("--min-samples", type=int, default=10)
    args = ap.parse_args()

    if args.list:
        return cmd_list(args)
    if args.agenda or args.add:
        return cmd_agenda(args)
    if not (args.file and args.verdict):
        ap.error("need --file and --verdict (or --list / --agenda)")
    return cmd_reply(args)


if __name__ == "__main__":
    sys.exit(main())
