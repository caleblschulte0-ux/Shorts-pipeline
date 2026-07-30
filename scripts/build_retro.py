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


def _vid(v: dict) -> str:
    """Stable identity for a video. Falls back to the URL, then the title —
    never to an index, which shifts as the analytics window slides."""
    return str(v.get("video_id") or v.get("url") or v.get("title") or "")


def metric(v: dict, key: str):
    """A metric, or None if the API did not report it.

    MISSING IS NOT ZERO. `likes: null` means YouTube gave us nothing;
    `likes: 0` means nobody liked it. Collapsing the two invents evidence —
    a reviewer would read a whole cohort of unreported retention as a
    catastrophic retention problem."""
    val = v.get(key)
    return None if val is None else val


def _vph(v: dict) -> float:
    age = max(float(v.get("age_hours") or 0), 1.0)
    return round(float(v.get("views") or 0) / age, 4)


def percentile_in(value: float, population: list[float]) -> float | None:
    """Where `value` sits in `population`, 0-100. None if too few samples.

    Uses the MIDRANK of ties, not "strictly below". With ten zero-view
    videos, a strictly-below count puts every one of them at p0 — reading
    as "worst on the channel" when the honest answer is "exactly average
    for this cohort, which is zero". Midrank gives them p50."""
    pop = sorted(p for p in population if p is not None)
    if len(pop) < MIN_SAMPLES:
        return None
    below = sum(1 for p in pop if p < value)
    equal = sum(1 for p in pop if p == value)
    return round(100.0 * (below + 0.5 * equal) / len(pop), 1)



# Ages at which a cohort is worth comparing. A 2-hour-old upload and a
# 7-day-old one are different questions; reporting them together is how a
# reviewer concludes "today was great" every single day.
MATURITY_CHECKPOINTS = [("24h", 20, 30), ("72h", 60, 84), ("7d", 156, 192)]
# A verdict on editorial quality needs a video old enough to have been seen.
MATURE_HOURS = 20


def cohort_at(videos: list[dict], lo: float, hi: float,
              fmt: str | None = None) -> dict:
    """Videos currently inside an age window — the only fair comparison.

    `fmt` narrows to one format, because a graph_race baseline does not
    judge a reddit_story. Cross-format comparison needs an argument, so the
    brief makes the same-format number the easy one to reach for."""
    sel = [v for v in videos if lo <= float(v.get("age_hours") or 0) < hi
           and (fmt is None or v.get("_fmt") == fmt)]
    if not sel:
        return {"n": 0, "note": "no videos in this age window"}
    vph = sorted(v["_vph"] for v in sel)
    got = [v for v in sel if v.get("avg_view_pct") is not None]
    return {
        "n": len(sel),
        "median_vph": round(statistics.median(vph), 4),
        "median_views": round(statistics.median(
            float(v.get("views") or 0) for v in sel), 1),
        "median_view_pct": (round(statistics.median(
            float(v["avg_view_pct"]) for v in got), 1) if got else None),
        "view_pct_reported_for": f"{len(got)}/{len(sel)}",
        "enough_to_judge": len(sel) >= MIN_SAMPLES,
    }


def format_of(v: dict) -> str:
    """Best-effort format tag so cohorts can stay within a format."""
    for key in ("format", "experiment_arm", "series"):
        val = v.get(key)
        if val:
            return str(val)
    return "unknown"


# Not every bad number is an editorial failure, and treating them alike is
# how a reviewer "learns" that viewers hated an idea the pipeline never
# actually published. The brief separates the classes so a proposal has to
# pick one.
PROBLEM_CLASSES = {
    "audience_performance": "real viewers saw it and did not stay",
    "editorial_quality": "the idea or the writing was weak",
    "packaging": "title, thumbnail or hook did not earn the click",
    "media_quality": "the visuals were wrong, generic or repeated",
    "pipeline_failure": "render, upload or gate failed — viewers never "
                        "judged this at all",
    "insufficient_data": "too young, too few samples, or the metric was "
                         "not reported",
}


def channel_report(name: str, path: str, today: str) -> dict:
    data = _load(ROOT / path)
    if not isinstance(data, dict):
        return {"channel": name, "available": False,
                "note": f"no analytics at {path}"}
    videos = [v for v in (data.get("videos") or []) if isinstance(v, dict)]
    for v in videos:
        v["_vph"] = _vph(v)
        v["_band"] = band_of(float(v.get("age_hours") or 0))
        v["_fmt"] = format_of(v)

    # Historical distribution per band — the yardstick today is measured on.
    # Keyed by (video_id, vph) so a video can be excluded from its own
    # comparison by IDENTITY. Excluding by VALUE deleted every other video
    # sharing that number — and on a channel where most videos sit at 0
    # views, that removed nearly the whole population and left the survivor
    # looking like a top performer against 1 peer.
    by_band: dict[str, list[tuple[str, float]]] = {}
    for v in videos:
        by_band.setdefault(v["_band"], []).append((_vid(v), v["_vph"]))

    def _published_on(v: dict, day: str) -> bool:
        return str(v.get("published_at") or "")[:10].replace("-", "") == day

    todays = [v for v in videos if _published_on(v, today)]
    rows = []
    for v in sorted(todays, key=lambda x: x.get("published_at") or ""):
        band = v["_band"]
        me = _vid(v)
        peers = [val for vid, val in by_band.get(band, []) if vid != me]
        pct = percentile_in(v["_vph"], peers)
        rows.append({
            "title": v.get("title"),
            "url": v.get("url"),
            "published_at": v.get("published_at"),
            "age_hours": v.get("age_hours"),
            "age_band": band,
            "views": metric(v, "views"),
            "engaged_views": metric(v, "engaged_views"),
            "likes": metric(v, "likes"),
            "comments": metric(v, "comments"),
            "avg_view_pct": metric(v, "avg_view_pct"),
            "avg_view_duration": metric(v, "avg_view_duration"),
            "impressions": metric(v, "impressions"),
            "ctr": metric(v, "ctr"),
            "missing_metrics": [k for k in
                                ("avg_view_pct", "avg_view_duration",
                                 "impressions", "ctr", "likes", "comments")
                                if v.get(k) is None],
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
        # Age-matched cohorts — compare these, not raw totals.
        "maturity": {
            label: {"all_formats": cohort_at(videos, lo, hi),
                    "by_format": {f: cohort_at(videos, lo, hi, f)
                                  for f in sorted({v["_fmt"] for v in videos})}}
            for label, lo, hi in MATURITY_CHECKPOINTS},
        "mature_enough_to_judge": [
            {"title": v.get("title"), "vph": v["_vph"], "fmt": v["_fmt"],
             "age_hours": v.get("age_hours")}
            for v in sorted(videos, key=lambda x: -x["_vph"])
            if float(v.get("age_hours") or 0) >= MATURE_HOURS][:5],
        "worst_mature": [
            {"title": v.get("title"), "vph": v["_vph"], "fmt": v["_fmt"],
             "age_hours": v.get("age_hours")}
            for v in sorted(videos, key=lambda x: x["_vph"])
            if float(v.get("age_hours") or 0) >= MATURE_HOURS][:5],
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
        "problem_classes": PROBLEM_CLASSES,
        "how_to_read_this": {
            "classify_before_you_propose": (
                "Pick a `problem_class` first. A render that failed or an "
                "upload that never went public is a pipeline_failure — NOT "
                "evidence that viewers rejected the idea. A null metric is "
                "insufficient_data, not a zero."),
            "compare_like_with_like": (
                "Use `channels.<n>.maturity` — cohorts at ~24h, ~72h and "
                "~7d, and within a format. A graph_race baseline does not "
                "judge a reddit_story unless you argue why it does."),
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


def executive_summary(brief: dict) -> str:
    """The version a human reads in 30 seconds.

    Deliberately NOT the analytics dump — that is `brief.md`, and nobody
    reads it daily. This answers: is anything broken, is anything moving,
    and is anything waiting on me."""
    d = brief["date"]
    L = [f"# Daily summary — {d}", ""]

    # 1. Is the machine healthy? A pipeline failure outranks every content
    #    observation, because a video that never published was not judged.
    h = brief.get("pipeline_health") or {}
    fails = str(h.get("consecutive_failures", "0"))
    broken = []
    if fails not in ("0", "unknown"):
        broken.append(f"{fails} consecutive daily-run failure(s)")
    ex_ = h.get("exchange") or {}
    if ex_.get("note"):
        broken.append("the ChatGPT exchange did not complete")
    if (ex_.get("media") or {}).get("unfilled"):
        broken.append(f"{ex_['media']['unfilled']} shot(s) shipped with no media")
    bank = h.get("reserve_bank") or {}
    if bank.get("low_on"):
        broken.append(f"reserve bank low on {', '.join(bank['low_on'])}")
    L += ["## Health", ""]
    L += [f"- {b}" for b in broken] or ["- nothing broken"]
    L.append("")

    # 2. Channels, judged only on videos old enough to judge.
    L += ["## Channels (mature videos only)", ""]
    for name, c in (brief.get("channels") or {}).items():
        if not c.get("available"):
            L.append(f"- **{name}**: no analytics")
            continue
        m = (c.get("maturity") or {}).get("24h", {}).get("all_formats", {})
        n = m.get("n", 0)
        if not n:
            L.append(f"- **{name}**: nothing in the 24h window yet")
            continue
        best = (c.get("mature_enough_to_judge") or [{}])[0]
        worst = (c.get("worst_mature") or [{}])[0]
        L.append(f"- **{name}**: {n} video(s) at ~24h, median "
                 f"{m.get('median_views')} views"
                 + ("" if m.get("enough_to_judge") else " _(thin)_"))
        if best.get("title"):
            L.append(f"    - best: {str(best['title'])[:60]} "
                     f"({best.get('vph')} vph)")
        if worst.get("title") and worst.get("title") != best.get("title"):
            L.append(f"    - worst: {str(worst['title'])[:60]} "
                     f"({worst.get('vph')} vph)")
    L.append("")

    # 3. What is actually in flight.
    cont = brief.get("continuity") or {}
    live = (cont.get("experiments") or {}).get("running") or []
    L += ["## Experiments", ""]
    L += [f"- `{e['id']}` — {e['hypothesis'][:60]} ({e['blocked_by']})"
          for e in live] or ["- none running"]
    L.append("")

    verdicts = cont.get("my_verdicts_on_your_last_proposals") or []
    if verdicts:
        L += ["## Claude's last decisions", ""]
        for v in verdicts[-5:]:
            L.append(f"- **{str(v.get('verdict', '?')).upper()}** "
                     f"{v.get('title')}"
                     + (f" (`{v['commit'][:8]}`)" if v.get("commit") else ""))
        L.append("")

    # 4. The only section Caleb has to act on.
    owed = brief.get("what_you_owe_today") or {}
    needs_you = [i for i in (owed.get("items") or [])
                 if i.get("kind") == "agenda"]
    stale = [e for e in live if "days" in str(e.get("blocked_by", ""))
             and e.get("days", 0) > 30]
    L += ["## Needs Caleb", ""]
    if not needs_you and not stale and not broken:
        L.append("- nothing")
    else:
        L += [f"- {i['what'][:110]}" for i in needs_you]
        L += [f"- experiment `{e['id']}` has been open {e['days']}d with no "
              f"verdict" for e in stale]
        L += [f"- {b}" for b in broken]
    L.append("")
    return "\n".join(L)


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
    (out / "summary.md").write_text(executive_summary(brief))
    (out / "proposals").mkdir(exist_ok=True)
    (out / "proposals" / ".gitkeep").touch()
    print(f"\n[retro] wrote {(out / 'brief.json').relative_to(ROOT)} "
          f"({len(json.dumps(brief)):,} bytes)")
    print(f"[retro] summary at {(out / 'summary.md').relative_to(ROOT)}")
    print(f"[retro] the reviewer writes retro/{date}/proposals.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
