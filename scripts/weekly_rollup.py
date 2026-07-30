#!/usr/bin/env python3
"""Weekly rollup — the patterns a daily view structurally cannot see.

A daily reviewer sees one day and asks "what changed?". Some of the most
expensive problems on a channel are invisible at that resolution because
they are slopes, not events: a format decaying over three weeks, the same
hook shape recycled until it stops working, media repeating across videos,
a channel drifting off its own doctrine, experiments that keep landing
inconclusive because they are underpowered.

None of those produce a bad DAY. They produce a bad month.

    python scripts/weekly_rollup.py
    python scripts/weekly_rollup.py --weeks 4 --json

Writes retro/weekly/<YYYY-Www>.json + .md. Read-only over the briefs and
the ledger; never blocks anything.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

RETRO_ROOT = ROOT / "retro"
OUT_DIR = RETRO_ROOT / "weekly"
DATE_DIR = re.compile(r"^\d{8}$")
# A slope needs points. Under this many briefs, say so rather than drawing
# a trend line through three dots.
MIN_BRIEFS = 4


def recent_briefs(days: int) -> list[dict]:
    out = []
    for d in sorted((p for p in RETRO_ROOT.iterdir()
                     if p.is_dir() and DATE_DIR.match(p.name)),
                    key=lambda p: p.name)[-days:]:
        try:
            out.append(json.loads((d / "brief.json").read_text()))
        except Exception:                            # noqa: BLE001
            continue
    return out


def format_fatigue(briefs: list[dict]) -> list[dict]:
    """A format whose mature median is sliding across the window.

    Fatigue is the thing a daily read never catches: each day looks like
    noise, and the slope only exists across weeks."""
    series: dict[tuple, list[float]] = {}
    for b in briefs:
        for chan, c in (b.get("channels") or {}).items():
            for label, cohort in (c.get("maturity") or {}).items():
                for fmt, stats in (cohort.get("by_format") or {}).items():
                    if stats.get("median_vph") is None:
                        continue
                    series.setdefault((chan, fmt, label), []).append(
                        float(stats["median_vph"]))
    out = []
    for (chan, fmt, label), vals in series.items():
        if len(vals) < MIN_BRIEFS:
            continue
        half = len(vals) // 2
        early, late = vals[:half], vals[half:]
        if not early or not late:
            continue
        a, b_ = statistics.median(early), statistics.median(late)
        if a > 0 and (b_ - a) / a <= -0.25:
            out.append({"channel": chan, "format": fmt, "cohort": label,
                        "from": round(a, 4), "to": round(b_, 4),
                        "change_pct": round(100 * (b_ - a) / a, 1),
                        "n_briefs": len(vals)})
    return sorted(out, key=lambda x: x["change_pct"])


def hook_patterns(briefs: list[dict]) -> dict:
    """Repeated opening shapes across the week's worst performers — the
    'every title is a question' problem nobody notices day to day."""
    worst = []
    for b in briefs:
        for c in (b.get("channels") or {}).values():
            worst += [w.get("title") or "" for w in (c.get("worst_mature") or [])]
    starts = Counter(" ".join(t.split()[:2]).lower() for t in worst if t)
    return {"repeated_openers": [{"opener": k, "count": v}
                                 for k, v in starts.most_common(5) if v > 1],
            "sampled": len(worst)}


def experiment_health() -> dict:
    try:
        from shared import experiments as ex
    except Exception as exc:                         # noqa: BLE001
        return {"error": str(exc)[:80]}
    exps = ex.all_experiments()
    concluded = [e for e in exps if e.get("status") in
                 ("adopted", "reverted", "inconclusive")]
    inconclusive = [e for e in concluded if e["status"] == "inconclusive"]
    note = None
    if concluded and len(inconclusive) / len(concluded) >= 0.6:
        note = (f"{len(inconclusive)}/{len(concluded)} experiments came back "
                f"inconclusive — the changes being tested are probably too "
                f"small to detect at this volume. Test bigger swings, or "
                f"raise min_samples.")
    return {"total": len(exps),
            "running": len(ex.running()),
            "stale": [e["id"] for e in ex.stale()],
            "concluded": len(concluded),
            "inconclusive": len(inconclusive),
            "adopted": sum(1 for e in concluded if e["status"] == "adopted"),
            "reverted": sum(1 for e in concluded if e["status"] == "reverted"),
            "underpowered_warning": note}


def decision_health() -> dict:
    try:
        from retro_reply import read_ledger
        rows = read_ledger()
    except Exception:                                # noqa: BLE001
        return {}
    v = Counter(r.get("verdict") for r in rows)
    recent = rows[-20:]
    note = None
    if recent and v.get("adopt", 0) == 0:
        note = ("nothing has been adopted recently — either the proposals "
                "are not good enough or the bar is set where nothing passes. "
                "Both are worth naming.")
    return {"total_decisions": len(rows), "by_verdict": dict(v),
            "note": note}


def build(weeks: int) -> dict:
    briefs = recent_briefs(weeks * 7)
    now = datetime.now(timezone.utc)
    return {
        "schema": "shorts-retro-weekly/v1",
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "week": now.strftime("%G-W%V"),
        "briefs_analysed": len(briefs),
        "enough_data": len(briefs) >= MIN_BRIEFS,
        "format_fatigue": format_fatigue(briefs),
        "hook_patterns": hook_patterns(briefs),
        "experiments": experiment_health(),
        "decisions": decision_health(),
        "what_this_is_for": (
            "Slopes, not events. Format decay, recycled hooks, repeated "
            "media, channel drift, and underpowered experiments do not "
            "produce a bad DAY — they produce a bad month, which is why "
            "the daily review cannot see them."),
    }


def to_md(r: dict) -> str:
    L = [f"# Weekly rollup — {r['week']}", "",
         f"{r['briefs_analysed']} daily brief(s) analysed", ""]
    if not r["enough_data"]:
        L += [f"_Fewer than {MIN_BRIEFS} briefs — too early for trends. "
              f"This is a note, not a finding._", ""]
    if r["format_fatigue"]:
        L += ["## Format fatigue", ""]
        for f in r["format_fatigue"]:
            L.append(f"- **{f['channel']}/{f['format']}** at {f['cohort']}: "
                     f"{f['change_pct']}% ({f['from']} -> {f['to']}, "
                     f"n={f['n_briefs']})")
        L.append("")
    hp = r["hook_patterns"]
    if hp.get("repeated_openers"):
        L += ["## Repeated openers among weak performers", ""]
        for o in hp["repeated_openers"]:
            L.append(f"- \"{o['opener']}…\" x{o['count']}")
        L.append("")
    e = r["experiments"]
    L += ["## Experiments", "",
          f"- {e.get('running', 0)} running, {e.get('concluded', 0)} concluded "
          f"({e.get('adopted', 0)} adopted, {e.get('reverted', 0)} reverted, "
          f"{e.get('inconclusive', 0)} inconclusive)"]
    if e.get("stale"):
        L.append(f"- **stale, blocking a slot:** {', '.join(e['stale'])}")
    if e.get("underpowered_warning"):
        L.append(f"- {e['underpowered_warning']}")
    d = r["decisions"]
    if d.get("note"):
        L += ["", f"## Decisions", "", f"- {d['note']}"]
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        r = build(args.weeks)
    except Exception as exc:                         # noqa: BLE001
        print(f"::warning::weekly rollup failed ({exc}) — not fatal")
        return 0
    print(json.dumps(r, indent=2) if args.json else to_md(r))
    if not args.dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{r['week']}.json").write_text(json.dumps(r, indent=2) + "\n")
        (OUT_DIR / f"{r['week']}.md").write_text(to_md(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
