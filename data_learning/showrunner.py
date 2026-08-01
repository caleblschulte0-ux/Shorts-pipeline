#!/usr/bin/env python3
"""THE SHOWRUNNER — the quality memory that makes each video better than the last.

Every render is already judged: the interest judge measures dead time / appeal,
the cool judge raises hands (LONG_HOLD, DULL, LOW_MOTION, STILL_WHEN_MOTION_EXISTS,
FRAGMENT_OF_THE_SPECTACLE), the motion-first gate logs when it fell back to a
still, continuity checks reuse. But those verdicts used to EVAPORATE — video #50
was no smarter than video #1.

The Showrunner is the spine that remembers. It:

  1. RECORDS every render's verdicts into a persistent ledger
     (quality_memory/ledger.jsonl — one line per render).
  2. LEARNS the recurring failures — a beat JOB that keeps getting flagged, a
     subject that keeps failing to find motion, whether dead-time is trending down
     — and writes them as RULES (quality_memory/rules.json).
  3. ADVISES the next render — given a story's beats, it surfaces the learned
     warnings BEFORE the render burns, so the author/planner fixes the thing that
     bit the last N videos instead of rediscovering it.

This is how "improve the quality of the video over time" becomes mechanical
rather than aspirational: the lessons compound in a file, not in someone's head.

CLI:
  python -m data_learning.showrunner record --slug hurricane --label v9 \
        --interest <interest_dir> --cool <cool_dir> --log <render.log>
  python -m data_learning.showrunner learn          # rebuild rules.json
  python -m data_learning.showrunner advise <story.beats.json>
  python -m data_learning.showrunner report          # human summary
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MEM = Path(__file__).resolve().parent / "quality_memory"
LEDGER = MEM / "ledger.jsonl"
RULES = MEM / "rules.json"

# a cool-judge / interest hand that we track failure-rates for, per beat JOB
TRACKED_FLAGS = ("LONG_HOLD", "DULL", "LOW_MOTION", "STILL_WHEN_MOTION_EXISTS",
                 "FRAGMENT_OF_THE_SPECTACLE")
# a pattern is a RULE once it bites this often across at least MIN_RENDERS renders
FLAG_RATE = 0.5
MIN_RENDERS = 2


# ---- 1. RECORD -----------------------------------------------------------
def _read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def _ingest_interest(d: Path) -> dict:
    j = _read_json(d / "interest.json") if d else None
    if not j:
        return {}
    keep = ("duration", "dead_fraction", "mean_appeal", "hook_appeal",
            "bland_fraction", "mean_novelty", "variety_scenes", "hook_weak")
    return {k: j[k] for k in keep if k in j}


def _ingest_cool(d: Path) -> list[dict]:
    rows = _read_json(d / "cool_prescreen.json") if d else None
    if not isinstance(rows, list):
        return []
    return [{"job": r.get("job", ""), "motion": r.get("motion"),
             "appeal": r.get("appeal"), "hold_s": r.get("hold_s"),
             "suspect": r.get("suspect", [])} for r in rows]


_FALLBACK_RE = re.compile(r"no moving clip cleared the bar for '([^']+)'")
_MOTION_WIN_RE = re.compile(r"MOTION WINS for '([^']+)'")


def _ingest_log(p: Path) -> dict:
    if not p or not p.exists():
        return {}
    txt = p.read_text(errors="ignore")
    return {
        "motion_fallbacks": sorted(set(_FALLBACK_RE.findall(txt))),
        "motion_wins": sorted(set(_MOTION_WIN_RE.findall(txt))),
        "continuity_ok": "continuity OK" in txt,
    }


def record(slug: str, label: str, interest: Path | None,
           cool: Path | None, log: Path | None) -> dict:
    MEM.mkdir(parents=True, exist_ok=True)
    prior = _load_ledger()
    rec = {"seq": len(prior) + 1, "slug": slug, "label": label,
           "metrics": _ingest_interest(interest),
           "beats": _ingest_cool(cool), **_ingest_log(log)}
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def _load_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for ln in LEDGER.read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return out


# ---- 2. LEARN ------------------------------------------------------------
def learn() -> dict:
    """Scan the ledger, distil recurring failures into RULES, and persist them."""
    led = _load_ledger()
    n = len(led)
    rules: list[dict] = []

    # (a) per-JOB flag rates: a job whose beats keep raising the same hand
    job_flag: dict[tuple[str, str], int] = {}
    job_seen: dict[str, int] = {}
    for rec in led:
        seen_jobs, seen_pairs = set(), set()
        for b in rec.get("beats", []):
            job = (b.get("job") or "?").upper()
            seen_jobs.add(job)
            for f in b.get("suspect", []):
                if f in TRACKED_FLAGS:
                    seen_pairs.add((job, f))
        for j in seen_jobs:
            job_seen[j] = job_seen.get(j, 0) + 1
        for pair in seen_pairs:
            job_flag[pair] = job_flag.get(pair, 0) + 1
    for (job, flag), hits in sorted(job_flag.items()):
        seen = job_seen.get(job, 0)
        if seen >= MIN_RENDERS and hits / seen >= FLAG_RATE:
            rules.append({
                "scope": "job", "job": job, "flag": flag,
                "severity": "hard" if hits == seen else "soft",
                "rate": f"{hits}/{seen}",
                "guidance": _guidance(job, flag)})

    # (b) subjects that keep failing to find MOTION -> a real access need
    fb_count: dict[str, int] = {}
    for rec in led:
        for s in rec.get("motion_fallbacks", []):
            fb_count[s] = fb_count.get(s, 0) + 1
    access = [{"subject": s, "renders": c} for s, c in
              sorted(fb_count.items(), key=lambda kv: -kv[1]) if c >= MIN_RENDERS]

    # (c) is quality actually trending the right way?
    trend = _trend(led)

    out = {"generated_from_n_renders": n, "rules": rules,
           "access_needs": access, "trend": trend,
           "motion_wins": sorted({w for r in led for w in r.get("motion_wins", [])})}
    MEM.mkdir(parents=True, exist_ok=True)
    RULES.write_text(json.dumps(out, indent=2))
    return out


def _guidance(job: str, flag: str) -> str:
    if flag == "LONG_HOLD":
        return (f"{job} beats keep holding too long — cap max_unchanged and split "
                "into develop phases, or cut the beat shorter.")
    if flag == "DULL":
        return (f"{job} beats keep scoring low appeal — a designed card is getting "
                "scrolled; reach for footage or a 3D showpiece instead of a flat "
                "graphic.")
    if flag == "LOW_MOTION":
        return (f"{job} beats keep sitting near-frozen — pick a more dynamic window "
                "or add a real camera move.")
    if flag == "STILL_WHEN_MOTION_EXISTS":
        return (f"{job} beats keep landing on a still where a clip should exist — "
                "give the beat a motion_query/subject so the motion-first gate can "
                "find moving footage (see MOTION_FIRST.md).")
    if flag == "FRAGMENT_OF_THE_SPECTACLE":
        return (f"{job} beats keep cropping to a fragment — show the WHOLE spectacle "
                "(the cool judge's canonical fail).")
    return "recurring flag — investigate."


def _trend(led: list[dict]) -> dict:
    """First vs latest recorded value for the metrics that define quality."""
    def series(key):
        return [(r["label"], r["metrics"][key]) for r in led
                if isinstance(r.get("metrics"), dict) and key in r["metrics"]]
    out = {}
    for key, better in (("dead_fraction", "down"), ("mean_appeal", "up"),
                        ("bland_fraction", "down")):
        s = series(key)
        if len(s) >= 2:
            first, last = s[0][1], s[-1][1]
            if last == first:
                direction = "holding"
            elif (last < first) == (better == "down"):
                direction = "improving"
            else:
                direction = "regressing"
            out[key] = {"first": first, "latest": last,
                        "want": better, "direction": direction}
    return out


# ---- 3. ADVISE -----------------------------------------------------------
def advise(beats_path: Path) -> list[dict]:
    """Given a story's beats, surface the learned warnings that apply — BEFORE the
    render burns. Matches each beat's JOB against the learned per-job rules and the
    access-need list."""
    rules = _read_json(RULES) or {}
    by_job: dict[str, list[dict]] = {}
    for r in rules.get("rules", []):
        by_job.setdefault(r.get("job", ""), []).append(r)
    access = {a["subject"]: a for a in rules.get("access_needs", [])}

    story = _read_json(beats_path) or {}
    beats = story.get("beats", story if isinstance(story, list) else [])
    warnings: list[dict] = []
    for i, b in enumerate(beats):
        job = (b.get("job") or "").upper()
        for r in by_job.get(job, []):
            warnings.append({"beat": i, "job": job, "severity": r["severity"],
                             "flag": r["flag"], "rate": r["rate"],
                             "guidance": r["guidance"]})
        subj = b.get("subject") or (b.get("image") or {}).get("query", "")
        if subj in access:
            warnings.append({"beat": i, "job": job, "severity": "access",
                             "flag": "MOTION_UNAVAILABLE",
                             "rate": f"{access[subj]['renders']} renders",
                             "guidance": f"'{subj}' has never found motion — a "
                             "stock-video key (PEXELS_API_KEY/PIXABAY_API_KEY) "
                             "would let the motion-first gate pull a moving clip."})
    return warnings


# ---- CLI -----------------------------------------------------------------
def _fmt_report(rules: dict) -> str:
    lines = [f"SHOWRUNNER — learned from {rules.get('generated_from_n_renders',0)} "
             "renders", ""]
    tr = rules.get("trend", {})
    if tr:
        lines.append("QUALITY TREND (first -> latest):")
        for k, v in tr.items():
            tag = {"improving": "improving", "holding": "holding",
                   "regressing": "REGRESSING"}[v["direction"]]
            lines.append(f"  {k}: {v['first']} -> {v['latest']} "
                         f"(want {v['want']}) — {tag}")
        lines.append("")
    if rules.get("rules"):
        lines.append("LEARNED RULES:")
        for r in rules["rules"]:
            lines.append(f"  [{r['severity'].upper()}] {r['job']} / {r['flag']} "
                         f"({r['rate']}): {r['guidance']}")
        lines.append("")
    if rules.get("access_needs"):
        lines.append("ACCESS NEEDS (subjects that never found motion):")
        for a in rules["access_needs"]:
            lines.append(f"  '{a['subject']}' — {a['renders']} renders")
        lines.append("")
    if rules.get("motion_wins"):
        lines.append(f"MOTION WINS on record: {len(rules['motion_wins'])} subjects")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--slug", required=True)
    r.add_argument("--label", required=True)
    r.add_argument("--interest", type=Path)
    r.add_argument("--cool", type=Path)
    r.add_argument("--log", type=Path)
    sub.add_parser("learn")
    a = sub.add_parser("advise")
    a.add_argument("beats", type=Path)
    sub.add_parser("report")
    args = ap.parse_args(argv)

    if args.cmd == "record":
        rec = record(args.slug, args.label, args.interest, args.cool, args.log)
        print(f"[showrunner] recorded {args.slug}/{args.label} "
              f"(seq {rec['seq']}) — {len(rec['beats'])} beats, "
              f"{len(rec.get('motion_fallbacks', []))} motion fallbacks")
        learn()
        return 0
    if args.cmd == "learn":
        rules = learn()
        print(_fmt_report(rules))
        return 0
    if args.cmd == "advise":
        ws = advise(args.beats)
        if not ws:
            print("[showrunner] no learned warnings apply to this story.")
            return 0
        print(f"[showrunner] {len(ws)} learned warning(s) for {args.beats.name}:")
        for w in ws:
            print(f"  beat {w['beat']} [{w['severity']}] {w['job']}/{w['flag']} "
                  f"({w['rate']}): {w['guidance']}")
        return 0
    if args.cmd == "report":
        print(_fmt_report(_read_json(RULES) or {}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
