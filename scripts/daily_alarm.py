#!/usr/bin/env python3
"""Did today actually work? The alarm that fires when nothing else does.

Every failure this pipeline has had was SILENT. Not one of them turned a
workflow red:

  * 2026-07-26..28 — three days, zero videos. No alert, no red check.
  * 2026-08-01 — Phase B consumed the wrong day's bundle, applied a
    two-day-old one, exited green, and 16 verified ChatGPT images were
    thrown away.
  * For the channel's whole life — 21 hashtags per upload, which YouTube
    silently discards entirely, and a description that was a bare wall of
    them on four of every six videos.

The pattern is always the same: the pipeline reports on the STEPS it ran,
never on the OUTCOME it produced. A step can succeed at the wrong thing.

So this checks OUTCOMES, from artifacts on disk, against
`config/channel_registry.json`. It is deliberately the last thing to run and
deliberately the only thing allowed to be loud.

    python scripts/daily_alarm.py                 # today, human-readable
    python scripts/daily_alarm.py --json
    python scripts/daily_alarm.py --date 20260801

Exit 0 = the day did what it was supposed to. Exit 1 = at least one alarm.
Never exit non-zero for a reason it cannot evidence — a false alarm teaches
people to ignore the real one.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import channel_registry as reg          # noqa: E402

#: A day is not judged until its last publish slot has had time to land.
#: Publishing runs on Central wall-clock; the last trending slot is 15:30,
#: and a render takes ~an hour, so nothing before ~18:00 Central means
#: anything.
JUDGE_AFTER_HOUR_CENTRAL = 18
CENTRAL = "America/Chicago"


def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:                                    # noqa: BLE001
        return default


def _posted_on(log_path: Path, date: str) -> list[dict]:
    """Entries in a posted log stamped with this production date."""
    log = _load(log_path, {})
    entries = log.get("posted") if isinstance(log, dict) else log
    want = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    out = []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        stamp = str(e.get("posted_at") or e.get("publish_at") or "")
        if stamp.startswith(want):
            out.append(e)
    return out


def _too_early(date: str, now=None) -> bool:
    """Is it still plausibly mid-day for this production date?"""
    try:
        from zoneinfo import ZoneInfo
        now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(CENTRAL))
    except Exception:                                    # noqa: BLE001
        now = now or datetime.now(timezone.utc)
    try:
        day = datetime.strptime(date, "%Y%m%d").date()
    except ValueError:
        return False
    if now.date() > day:
        return False                     # the day is over, judge it
    return now.hour < JUDGE_AFTER_HOUR_CENTRAL


def check(date: str, now=None) -> dict:
    """Every outcome check for one production date."""
    alarms: list[dict] = []
    notes: list[str] = []

    def alarm(code, severity, detail, fix=""):
        alarms.append({"code": code, "severity": severity, "detail": detail,
                       "fix": fix})

    # ---- the registry must be readable at all ---------------------------
    try:
        registry = reg.load()
    except reg.RegistryError as exc:
        alarm("registry_unusable", "critical",
              f"config/channel_registry.json will not load: {exc}",
              "Nothing can resolve a slate. Fix the JSON first; every other "
              "check below is meaningless until it loads.")
        return {"date": date, "alarms": alarms, "notes": notes, "ok": False}

    early = _too_early(date, now)
    if early:
        notes.append(f"still before {JUDGE_AFTER_HOUR_CENTRAL}:00 Central on "
                     f"{date} — publishing checks deferred, everything else "
                     f"still checked")

    # ---- 1. did each channel ship what the registry asked for? ----------
    for cid in reg.channel_ids(registry):
        paths = reg.paths(cid, registry)
        log_rel = paths.get("posted_log")
        target = reg.target_count(cid, registry)
        if not log_rel or not target:
            continue
        posted = _posted_on(ROOT / log_rel, date)
        if early:
            continue
        if not posted:
            alarm(f"no_posts_{cid}", "critical",
                  f"{cid}: ZERO videos posted for {date} (registry wants "
                  f"{target}).",
                  f"Check the {cid} workflow run for {date}. A day that "
                  f"ships nothing has never once turned a check red — that "
                  f"is why this alarm exists.")
        elif len(posted) < target:
            alarm(f"short_slate_{cid}", "warning",
                  f"{cid}: {len(posted)}/{target} posted for {date}.",
                  "Some slots failed or were skipped. The per-video reason "
                  "is in that day's run log.")
        else:
            notes.append(f"{cid}: {len(posted)}/{target} posted")

    # ---- 1b. the orchestrator's own production outcome ------------------
    # Written by the render run since 2026-08-02 (ChatGPT's takeover
    # contract, ratified): `response.json`/`DONE` mean handoff, never
    # production. `repair_required` sitting there at end of day means the
    # day KNOWS it is short and nobody repaired it — that is exactly the
    # kind of silent-but-recorded failure this alarm exists to shout about.
    outcome_dir = ROOT / "state" / "production_runs" / date
    if outcome_dir.is_dir() and not early:
        for f in sorted(outcome_dir.glob("*.json")):
            oc = _load(f)
            if not isinstance(oc, dict):
                continue
            cid = oc.get("channel") or f.stem
            status = str(oc.get("status") or "")
            if status == "repair_required":
                alarm(f"production_repair_{cid}", "critical",
                      f"{cid} {date}: production outcome says "
                      f"{oc.get('uploaded', '?')}/{oc.get('expected', '?')} "
                      f"uploaded and repair never completed "
                      f"({oc.get('quarantined', 0)} quarantined, "
                      f"{oc.get('failed', 0)} failed).",
                      "The repair path is a push to .github/triggers/daily "
                      "(resumes the unposted remainder; posted-title dedupe "
                      "makes it safe). A held video may also just be the "
                      "showrunner doing its job — read the run log before "
                      "re-kicking.")
            elif status == "production_complete":
                notes.append(f"{cid}: production outcome complete "
                             f"({oc.get('uploaded')}/{oc.get('expected')})")

    # ---- 2. did the exchange actually land? -----------------------------
    bundle_dir = ROOT / "exchange" / "bundles" / date
    bundle = _load(bundle_dir / "bundle.json")
    response = _load(bundle_dir / "response.json")
    report = _load(bundle_dir / "phase_b_report.json")
    done = (bundle_dir / "DONE").exists()

    if bundle is None:
        alarm("no_bundle", "warning",
              f"no exchange/bundles/{date}/bundle.json — Phase A never "
              f"wrote one.",
              "A Phase A that finds no packages exits 0, so this is "
              "invisible in the Actions tab. Check exchange_phase_a.yml.")
    elif done and report is None:
        # THE 2026-08-01 BUG, caught by outcome rather than by luck.
        alarm("done_but_no_report", "critical",
              f"{date} has a DONE marker but NO phase_b_report.json — "
              f"ChatGPT finished and Phase B never applied it to this date.",
              "Phase B resolved a different date. Check which date its run "
              "logged; it must come from `git diff-tree -r HEAD` on a "
              "checkout with fetch-depth >= 2.")
    elif report is not None:
        media = report.get("media") or {}
        offered = len((response or {}).get("media") or [])
        got = int(media.get("fulfilled") or 0)
        if offered and got == 0:
            alarm("chatgpt_media_dropped", "critical",
                  f"ChatGPT delivered {offered} media pointer(s) for {date} "
                  f"and Phase B pinned {got}.",
                  "Every one was refused or failed to fetch. See "
                  f"exchange/bundles/{date}/phase_b_report.json -> "
                  f"checkpoints.rejected_detail.")
        elif offered and got < offered:
            alarm("chatgpt_media_partial", "warning",
                  f"{got}/{offered} ChatGPT images pinned for {date} "
                  f"({media.get('refused', 0)} refused, "
                  f"{media.get('self_filled', 0)} self-filled).", "")
        elif offered:
            notes.append(f"exchange: {got}/{offered} ChatGPT images pinned")
        if report.get("date") and str(report["date"]) != str(date):
            alarm("report_wrong_date", "critical",
                  f"phase_b_report.json under {date}/ says it is for "
                  f"{report['date']}.", "Phase B wrote to the wrong folder.")

    # ---- 3. the slate matched the contract ------------------------------
    if isinstance(bundle, dict) and isinstance(bundle.get("contract"), dict):
        for cid, plan in (bundle["contract"].get("channels") or {}).items():
            pkg_dir = ROOT / "state" / f"{cid}_packages" / date
            if cid == "trending":
                pkg_dir = ROOT / "state" / "trending_packages" / date
            if not pkg_dir.is_dir():
                continue
            pkgs = []
            for p in sorted(pkg_dir.glob("*.json")):
                if p.name.startswith("_"):
                    continue
                obj = _load(p)
                if isinstance(obj, dict):
                    pkgs.append(obj)
            if not pkgs:
                continue
            retired = set(plan.get("retired_formats") or [])
            used = {}
            for p in pkgs:
                f = reg.classify(p, cid, registry)
                used[f] = used.get(f, 0) + 1
            bad = sorted(retired & set(used))
            if bad:
                alarm(f"retired_format_shipped_{cid}", "warning",
                      f"{cid} {date}: {', '.join(bad)} is RETIRED but "
                      f"{sum(used[b] for b in bad)} package(s) used it.",
                      "Promotion should have refused these. If they predate "
                      "the retirement that is expected once, not twice.")

    # ---- 4. the reserve bank still has cover ----------------------------
    try:
        from shared import package_buffer as buf
        low = buf.low_formats()
        if low:
            alarm("reserve_bank_low", "warning",
                  f"reserve bank is low on {', '.join(low)}.",
                  "A dead-Claude morning is covered by the bank first. "
                  "Top up: python scripts/package_reserve.py deposit ...")
    except Exception as exc:                             # noqa: BLE001
        notes.append(f"reserve bank not checked: {exc}")

    ok = not any(a["severity"] == "critical" for a in alarms)
    return {"date": date, "ok": ok, "alarms": alarms, "notes": notes,
            "deferred": early}


def render(result: dict) -> str:
    """Markdown for a GitHub issue comment. Only ever posted when something
    is wrong — a daily 'all good' comment is how people stop reading."""
    date = result["date"]
    crit = [a for a in result["alarms"] if a["severity"] == "critical"]
    warn = [a for a in result["alarms"] if a["severity"] != "critical"]
    lines = [f"## Pipeline alarm — {date}", ""]
    if crit:
        lines.append(f"**{len(crit)} CRITICAL** — the day did not do what it "
                     f"was supposed to.")
    elif warn:
        lines.append(f"{len(warn)} warning(s). Nothing critical.")
    lines.append("")
    for a in crit + warn:
        mark = "🔴" if a["severity"] == "critical" else "🟠"
        lines.append(f"{mark} **`{a['code']}`** — {a['detail']}")
        if a.get("fix"):
            lines.append(f"   > {a['fix']}")
        lines.append("")
    if result.get("notes"):
        lines.append("<details><summary>what did work</summary>")
        lines.append("")
        for n in result["notes"]:
            lines.append(f"- {n}")
        lines.append("</details>")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default=None,
                    help="production date (default: today UTC)")
    ap.add_argument("--yesterday", action="store_true",
                    help="judge the previous day, which is always complete")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    date = args.date
    if not date:
        now = datetime.now(timezone.utc)
        if args.yesterday:
            now -= timedelta(days=1)
        date = now.strftime("%Y%m%d")

    result = check(date)
    if args.json:
        print(json.dumps(result, indent=2))
    elif args.markdown:
        print(render(result))
    else:
        for a in result["alarms"]:
            mark = "CRITICAL" if a["severity"] == "critical" else "warning "
            print(f"[{mark}] {a['code']}: {a['detail']}")
            if a.get("fix"):
                print(f"           -> {a['fix']}")
        for n in result["notes"]:
            print(f"[ ok      ] {n}")
        print(f"\n{date}: "
              + ("OK" if result["ok"] else "SOMETHING IS WRONG")
              + (" (publishing checks deferred — still mid-day)"
                 if result.get("deferred") else ""))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
