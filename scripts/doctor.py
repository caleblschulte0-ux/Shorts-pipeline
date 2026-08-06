#!/usr/bin/env python3
"""The DOCTOR — ChatGPT reads the repo; Claude decides; nothing is automatic.

Operator ruling, 2026-08-05: *"ChatGPT will read the main repo line by line,
and make a long-term plan, short-term plan, small fixes, bug fixes, whatever
it sees, and send that in a file somewhere in the repo that you'll go look at
and be like — we should do this, we are not gonna do this, this is still a
ways out, we're working on this."*

So the split is:

    ChatGPT   READS the code and the runtime evidence, and WRITES findings.
              It never edits code. It is the diagnostician.
    Claude    RULES on each finding, and builds the ones it accepts.
              A scheduled Claude session picks up the open work.
    Nothing   is ever applied automatically. There is no autonomous fix
              path here, by design — the first version of this had one and
              that was over-built past what was asked for.

THE ONE THING THAT MAKES THIS SURVIVE THREE MONTHS
--------------------------------------------------
A reviewer that re-reads the whole repo every day will re-suggest the thing
you already killed — and a file that repeats itself is a file you stop
opening. So verdicts are DURABLE and keyed to a STABLE SIGNATURE:

  * the signature keys on WHAT a finding touches (area + files + kind), not
    on how it was worded, so a thesaurus cannot smuggle a settled item back;
  * `doctor/verdicts.json` is the standing record of every ruling;
  * ChatGPT must read the verdicts BEFORE it writes, and this script REFUSES
    a report that re-files something settled unless it carries
    `new_evidence_since` naming what actually changed.

The vocabulary is the operator's own, verbatim:

    doing        "we should do this"          -> queued for a Claude session
    not_doing    "we are not gonna do this"   -> settled; needs new evidence
    later        "this is still a ways out"   -> parked with a revisit date
    in_progress  "we're working on this"      -> a session has it
    done         shipped                       -> closed, records the commit

    python scripts/doctor.py evidence            # write the pack for ChatGPT
    python scripts/doctor.py validate <report>   # schema + anti-repetition
    python scripts/doctor.py ingest <report>     # accept into the backlog
    python scripts/doctor.py backlog             # what is open, ranked
    python scripts/doctor.py next                # what a session should pick
    python scripts/doctor.py rule <sig> doing --because "..."
    python scripts/doctor.py show <sig>

Exit 0 unless a command genuinely failed; `validate` exits 1 on a bad report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCTOR_DIR = ROOT / "doctor"
REPORTS_DIR = DOCTOR_DIR / "reports"
VERDICTS = DOCTOR_DIR / "verdicts.json"
BACKLOG = DOCTOR_DIR / "backlog.json"
EVIDENCE = DOCTOR_DIR / "evidence.json"

SCHEMA = "shorts-doctor-report/v1"
BACKLOG_SCHEMA = "shorts-doctor-backlog/v1"

#: The operator's own words, in the order a finding travels.
VERDICTS_ALLOWED = ("doing", "not_doing", "later", "in_progress", "done")
#: A finding with no ruling yet.
UNRULED = "new"

#: What ChatGPT is asked to produce. `horizon` is the plan bucket.
HORIZONS = ("bug", "small_fix", "short_term", "long_term")
SEVERITIES = ("critical", "high", "medium", "low")

REQUIRED_FIELDS = ("title", "horizon", "severity", "area", "observation",
                   "proposal", "evidence")

#: How long a `later` ruling parks something before it may resurface.
LATER_COOLDOWN_DAYS = 30
#: A `not_doing` is settled indefinitely — only `new_evidence_since` reopens it.


# ---------------------------------------------------------------------------
# Identity. The whole anti-repetition scheme rests on this being stable.
# ---------------------------------------------------------------------------
def signature(item: dict) -> str:
    """Stable identity for "the same finding again".

    Keyed on WHAT IT TOUCHES — the area, the files, the kind of change — and
    deliberately NOT on wording. "the reddit renderer drops shot images" and
    "shot illustrations are ignored by make_reddit_story" are the same
    finding; a dedupe keyed on title words loses to a thesaurus, which is
    exactly how a killed idea comes back wearing a hat.

    Files are the strongest signal, so when they are named they decide the
    identity. Title words are the fallback for a finding with no file yet
    (an architectural or planning item).
    """
    files = sorted({str(f).strip() for f in (item.get("files") or []) if f})
    parts = [str(item.get("area") or "").strip().lower(),
             str(item.get("horizon") or "").strip().lower()]
    if files:
        parts.append(",".join(files))
    else:
        words = sorted(set(re.findall(
            r"[a-z]{4,}", str(item.get("title") or "").lower())))
        parts.append(",".join(words[:8]))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:                                    # noqa: BLE001
        return default


def _save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    from shared.fsutil import write_json_if_changed
    write_json_if_changed(path, obj)


# ---------------------------------------------------------------------------
# The standing record.
# ---------------------------------------------------------------------------
def load_verdicts() -> dict:
    """signature -> the current ruling, with its history."""
    return _load(VERDICTS, {}).get("verdicts", {}) if VERDICTS.exists() else {}


def save_verdicts(v: dict) -> None:
    _save(VERDICTS, {"schema": "shorts-doctor-verdicts/v1",
                     "updated": _today(), "verdicts": v})


def load_backlog() -> dict:
    """signature -> the finding itself (the latest text ChatGPT filed)."""
    return _load(BACKLOG, {}).get("items", {}) if BACKLOG.exists() else {}


def save_backlog(items: dict) -> None:
    _save(BACKLOG, {"schema": BACKLOG_SCHEMA, "updated": _today(),
                    "items": items})


def ruling_of(sig: str, verdicts: dict | None = None) -> str:
    v = (verdicts if verdicts is not None else load_verdicts()).get(sig)
    return (v or {}).get("verdict") or UNRULED


# ---------------------------------------------------------------------------
# The refusal list. Inherited, not re-written — one list for every agent that
# suggests anything to this repo.
# ---------------------------------------------------------------------------
def _rp_reasons(item: dict) -> list[str]:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import review_proposals as rp
        probe = {"title": item.get("title", ""),
                 "observation": item.get("observation", ""),
                 "proposal": item.get("proposal", ""),
                 "files": item.get("files") or []}
        return rp.check_forbidden(probe)
    except Exception:                                    # noqa: BLE001
        return []


def forbidden(item: dict) -> list[str]:
    """The "make the numbers go up by lowering the bar" class, refused.

    Reuses `review_proposals.check_forbidden` for the INTENT rules so the
    doctor and the retro reviewer cannot drift on what is unacceptable to
    ASK FOR. But the retro's file-touch refusals ("touches <protected>")
    are deliberately NOT applied here, because the two queues differ in
    what a submission IS: a retro proposal gets implemented by
    retro_decide, so touching a protected file is itself the danger; a
    doctor finding is a DIAGNOSIS that a Claude session rules on, and
    nothing is applied automatically.

    Day one proved why this matters: the doctor's first report contained a
    verified HIGH bug in the publish gate — malformed verdicts shipping —
    proposing to make the gate STRICTER, and the file-touch rule silently
    binned it along with two more showrunner findings. The area a finding
    points at is not a crime; what it asks for can be. Protected-area
    context is preserved as `protected_notes()` and stored on the backlog
    item, so the session ruling on it sees the constraint (fixes may only
    ever ADD blocks) instead of never seeing the finding at all.
    """
    return [r for r in _rp_reasons(item) if not r.startswith("touches ")]


def protected_notes(item: dict) -> list[str]:
    """The protected-area warnings for a finding — context for the ruling,
    not grounds for refusal. See `forbidden` for why these are split."""
    return [r for r in _rp_reasons(item) if r.startswith("touches ")]


# ---------------------------------------------------------------------------
# Validation. This is the gate on ChatGPT's report.
# ---------------------------------------------------------------------------
def validate_item(item: dict, verdicts: dict) -> list[str]:
    problems: list[str] = []
    if not isinstance(item, dict):
        return ["not an object"]

    for f in REQUIRED_FIELDS:
        if not str(item.get(f) or "").strip():
            problems.append(f"missing `{f}`")
    if item.get("horizon") not in HORIZONS:
        problems.append(f"horizon must be one of {list(HORIZONS)}")
    if item.get("severity") not in SEVERITIES:
        problems.append(f"severity must be one of {list(SEVERITIES)}")

    files = item.get("files") or []
    if not isinstance(files, list):
        problems.append("`files` must be a list")
    else:
        for f in files:
            if not (ROOT / str(f)).exists():
                problems.append(f"names a file that does not exist: {f}")

    # A finding must be anchored in something a reader can check.
    ev = str(item.get("evidence") or "")
    if len(ev) < 20:
        problems.append("`evidence` is too thin to check — cite the file, "
                        "the line, the log, or the run")

    problems.extend(forbidden(item))

    # THE ANTI-REPETITION RULE.
    sig = item.get("signature") or signature(item)
    prior = verdicts.get(sig)
    if prior:
        verdict = prior.get("verdict")
        fresh = str(item.get("new_evidence_since") or "").strip()
        if verdict == "not_doing" and not fresh:
            problems.append(
                f"already ruled `not_doing` on {prior.get('date')} "
                f"({str(prior.get('because') or '')[:80]}) — re-file only "
                f"with `new_evidence_since` naming what actually changed")
        elif verdict == "later" and not fresh:
            until = prior.get("revisit_after") or ""
            if until and _today() < str(until):
                problems.append(
                    f"parked as `later` until {until} — do not re-file "
                    f"before then without `new_evidence_since`")
        elif verdict == "done" and not fresh:
            problems.append(
                f"already shipped on {prior.get('date')} — if it did not "
                f"work, file that as a NEW finding with the evidence, not "
                f"as a repeat of the old one")
    return problems


def validate_report(report: dict) -> dict:
    """Returns {ok, accepted[], rejected[], counts}. Pure — no writes."""
    out = {"ok": False, "accepted": [], "rejected": [], "counts": {}}
    if not isinstance(report, dict):
        out["rejected"].append({"problems": ["report is not an object"]})
        return out
    if report.get("schema") != SCHEMA:
        out["rejected"].append(
            {"problems": [f"schema must be {SCHEMA!r}, got "
                          f"{report.get('schema')!r}"]})
        return out

    verdicts = load_verdicts()
    seen: set[str] = set()
    for item in report.get("findings") or []:
        sig = (item.get("signature") if isinstance(item, dict) else None) \
            or (signature(item) if isinstance(item, dict) else "?")
        problems = validate_item(item, verdicts)
        if sig in seen:
            problems.append("duplicate of another finding in this same "
                            "report")
        seen.add(sig)
        entry = {"signature": sig,
                 "title": (item or {}).get("title") if isinstance(item, dict)
                 else None}
        if problems:
            out["rejected"].append({**entry, "problems": problems})
        else:
            out["accepted"].append({**entry, "item": {**item,
                                                      "signature": sig}})
    out["counts"] = {"accepted": len(out["accepted"]),
                     "rejected": len(out["rejected"])}
    out["ok"] = bool(out["accepted"]) and not out["rejected"]
    return out


def ingest(report: dict, *, date: str | None = None) -> dict:
    """Fold a validated report into the standing backlog.

    Accepted findings land as `new` (awaiting a ruling). A finding that is
    already in the backlog has its TEXT refreshed but keeps its ruling —
    ChatGPT may sharpen the description of something Claude already decided;
    it may not launder a new decision through a rewrite.
    """
    date = date or _today()
    res = validate_report(report)
    items = load_backlog()
    verdicts = load_verdicts()
    added, refreshed = [], []
    for acc in res["accepted"]:
        sig, item = acc["signature"], acc["item"]
        notes = protected_notes(item)
        if notes:
            # Context the ruling session must see: this finding points at a
            # protected area, so whatever gets built may only ever ADD
            # blocks / strengthen the gate — never the reverse.
            item["protected"] = notes
        item["last_seen"] = date
        if sig in items:
            item["first_seen"] = items[sig].get("first_seen", date)
            items[sig] = item
            refreshed.append(sig)
        else:
            item["first_seen"] = date
            items[sig] = item
            added.append(sig)
    save_backlog(items)
    res["added"], res["refreshed"] = added, refreshed
    res["awaiting_ruling"] = [s for s in items
                              if ruling_of(s, verdicts) == UNRULED]
    return res


# ---------------------------------------------------------------------------
# Ruling — Claude's half.
# ---------------------------------------------------------------------------
def rule(sig: str, verdict: str, *, because: str = "",
         revisit_after: str | None = None, commit: str = "") -> dict:
    if verdict not in VERDICTS_ALLOWED:
        raise ValueError(f"verdict must be one of {list(VERDICTS_ALLOWED)}")
    verdicts = load_verdicts()
    prior = verdicts.get(sig) or {}
    if verdict == "later" and not revisit_after:
        revisit_after = (datetime.now(timezone.utc)
                         + timedelta(days=LATER_COOLDOWN_DAYS)).strftime(
                             "%Y%m%d")
    entry = {"verdict": verdict, "date": _today(), "because": because,
             "history": (prior.get("history") or [])
             + ([{"verdict": prior["verdict"], "date": prior.get("date"),
                  "because": prior.get("because")}] if prior.get("verdict")
                else [])}
    if revisit_after:
        entry["revisit_after"] = revisit_after
    if commit:
        entry["commit"] = commit
    verdicts[sig] = entry
    save_verdicts(verdicts)
    return entry


#: Ranking for what a session should pick up first.
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_HOR_RANK = {"bug": 0, "small_fix": 1, "short_term": 2, "long_term": 3}


def backlog_view(state: str | None = None) -> list[dict]:
    items, verdicts = load_backlog(), load_verdicts()
    out = []
    for sig, item in items.items():
        r = ruling_of(sig, verdicts)
        if state and r != state:
            continue
        out.append({**item, "signature": sig, "ruling": r,
                    "ruling_detail": verdicts.get(sig) or {}})
    out.sort(key=lambda i: (_SEV_RANK.get(i.get("severity"), 9),
                            _HOR_RANK.get(i.get("horizon"), 9),
                            i.get("first_seen") or ""))
    return out


def next_up(limit: int = 5) -> list[dict]:
    """What a scheduled Claude session should work on: things ruled `doing`,
    then anything still unruled (which needs a decision before it needs
    code)."""
    return (backlog_view("doing") + backlog_view(UNRULED))[:limit]


# ---------------------------------------------------------------------------
# The evidence pack ChatGPT reads alongside the code.
# ---------------------------------------------------------------------------
def evidence_pack() -> dict:
    """Runtime truth, so the doctor reads the code AND what it actually did.

    Reading source alone produces plausible findings; reading source plus
    what broke produces checkable ones."""
    pack: dict = {"schema": "shorts-doctor-evidence/v1", "date": _today()}

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
        "%Y%m%d")
    pack["judged_date"] = yesterday
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import daily_alarm
        pack["alarm"] = daily_alarm.check(yesterday)
    except Exception as exc:                             # noqa: BLE001
        pack["alarm"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Recent production outcomes — ChatGPT's own "DONE is not production
    # completion" contract, which is the strongest signal of a bad day.
    runs = []
    root = ROOT / "state" / "production_runs"
    if root.is_dir():
        for d in sorted(root.iterdir(), reverse=True)[:7]:
            for f in sorted(d.glob("*.json")):
                oc = _load(f, None)
                if isinstance(oc, dict):
                    runs.append(oc)
    pack["production_runs"] = runs[:20]

    # The taste gate's recent memory.
    ledger = ROOT / "state" / "showrunner_verdicts.jsonl"
    recent = []
    try:
        for line in ledger.read_text().splitlines()[-60:]:
            try:
                recent.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    pack["showrunner_recent"] = recent

    try:
        out = subprocess.run(
            ["git", "log", "--format=%h %ad %s", "--date=short", "-40"],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        pack["recent_commits"] = (out.stdout or "").strip().splitlines()
    except Exception:                                    # noqa: BLE001
        pack["recent_commits"] = []

    # What is already decided — so the doctor does not re-file it.
    pack["open_backlog"] = [
        {k: i.get(k) for k in ("signature", "title", "horizon", "severity",
                               "ruling")}
        for i in backlog_view() if i["ruling"] in (UNRULED, "doing",
                                                  "in_progress")]
    pack["settled"] = [
        {"signature": s, "verdict": v.get("verdict"), "date": v.get("date"),
         "because": v.get("because"), "revisit_after": v.get("revisit_after")}
        for s, v in load_verdicts().items()
        if v.get("verdict") in ("not_doing", "later", "done")]
    return pack


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------
_MARK = {"new": "🆕", "doing": "🔨", "in_progress": "⚙️", "later": "🅿️",
         "not_doing": "🚫", "done": "✅"}


def render_backlog(rows: list[dict]) -> str:
    if not rows:
        return "backlog is empty."
    lines = []
    for i in rows:
        lines.append(
            f"{_MARK.get(i['ruling'], '?')} [{i['signature']}] "
            f"{i.get('severity')}/{i.get('horizon')} — {i.get('title')}")
        if i["ruling_detail"].get("because"):
            lines.append(f"      ↳ {i['ruling_detail']['because'][:100]}")
    return "\n".join(lines)


def main() -> int:                                       # noqa: C901
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("evidence", help="write doctor/evidence.json for ChatGPT")

    for name, helptext in (("validate", "check a report, write nothing"),
                           ("ingest", "validate then fold into the backlog")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("report", help="path to the report JSON, or - for stdin")
        p.add_argument("--json", action="store_true")

    b = sub.add_parser("backlog", help="everything, ranked")
    b.add_argument("--state", choices=(UNRULED,) + VERDICTS_ALLOWED)
    b.add_argument("--json", action="store_true")

    n = sub.add_parser("next", help="what a session should pick up")
    n.add_argument("--limit", type=int, default=5)
    n.add_argument("--json", action="store_true")

    r = sub.add_parser("rule", help="record a decision")
    r.add_argument("signature")
    r.add_argument("verdict", choices=VERDICTS_ALLOWED)
    r.add_argument("--because", default="")
    r.add_argument("--revisit-after", default=None)
    r.add_argument("--commit", default="")

    s = sub.add_parser("show", help="one finding in full")
    s.add_argument("signature")

    args = ap.parse_args()

    if args.cmd == "evidence":
        pack = evidence_pack()
        _save(EVIDENCE, pack)
        print(f"wrote {EVIDENCE.relative_to(ROOT)} "
              f"({len(pack.get('open_backlog') or [])} open, "
              f"{len(pack.get('settled') or [])} settled)")
        return 0

    if args.cmd in ("validate", "ingest"):
        text = sys.stdin.read() if args.report == "-" else \
            Path(args.report).read_text()
        report = json.loads(text)
        res = ingest(report) if args.cmd == "ingest" else \
            validate_report(report)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            for rej in res["rejected"]:
                print(f"REJECTED [{rej.get('signature')}] "
                      f"{rej.get('title')}")
                for p in rej["problems"]:
                    print(f"    - {p}")
            print(f"{res['counts']['accepted']} accepted, "
                  f"{res['counts']['rejected']} rejected")
            if args.cmd == "ingest":
                print(f"{len(res['added'])} new, "
                      f"{len(res['refreshed'])} refreshed, "
                      f"{len(res['awaiting_ruling'])} awaiting your ruling")
        # Rejections are the gate doing its job on a partial report; only a
        # report with NOTHING usable is a failure.
        return 0 if res["counts"]["accepted"] or not res["rejected"] else 1

    if args.cmd == "backlog":
        rows = backlog_view(args.state)
        print(json.dumps(rows, indent=2) if args.json
              else render_backlog(rows))
        return 0

    if args.cmd == "next":
        rows = next_up(args.limit)
        print(json.dumps(rows, indent=2) if args.json
              else render_backlog(rows))
        return 0

    if args.cmd == "rule":
        e = rule(args.signature, args.verdict, because=args.because,
                 revisit_after=args.revisit_after, commit=args.commit)
        print(f"{args.signature}: {e['verdict']}"
              + (f" (revisit after {e['revisit_after']})"
                 if e.get("revisit_after") else ""))
        return 0

    if args.cmd == "show":
        item = load_backlog().get(args.signature)
        if not item:
            print(f"no finding {args.signature!r}", file=sys.stderr)
            return 1
        print(json.dumps({**item, "ruling": ruling_of(args.signature),
                          "ruling_detail": load_verdicts().get(
                              args.signature, {})}, indent=2))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
