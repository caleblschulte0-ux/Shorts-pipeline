#!/usr/bin/env python3
"""Build the day's RETRO BRIEF — the evidence pack the reviewer reasons over.

Once a day, after the last slot has posted, this assembles everything needed
to answer "how did we do, and what should change" into one file. ChatGPT
reads it, writes PROPOSALS into `retro/<date>/proposals/`, and a human-or-
Claude review decides what actually ships. Nothing here changes the pipeline.

    python scripts/build_retro.py                    # today, write it
    python scripts/build_retro.py --date 20260731
    python scripts/build_retro.py --dry-run --json

Why a generated brief instead of "go read the repo": a reviewer given raw
files invents narratives. A reviewer given matched-age cohorts, explicit
sample sizes, and a "what we cannot tell you" section argues from evidence.

THE AGE PROBLEM, handled explicitly. Views-per-hour flatters a 2-hour-old
video and buries a 3-week-old one, so a naive daily comparison always
concludes "today was great". Every comparison here is WITHIN an age band,
and today's videos are scored as a percentile against the historical
distribution *at the same age*. A video too young to judge is reported as
too young, not as a win.

Writes:
    retro/<date>/brief.json     machine-readable, what ChatGPT reads
    retro/<date>/brief.md       human-readable, same content
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RETRO_ROOT = ROOT / "retro"
STATE = ROOT / "state"

# Age bands. A video is only ever compared with others in its own band —
# see the module docstring.
AGE_BANDS = [
    ("0-6h", 0, 6), ("6-24h", 6, 24), ("1-3d", 24, 72),
    ("3-7d", 72, 168), ("1-4w", 168, 672), ("4w+", 672, 10 ** 9),
]
# Below this many samples a band's statistics are noise. Reported, but
# flagged so the reviewer does not build a theory on two videos.
MIN_SAMPLES = 5

CHANNELS = {
    "trending": "state/analytics/latest.json",
    "explainer": "state/analytics_explainer/latest.json",
    "curiosity": "state/analytics_curiosity/latest.json",
    "third": "state/analytics_third/latest.json",
}


def _load(path: Path | str, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:                                # noqa: BLE001
        return default


def _sh(*args: str) -> str:
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:                                # noqa: BLE001
        return ""


def band_of(age_hours: float) -> str:
    for name, lo, hi in AGE_BANDS:
        if lo <= age_hours < hi:
            return name
    return AGE_BANDS[-1][0]


def _vph(v: dict) -> float:
    age = max(float(v.get("age_hours") or 0), 1.0)
    return round(float(v.get("views") or 0) / age, 4)


def percentile_in(value: float, population: list[float]) -> float | None:
    """Where `value` sits in `population`, 0-100. None if too few samples."""
    pop = sorted(p for p in population if p is not None)
    if len(pop) < MIN_SAMPLES:
        return None
    below = sum(1 for p in pop if p < value)
    return round(100.0 * below / len(pop), 1)


def channel_report(name: str, path: str, today: str) -> dict:
    data = _load(ROOT / path)
    if not isinstance(data, dict):
        return {"channel": name, "available": False,
                "note": f"no analytics at {path}"}
    videos = [v for v in (data.get("videos") or []) if isinstance(v, dict)]
    for v in videos:
        v["_vph"] = _vph(v)
        v["_band"] = band_of(float(v.get("age_hours") or 0))

    # Historical distribution per band — the yardstick today is measured on.
    by_band: dict[str, list[float]] = {}
    for v in videos:
        by_band.setdefault(v["_band"], []).append(v["_vph"])

    def _published_on(v: dict, day: str) -> bool:
        return str(v.get("published_at") or "")[:10].replace("-", "") == day

    todays = [v for v in videos if _published_on(v, today)]
    rows = []
    for v in sorted(todays, key=lambda x: x.get("published_at") or ""):
        band = v["_band"]
        peers = [p for p in by_band.get(band, []) if p != v["_vph"]]
        pct = percentile_in(v["_vph"], peers)
        rows.append({
            "title": v.get("title"),
            "url": v.get("url"),
            "published_at": v.get("published_at"),
            "age_hours": v.get("age_hours"),
            "age_band": band,
            "views": v.get("views"),
            "engaged_views": v.get("engaged_views"),
            "likes": v.get("likes"),
            "comments": v.get("comments"),
            "views_per_hour": v["_vph"],
            "percentile_vs_same_age": pct,
            "verdict": ("too young to judge" if float(v.get("age_hours") or 0) < 2
                        else "no comparable history" if pct is None
                        else "top quartile" if pct >= 75
                        else "bottom quartile" if pct <= 25 else "middling"),
        })

    def _window(hours: float) -> dict:
        sel = [v for v in videos if float(v.get("age_hours") or 0) <= hours]
        if not sel:
            return {"videos": 0}
        views = [float(v.get("views") or 0) for v in sel]
        return {
            "videos": len(sel),
            "total_views": int(sum(views)),
            "median_views": round(statistics.median(views), 1),
            "median_vph": round(statistics.median(v["_vph"] for v in sel), 4),
            "best": max(sel, key=lambda v: v["_vph"]).get("title"),
            "worst": min(sel, key=lambda v: v["_vph"]).get("title"),
        }

    return {
        "channel": name, "available": True,
        "fetched_at": data.get("fetched_at"),
        "today": rows,
        "last_7d": _window(168),
        "last_30d": _window(720),
        "all_time_summary": data.get("summary") or {},
        "band_sample_sizes": {b: len(v) for b, v in sorted(by_band.items())},
        "thin_bands": [b for b, v in by_band.items() if len(v) < MIN_SAMPLES],
    }


def pipeline_health(today: str) -> dict:
    """Did the machine work, separately from whether the videos landed?"""
    out: dict = {}
    out["consecutive_failures"] = (
        (STATE / "failure_count.txt").read_text().strip()
        if (STATE / "failure_count.txt").exists() else "unknown")

    b = _load(ROOT / "exchange" / "bundles" / today / "phase_b_report.json")
    if b:
        out["exchange"] = {"media": b.get("media"), "punchup": b.get("punchup"),
                           "done_marker": b.get("done_marker"),
                           "authored": b.get("authored")}
    else:
        out["exchange"] = {"note": f"no phase_b_report for {today} — the "
                                   f"exchange did not complete"}

    a = _load(ROOT / "exchange" / "bundles" / today / "authored_report.json")
    if a:
        out["chatgpt_takeover"] = {"promoted": len(a.get("promoted") or []),
                                   "rejected": a.get("rejected") or []}

    try:
        from shared import package_buffer as buf
        out["reserve_bank"] = {f: len(v) for f, v in buf.inventory().items()}
        out["reserve_bank"]["low_on"] = buf.low_formats()
    except Exception as exc:                         # noqa: BLE001
        out["reserve_bank"] = {"error": str(exc)[:80]}

    verdicts = STATE / "showrunner_verdicts.jsonl"
    if verdicts.exists():
        lines = [json.loads(l) for l in verdicts.read_text().splitlines()
                 if l.strip()][-40:]
        out["showrunner"] = {
            "recent": len(lines),
            "blocks": sum(1 for v in lines if v.get("verdict") == "BLOCK"),
            "avg_score": round(statistics.mean(
                [float(v.get("score") or 0) for v in lines]), 1) if lines else None,
        }
    else:
        out["showrunner"] = {"note": "no verdicts logged yet"}

    census = _load(STATE / "failure_census.json")
    if census:
        out["failure_census"] = census
    return out


def repo_state(since_days: int = 1) -> dict:
    since = (datetime.now(timezone.utc)
             - timedelta(days=since_days)).strftime("%Y-%m-%d")
    commits = _sh("git", "log", f"--since={since}", "--oneline",
                  "--no-merges").splitlines()
    return {
        "head": _sh("git", "rev-parse", "--short", "HEAD"),
        "commits_since": since,
        "commit_count": len(commits),
        "commits": commits[:40],
        "test_files": sorted(p.name for p in (ROOT / "tests").glob("test_*.py")),
        "open_ticket_docs": [d.name for d in (ROOT / "docs").glob("*.md")
                             if "REGISTRY" in d.name or "ACQUISITION" in d.name],
    }



def continuity(date: str) -> dict:
    """Yesterday's verdicts, the running experiments, and what is OWED today.

    Without this the loop has no memory: declined ideas come back in new
    clothes, adopted changes are never read out, and every day starts from
    zero. This section is what makes the reviewer's job "continue the work"
    rather than "have an opinion about today"."""
    sys.path.insert(0, str(ROOT / "scripts"))
    out: dict = {}
    try:
        from retro_reply import read_agenda, read_ledger
        ledger = read_ledger()
        out["my_verdicts_on_your_last_proposals"] = [
            {"date": r.get("date"), "title": r.get("title"),
             "verdict": r.get("verdict"), "because": r.get("because"),
             "shipped": r.get("shipped"),
             "experiment_id": r.get("experiment_id")}
            for r in ledger[-12:]]
        out["decision_history"] = {
            "total": len(ledger),
            "adopted": sum(1 for r in ledger if r.get("verdict") == "adopt"),
            "declined": sum(1 for r in ledger if r.get("verdict") == "decline"),
        }
        out["open_agenda"] = read_agenda().get("open") or []
    except Exception as exc:                         # noqa: BLE001
        out["ledger_error"] = str(exc)[:100]

    try:
        from shared import experiments as ex
        due = ex.refresh_due()
        out["experiments"] = ex.summary()
        out["readouts_due"] = [
            {"id": e["id"], "hypothesis": e["hypothesis"],
             "metric": e["metric"], "direction": e["direction"],
             "baseline": e["baseline"], "guardrail": e.get("guardrail"),
             "started": e["started_at"], "days": ex.days_elapsed(e),
             "what_to_do": ("Read this out. Compare `metric` now against "
                            "`baseline`, check the guardrail did not slip, "
                            "and propose adopt / revert / extend with the "
                            "numbers.")}
            for e in due or [e for e in ex.running()
                             if e.get("status") == "readout_due"]]
    except Exception as exc:                         # noqa: BLE001
        out["experiments_error"] = str(exc)[:100]
    return out


def obligations(cont: dict, channels: dict) -> dict:
    """What the reviewer OWES today. An empty retro is only legitimate when
    this comes back empty — see retro/README.md.

    The channel is meant to improve without supervision, which means the
    default is work, not agreement. `nothing to change` on a day with a
    readout due or an open agenda item is the loop quietly dying."""
    items = []
    for r in cont.get("readouts_due") or []:
        items.append({"kind": "readout", "ref": r["id"], "must": True,
                      "what": f"Experiment '{r['hypothesis']}' has closed its "
                              f"window — read it out with numbers."})
    for a in cont.get("open_agenda") or []:
        items.append({"kind": "agenda", "ref": a.get("proposal_file")
                      or a.get("title"), "must": True,
                      "what": f"I asked for: {a.get('what_i_need') or a.get('title')}"})
    live = (cont.get("experiments") or {}).get("running") or []
    if not live:
        items.append({"kind": "no_live_experiment", "ref": None, "must": True,
                      "what": "Nothing is being tested right now. Propose an "
                              "experiment: a specific change, the metric it "
                              "should move, and the window to judge it over."})
    thin = [n for n, c in channels.items()
            if c.get("available") and c.get("thin_bands")]
    if thin:
        items.append({"kind": "coverage", "ref": ",".join(thin), "must": False,
                      "what": "Some age bands are too thin to judge. Worth a "
                              "`watch` note on what would give us signal."})
    return {
        "count": len(items),
        "must_do": sum(1 for i in items if i["must"]),
        "items": items,
        "an_empty_retro_is_only_ok_if": (
            "must_do is 0. Otherwise 'nothing needs changing' means the loop "
            "stopped working, not that the channel is finished."),
    }


def build(date: str) -> dict:
    channels = {n: channel_report(n, p, date) for n, p in CHANNELS.items()}
    posted_today = sum(len(c.get("today") or []) for c in channels.values()
                       if c.get("available"))
    cont = continuity(date)
    owed = obligations(cont, channels)
    return {
        "schema": "shorts-retro-brief/v1",
        "date": date,
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "how_to_read_this": {
            "age_matters": ("Every video is compared ONLY against videos of "
                            "the same age band. `percentile_vs_same_age` is "
                            "the honest signal; raw `views` is not, because "
                            "a 2-hour-old short and a 3-week-old short are "
                            "not comparable."),
            "sample_size": (f"Bands listed in `thin_bands` have fewer than "
                            f"{MIN_SAMPLES} samples. Do not build a theory "
                            f"on them — say the data is thin instead."),
            "channel_scale": ("This channel is small. Single-digit view "
                              "counts are normal and mostly noise. Prefer "
                              "explanations that survive that fact over "
                              "ones that require a 9-view video to mean "
                              "something."),
        },
        "posted_today": posted_today,
        "continuity": cont,
        "what_you_owe_today": owed,
        "standing_directive": (
            "You are not a helper that comments on a dashboard — you are the "
            "channel's editor-in-residence, and the job is that it gets "
            "better every week without anyone asking. Continue yesterday's "
            "work: read out what is due, answer what I asked for, and always "
            "have something running. A day with nothing to change is a real "
            "outcome ONLY when `what_you_owe_today.must_do` is 0."),
        "channels": channels,
        "pipeline_health": pipeline_health(date),
        "repo": repo_state(),
        "your_job": "retro/README.md",
    }


def to_markdown(brief: dict) -> str:
    L = [f"# Retro — {brief['date']}", "",
         f"generated {brief['generated_at']} · {brief['posted_today']} "
         f"video(s) posted today", ""]
    for name, c in brief["channels"].items():
        if not c.get("available"):
            L += [f"## {name}", f"_{c.get('note')}_", ""]
            continue
        L += [f"## {name}", ""]
        if c["today"]:
            L.append("| video | age | views | vph | vs same age |")
            L.append("|---|---|---|---|---|")
            for r in c["today"]:
                pct = ("—" if r["percentile_vs_same_age"] is None
                       else f"p{r['percentile_vs_same_age']:.0f}")
                L.append(f"| {str(r['title'])[:44]} | {r['age_hours']}h | "
                         f"{r['views']} | {r['views_per_hour']} | "
                         f"{pct} · {r['verdict']} |")
        else:
            L.append("_nothing published today_")
        w, m = c["last_7d"], c["last_30d"]
        L += ["", f"- 7d: {w.get('videos', 0)} videos, "
                  f"median {w.get('median_views', 0)} views",
              f"- 30d: {m.get('videos', 0)} videos, "
              f"median {m.get('median_views', 0)} views"]
        if c["thin_bands"]:
            L.append(f"- thin data (<{MIN_SAMPLES}): "
                     f"{', '.join(c['thin_bands'])}")
        L.append("")
    owed = brief.get("what_you_owe_today") or {}
    if owed.get("items"):
        L += ["## What you owe today", ""]
        for i in owed["items"]:
            L.append(f"- {'**MUST**' if i['must'] else 'optional'} "
                     f"[{i['kind']}] {i['what']}")
        L.append("")
    cont = brief.get("continuity") or {}
    verdicts = cont.get("my_verdicts_on_your_last_proposals") or []
    if verdicts:
        L += ["## My verdicts on your last proposals", ""]
        for v in verdicts[-6:]:
            L.append(f"- **{v.get('verdict', '?').upper()}** — "
                     f"{v.get('title')}")
            if v.get("because"):
                L.append(f"    - {v['because']}")
        L.append("")
    live = (cont.get("experiments") or {}).get("running") or []
    if live:
        L += ["## Running experiments", ""]
        for e in live:
            L.append(f"- `{e['id']}` — {e['hypothesis']}")
            L.append(f"    - {e['days']}d, {e['samples']} samples, "
                     f"needs {e['needs']} · {e['blocked_by']}")
        L.append("")

    h = brief["pipeline_health"]
    L += ["## Pipeline health", "",
          f"- consecutive failures: {h.get('consecutive_failures')}",
          f"- exchange: {json.dumps(h.get('exchange'))[:200]}",
          f"- reserve bank: {json.dumps(h.get('reserve_bank'))[:160]}",
          f"- showrunner: {json.dumps(h.get('showrunner'))[:160]}", "",
          "## Repo", "",
          f"- HEAD {brief['repo']['head']}, "
          f"{brief['repo']['commit_count']} commit(s) since "
          f"{brief['repo']['commits_since']}", ""]
    L += ["Write proposals per `retro/README.md`. Nothing you write is "
          "applied automatically.", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default="",
                    help="YYYYMMDD (default: today UTC)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    date = args.date or datetime.now(timezone.utc).strftime("%Y%m%d")
    brief = build(date)

    if args.json:
        print(json.dumps(brief, indent=2)[:6000])
    else:
        print(to_markdown(brief))

    if args.dry_run:
        print("\n[retro] dry run — nothing written")
        return 0

    out = RETRO_ROOT / date
    out.mkdir(parents=True, exist_ok=True)
    (out / "brief.json").write_text(json.dumps(brief, indent=2) + "\n")
    (out / "brief.md").write_text(to_markdown(brief))
    (out / "proposals").mkdir(exist_ok=True)
    (out / "proposals" / ".gitkeep").touch()
    print(f"\n[retro] wrote {(out / 'brief.json').relative_to(ROOT)} "
          f"({len(json.dumps(brief)):,} bytes)")
    print(f"[retro] proposals go in {(out / 'proposals').relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
