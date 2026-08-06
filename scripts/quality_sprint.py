#!/usr/bin/env python3
"""THE SPRINT LOOP — five renders that are allowed to teach five things.

The problem this replaces. Five renders of one story on 2026-08-01/02, 2.5-4.5
hours each. Between them, one change apiece, chosen by whatever the last blind
judge complained about loudest. Two of the five made the film worse and nobody
could know until the next video existed. Net movement over twelve hours of
compute: 4.0 -> 3.0.

The loop that produced that was: guess, render, judge, guess again. Every step
cost hours and taught one thing, and nothing carried forward except my memory
of it.

What this does instead, per candidate change:

    1  score the plan            (milliseconds, offline)   shared/film_metrics
    2  compare against the last recorded render            film_metrics.compare
    3  REFUSE it if it trips a guard                       film_metrics.guard
    4  only then spend a render
    5  judge blind, record plan + verdict together         film_metrics.record
    6  after 5, ask whether the window actually improved   film_metrics.trend

Steps 1-3 are free and would have stopped both regressions. Step 6 is the
difference between "it feels better" and a table.

    python scripts/quality_sprint.py status      # where the sprint stands
    python scripts/quality_sprint.py check SLUG  # score this plan, gate it
    python scripts/quality_sprint.py next        # what the EVIDENCE says to fix
    python scripts/quality_sprint.py record SLUG --pkg DIR --note "..."

`next` is the half that improves the CODE rather than the film. A complaint
that appears in one verdict is about one film; a complaint that survives
several renders is about the machine that made them. Choosing the next change
from the single loudest line of the single latest verdict is precisely what
produced two regressions out of five.

`check` exits non-zero when a change is refused, so it can gate a dispatch in
CI or a shell loop without a human reading the output.

WHY `record` STILL EXISTS NOW THAT produce() SELF-RECORDS. A CI canary writes
its ledger row to the RUNNER's disk, which is thrown away with the container —
`state/` is never pushed from CI. So the auto-record covers local and
production runs, and a canary's row still has to be written here, from the
downloaded package:

    python scripts/quality_sprint.py record SLUG --pkg <downloaded>_pkg \
        --note "what changed" --head <sha>

That is not a workaround to tidy up later. It is the one manual step in the
loop, and it is manual because the blind taste verdict is produced by a fresh
subagent that has seen only the evidence package — which is the whole reason
the verdict is worth anything.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import film_metrics as fm  # noqa: E402


def _head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=REPO).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _plan_for(slug: str) -> tuple[list[dict], list[dict]]:
    """The shot plan this slug WOULD render right now — no media, no ffmpeg."""
    from data_learning import planner
    f = REPO / "data_learning" / "pro_stories" / f"{slug}.beats.json"
    beats = json.loads(f.read_text())["beats"]
    # Real narration durations need TTS; a flat 5s per beat is what makes this
    # instant. It is NOT "close enough" — that claim used to be in this
    # comment and it was wrong. Beat length decides how many shots a beat
    # chunks into, so it moves every count, every seconds-weighted fraction,
    # and the cut metrics outright. The numbers are internally consistent and
    # comparable ONLY against another plan scored the same way, which is why
    # they are tagged `estimated` and kept in their own history.
    return planner.plan_story(beats, [5.0] * len(beats)), beats


def cmd_check(args) -> int:
    shots, beats = _plan_for(args.slug)
    now = fm.score_plan(shots, beats, duration_source="estimated")
    print(f"PLAN  {args.slug}: {now['summary']}")

    # The baseline is the last OFFLINE score of this slug, not the last
    # render. Both are real measurements; only one is in the same units. See
    # `film_metrics.score_plan`'s duration_source note — diffing across that
    # boundary reported a REGRESSION on a change that touched no durations at
    # all, and would have refused it.
    rows = fm.snapshots(args.slug)
    refused: list[str] = []
    if not rows:
        print("no prior OFFLINE score for this slug — this run becomes the "
              "baseline for the next one")
    else:
        last = rows[-1]
        cmp = fm.compare(last, now)
        print(f"vs    {last.get('head', '?')[:8]} ({last.get('note', '')})")
        if cmp["verdict"] == "incomparable":
            print(f"      => INCOMPARABLE: {cmp['incomparable']}")
        else:
            for x in cmp["improved"]:
                print(f"  +  {x}")
            for x in cmp["regressed"]:
                print(f"  -  {x}")
            print(f"      => {cmp['verdict']}")
        refused = fm.guard(last, now)
        for r in refused:
            print(f"REFUSED: {r}")

    if not args.no_save and not refused:
        fm.snapshot(args.slug, now, note=args.note or "", head=_head())

    unanchored = fm.unanchored_beats(shots)
    if unanchored:
        print(f"\nADVISORY — {len(unanchored)} shot(s) do not depict their own "
              "line. This is an AUTHORING note, not a repair: the automatic "
              "rewrite was tried on 2026-08-02 and produced word salad.")
        for u in unanchored[:8]:
            print(f"  {u['query']!r}  <-  {u['line'][:60]!r}")
    return 1 if refused else 0


def cmd_record(args) -> int:
    pkg = Path(args.pkg)
    pm = pkg / "plan_metrics.json"
    metrics = json.loads(pm.read_text()) if pm.exists() else {}
    if not metrics:
        print(f"no plan_metrics.json in {pkg} — scoring the story's plan instead")
        shots, beats = _plan_for(args.slug)
        metrics = fm.score_plan(shots, beats)
    verdict = None
    v = pkg / "verdict.json"
    if v.exists():
        verdict = json.loads(v.read_text())
    else:
        print("WARNING: no verdict.json — recording the plan without a score. "
              "A row with no verdict cannot move the trend.")
    fm.record(args.slug, metrics, verdict=verdict, note=args.note,
              head=args.head or _head())
    print(f"recorded {args.slug}: {metrics.get('summary', '')} "
          f"overall={(verdict or {}).get('overall_10')}")
    return 0


def cmd_next(args) -> int:
    """What the evidence says the next change should be ABOUT.

    Not what it should be — that is a judgment. This prints the split between
    complaints that recur across renders (the machine makes them) and
    complaints seen once (that film had them), because choosing from the
    single loudest line of the single latest verdict is what produced two
    regressions in five renders.
    """
    rows = fm.history()
    if args.slug:
        rows = [r for r in rows if r.get("slug") == args.slug]
    rec = fm.recurring_defects(rows, n=args.window)
    print(f"last {rec['window']} renders, {rec['n_judged']} with a taste verdict\n")
    if not rec["recurring"] and not rec["once"]:
        print("no reject labels recorded — either nothing was judged, or the "
              "ledger rows predate verdict capture. Fix that first: a sprint "
              "with no verdicts cannot be measured.")
        return 0
    print(f"RECURRING (>= {rec['threshold']} renders) — these are CODE problems:")
    for lab, heads in rec["recurring"].items():
        print(f"  {len(heads)}x  {lab:<22} {', '.join(heads)}")
    if not rec["recurring"]:
        print("  (none — no defect has yet survived two renders)")
    print("\nSEEN ONCE — these are FILM problems, re-author the beat:")
    for lab, heads in rec["once"].items():
        print(f"  1x   {lab:<22} {heads[0]}")
    if not rec["once"]:
        print("  (none)")
    flat = fm.stagnant(rows, n=args.window)
    if flat:
        print(f"\nSTAGNANT: {flat}")
    return 0


def cmd_status(args) -> int:
    rows = fm.history()
    if not rows:
        print("ledger empty")
        return 0
    print(f"{len(rows)} recorded renders — {fm.LEDGER}\n")
    print(f"{'head':<10}{'figure':>7}{'cards':>7}{'dup':>5}{'unanch':>8}"
          f"{'overall':>9}{'pers':>6}  note")
    for r in rows:
        def g(k, d="-"):
            v = r.get(k)
            return d if v is None else v
        print(f"{str(r.get('head', ''))[:8]:<10}{g('figure_shots'):>7}"
              f"{g('card_fraction'):>7}{g('duplicate_media'):>5}"
              f"{g('unanchored_media'):>8}{g('overall_10'):>9}"
              f"{g('personality'):>6}  {r.get('note', '')}")
    t = fm.trend(rows, n=args.window)
    print()
    if not t.get("enough_data"):
        print(f"TREND: not yet — {t.get('note') or t}")
        print(f"       a {args.window}-render window needs {args.window * 2} "
              "scored renders to compare against the one before it.")
        return 0
    print(f"TREND over {t['window']}: overall {t['prior_overall']} -> "
          f"{t['recent_overall']} ({t['delta_overall']:+}), "
          f"personality {t['prior_personality']} -> {t['recent_personality']} "
          f"=> {t['direction'].upper()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="score a slug's current plan and gate it")
    c.add_argument("slug")
    c.add_argument("--note", default="", help="what changed since the last check")
    c.add_argument("--no-save", action="store_true",
                   help="do not append this score to the offline history")
    c.set_defaults(fn=cmd_check)
    r = sub.add_parser("record", help="add a finished render to the ledger")
    r.add_argument("slug")
    r.add_argument("--pkg", required=True, help="the <out>_pkg directory")
    r.add_argument("--note", default="")
    r.add_argument("--head", default="")
    r.set_defaults(fn=cmd_record)
    n = sub.add_parser("next", help="what the evidence says to work on")
    n.add_argument("slug", nargs="?", default="")
    n.add_argument("--window", type=int, default=5)
    n.set_defaults(fn=cmd_next)
    s = sub.add_parser("status", help="the ledger + whether it is improving")
    s.add_argument("--window", type=int, default=5)
    s.set_defaults(fn=cmd_status)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
