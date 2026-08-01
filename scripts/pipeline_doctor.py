#!/usr/bin/env python3
"""The PIPELINE DOCTOR — the daily autonomous maintainer.

Operator ruling, 2026-08-01: *"every day, look at the pipeline, look at
what's working, what's not working, recommend changes, and then actually go
and fix shit — so I don't have to keep coming on here."*

This is that. Once a day (`doctor.yml`, after the alarm has judged
yesterday), the doctor:

  1. GATHERS evidence — the alarm's verdict, the showrunner's ledger, the
     exchange reports, the reserve bank, ChatGPT's triaged retro suggestions,
     and its own journal of what it already tried.
  2. DIAGNOSES — turns evidence into findings with stable signatures, so the
     same problem on two days is the same finding, not two.
  3. PLANS — maps each finding to the least-powerful remedy that can fix it:
       mechanical  a deterministic playbook (re-dispatch a workflow, clear a
                   corrupt artifact) executed by the workflow, no brain
       authored    a code/content fix written by the HEADLESS CLAUDE BRAIN
                   on a `claude/doctor-<date>` branch, through a PR, through
                   the full auto-merge test gate
       report      an operator item with the exact command — for anything
                   the constitution forbids the doctor to touch
  4. ENFORCES THE CONSTITUTION — every authored diff is reviewed in code
     before it may become a PR. The refusal list is the same class
     `review_proposals.py` refuses, plus self-modification: the doctor can
     never weaken a gate, delete a test, touch a posted log, edit a
     workflow, or rewrite its own rules. Only the operator loosens the
     constitution.
  5. CLOSES THE LOOP — every action records what outcome it expects
     (usually: a specific alarm code absent tomorrow). The next run marks it
     resolved or failed. Two failures on the same signature and the doctor
     STOPS trying and escalates to a report — it never grinds the same
     failed fix forever.

Authority model (see CLAUDE.md "WHO MAY EDIT"): the doctor's brain is a
Claude, so it may write code — but only through a PR on a `claude/*` branch,
where the auto-merge gate (the full test suite, the drift gates, the
dry-runs) is the reviewer. ChatGPT's retro proposals reach the doctor ONLY
through `review_proposals.py` triage output (`retro/<date>/triage.json`) —
the doctor implements accepted suggestions; it never reads raw proposals and
never touches the refused classes.

    python scripts/pipeline_doctor.py run                # diagnose + plan
    python scripts/pipeline_doctor.py run --date 20260801 --json
    python scripts/pipeline_doctor.py review-diff /path/to.diff
    git diff | python scripts/pipeline_doctor.py review-diff -
    python scripts/pipeline_doctor.py record --signature S --kind authored \
        --action "opened PR #241" --expect-absent no_posts_trending

Exit codes: `run` exits 0 always (a diagnosis is not a failure);
`review-diff` exits 1 when the constitution refuses the diff.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

# ---------------------------------------------------------------------------
# Bounds. Small on purpose: the doctor earns wider limits by being right,
# and the operator widens them deliberately — never the doctor itself.
# ---------------------------------------------------------------------------
MAX_AUTHORED_PER_DAY = 1     # one brain-written fix a day, fully verified
MAX_MECHANICAL_PER_DAY = 3
MAX_DIFF_FILES = 8
MAX_DIFF_LINES = 400
MAX_ATTEMPTS = 2             # same signature failed twice -> escalate, stop

STATE_DIR = ROOT / "state" / "doctor"
JOURNAL = STATE_DIR / "journal.jsonl"

SCHEMA = "pipeline-doctor/v1"


# ---------------------------------------------------------------------------
# THE CONSTITUTION.
#
# What the doctor may NEVER touch, and why — enforced on the DIFF, in code,
# before a PR can exist. This is deliberately the same shape as
# `review_proposals.py`'s refusal list: a well-argued violation is still a
# violation. Making a gate STRONGER (adding checks, adding tests) is always
# allowed; that asymmetry is the whole design.
# ---------------------------------------------------------------------------
def _protected_files() -> dict[str, str]:
    """The proposal-triage protected set, plus the doctor's own additions.

    Imported from `review_proposals` so there is one refusal list, not two
    drifting copies — the exact failure mode `channel_registry` exists to
    prevent for slate policy."""
    import review_proposals as rp
    protected = dict(rp.PROTECTED_FILES)
    protected.update({
        # The policy moved here on 2026-08-01; both channels call it.
        "shared/showrunner_gate.py":
            "the fail-closed publish policy for every channel",
        # The doctor's own senses and rules. A doctor that can silence its
        # alarm or rewrite its constitution is the classic failure.
        "scripts/daily_alarm.py": "the doctor may not silence its own alarm",
        "tests/test_daily_alarm.py": "nor weaken the alarm's tests",
        "scripts/pipeline_doctor.py":
            "the doctor may not rewrite its own constitution",
        "tests/test_doctor.py": "nor the tests that hold it to it",
        "scripts/review_proposals.py":
            "the refusal list the doctor inherits — operator's pen only",
    })
    return protected


#: Whole subtrees the doctor may not write into. Workflows are operator
#: territory in v1 (every one is load-bearing); `config/` is channel policy;
#: `exchange/` and `retro/` belong to the daily contract with ChatGPT;
#: `state/` is run output — except the doctor's own corner of it.
FORBIDDEN_PREFIXES = (
    ".github/", "config/", "exchange/", "retro/", "assets/mascot/",
)
STATE_PREFIX = "state/"
DOCTOR_STATE_PREFIX = "state/doctor/"

#: Doctrine documents are contracts between sessions, not code.
DOCTRINE_FILES = (
    "CLAUDE.md", "CLAUDE_ROUTINE_INSTRUCTIONS.md", "docs/DIRECTOR.md",
    "docs/DOCTOR.md", "docs/EDITORIAL_RESET.md",
)

#: A REMOVED line matching any of these is refused wherever it appears —
#: code may only ever ADD blocks. (Adding lines that mention these is fine;
#: that is what "stronger is always allowed" means.)
FORBIDDEN_REMOVALS = (
    (r"showrunner", "removes showrunner-related code — a BLOCK is sovereign "
                    "and gates may only be ADDED"),
    (r"fail[-_ ]?closed|fails closed", "removes fail-closed handling"),
    (r"posted[_ ]?log", "touches posted-log handling — append-only dedupe "
                        "state"),
    (r"punchup_guard|placement_gate", "removes a guard"),
)


def parse_diff(diff_text: str) -> list[dict]:
    """A unified diff -> per-file {path, old_path, added[], removed[],
    deleted}. Handles git headers, /dev/null, renames. Tolerant: anything it
    cannot parse contributes no lines (and the bounds check still counts the
    file, so garbage cannot sneak size past the gate)."""
    files: list[dict] = []
    cur: dict | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*?) b/(.*)$", line)
            cur = {"path": m.group(2) if m else "", "old_path":
                   m.group(1) if m else "", "added": [], "removed": [],
                   "deleted": False}
            files.append(cur)
        elif cur is not None and line.startswith("deleted file mode"):
            cur["deleted"] = True
        elif cur is not None and line.startswith("+++ "):
            if line[4:].strip() == "/dev/null":
                cur["deleted"] = True
        elif cur is not None and line.startswith("+") and not \
                line.startswith("+++"):
            cur["added"].append(line[1:])
        elif cur is not None and line.startswith("-") and not \
                line.startswith("---"):
            cur["removed"].append(line[1:])
    return files


def review_diff(diff_text: str) -> list[str]:
    """The constitution, applied. Returns the list of violations; empty
    means the diff may become a PR. Every rule names its reason — a refusal
    the brain cannot understand is a refusal it will route around."""
    problems: list[str] = []
    files = parse_diff(diff_text)
    if not files:
        return ["empty or unparseable diff — nothing to review"]

    protected = _protected_files()
    total_lines = 0

    for f in files:
        path = f["path"] or f["old_path"]
        total_lines += len(f["added"]) + len(f["removed"])

        if path in protected:
            problems.append(f"{path}: PROTECTED — {protected[path]}")
        for prefix in FORBIDDEN_PREFIXES:
            if path.startswith(prefix):
                problems.append(
                    f"{path}: under {prefix} — operator territory; the "
                    f"doctor reports here, it does not edit")
        if path.startswith(STATE_PREFIX) and not \
                path.startswith(DOCTOR_STATE_PREFIX):
            problems.append(f"{path}: run state belongs to the runs that "
                            f"write it (only state/doctor/ is the doctor's)")
        if path in DOCTRINE_FILES:
            problems.append(f"{path}: doctrine — a contract between "
                            f"sessions, changed only by the operator's ask")

        is_test = (path.startswith("tests/") or
                   Path(path).name.startswith("test_"))
        if is_test and f["deleted"]:
            problems.append(f"{path}: deletes a test file — never")
        if is_test:
            removed_tests = sum(1 for ln in f["removed"]
                                if re.search(r"\bdef test_", ln))
            added_tests = sum(1 for ln in f["added"]
                              if re.search(r"\bdef test_", ln))
            if removed_tests > added_tests:
                problems.append(f"{path}: removes {removed_tests} test(s) "
                                f"and adds {added_tests} — a shrinking test "
                                f"file is a weakened gate")
            removed_asserts = sum(1 for ln in f["removed"]
                                  if re.search(r"\bassert", ln))
            added_asserts = sum(1 for ln in f["added"]
                                if re.search(r"\bassert", ln))
            if removed_asserts > added_asserts:
                problems.append(f"{path}: net-removes assertions "
                                f"({removed_asserts} out, {added_asserts} "
                                f"in) — weakened checks are refused even "
                                f"inside a kept test")

        for pattern, why in FORBIDDEN_REMOVALS:
            hits = [ln for ln in f["removed"]
                    if re.search(pattern, ln, re.IGNORECASE)]
            if hits:
                problems.append(f"{path}: {why} (removed: "
                                f"{hits[0].strip()[:70]!r})")

    if len(files) > MAX_DIFF_FILES:
        problems.append(f"diff touches {len(files)} files > "
                        f"{MAX_DIFF_FILES} — one bounded fix a day; split it "
                        f"or hand it to the operator")
    if total_lines > MAX_DIFF_LINES:
        problems.append(f"diff is {total_lines} changed lines > "
                        f"{MAX_DIFF_LINES} — too big to be the doctor's")

    return problems


def constitution_text() -> str:
    """The rules, as prose, for embedding in the brain's brief — the brain
    must be TOLD the rules it will be held to, or refusals teach it
    nothing."""
    protected = _protected_files()
    lines = [
        "HARD RULES — your diff is reviewed in code against these before it "
        "can become a PR; a violation discards ALL of your work:",
        "",
    ]
    for path, why in sorted(protected.items()):
        lines.append(f"- NEVER edit {path} ({why})")
    lines += [
        f"- NEVER write under: {', '.join(FORBIDDEN_PREFIXES)} or state/ "
        f"(except state/doctor/)",
        f"- NEVER edit doctrine: {', '.join(DOCTRINE_FILES)}",
        "- NEVER delete a test file, remove a test function, or net-remove "
        "assertions",
        "- NEVER remove a line that mentions the showrunner, fail-closed "
        "handling, a posted log, or a guard — gates may only be ADDED",
        f"- Keep the diff <= {MAX_DIFF_FILES} files and <= {MAX_DIFF_LINES} "
        f"changed lines",
        "- ADD a test that fails before your fix and passes after it",
        "- Making a gate stronger is always allowed",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evidence.
# ---------------------------------------------------------------------------
def _load(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:                                    # noqa: BLE001
        return default


def _ledger_tail(days: int = 7) -> list[dict]:
    """Recent showrunner verdicts — the taste gate's memory."""
    path = ROOT / "state" / "showrunner_verdicts.jsonl"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out = []
    try:
        for line in path.read_text().splitlines()[-500:]:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(rec.get("ts", "")) >= cutoff:
                out.append(rec)
    except OSError:
        pass
    return out


def gather(date: str, now=None) -> dict:
    """Everything the doctor can know from artifacts on disk. Offline,
    read-only, and defensive — missing evidence is an empty field, never a
    crash. The doctor must be able to diagnose a badly broken repo."""
    ev: dict = {"schema": SCHEMA, "date": date}

    try:
        import daily_alarm
        ev["alarm"] = daily_alarm.check(date, now=now)
    except Exception as exc:                             # noqa: BLE001
        ev["alarm"] = {"error": f"{type(exc).__name__}: {exc}"}

    ev["ledger"] = _ledger_tail()

    bundle_dir = ROOT / "exchange" / "bundles" / date
    ev["exchange"] = {
        "bundle": (bundle_dir / "bundle.json").exists(),
        "done": (bundle_dir / "DONE").exists(),
        "report": _load(bundle_dir / "phase_b_report.json"),
    }

    # ChatGPT's suggestions, AFTER the triage has run its refusal list.
    # The doctor never reads the raw suggestion files.
    tri = _load(ROOT / "retro" / date / "triage.json") or {}
    ev["triage_accepted"] = tri.get("accepted") or []

    try:
        from shared import package_buffer as buf
        ev["bank_low"] = buf.low_formats()
    except Exception:                                    # noqa: BLE001
        ev["bank_low"] = []

    ev["journal"] = load_journal()
    return ev


# ---------------------------------------------------------------------------
# The journal — the doctor's memory, and the closed loop.
# ---------------------------------------------------------------------------
def load_journal() -> list[dict]:
    out = []
    try:
        for line in JOURNAL.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


def append_journal(entry: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             **entry}
    with JOURNAL.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def failed_attempts(journal: list[dict]) -> dict[str, int]:
    """How many times each signature has been tried AND failed."""
    n: dict[str, int] = {}
    for e in journal:
        if e.get("outcome") == "failed" and e.get("signature"):
            n[e["signature"]] = n.get(e["signature"], 0) + 1
    return n


def open_expectations(journal: list[dict]) -> list[dict]:
    """Actions still waiting for their outcome, latest state per action id."""
    latest: dict[str, dict] = {}
    for e in journal:
        aid = e.get("action_id") or e.get("signature")
        if not aid:
            continue
        latest[aid] = e
    return [e for e in latest.values() if e.get("outcome") == "pending"
            and e.get("expect_absent")]


def close_the_loop(ev: dict) -> list[dict]:
    """Mark yesterday's pending actions resolved or failed, judged by
    whether the alarm code they expected to clear is actually gone. THIS is
    what stops the doctor from believing its own press: an action is not a
    fix until the outcome it named shows up."""
    alarm_codes = {a.get("code") for a in
                   (ev.get("alarm") or {}).get("alarms", [])}
    resolutions = []
    for e in open_expectations(ev.get("journal") or []):
        if e.get("date") == ev["date"]:
            continue                        # same day — too early to judge
        outcome = ("resolved" if e["expect_absent"] not in alarm_codes
                   else "failed")
        res = {"date": ev["date"], "signature": e.get("signature"),
               "action_id": e.get("action_id") or e.get("signature"),
               "kind": "verdict", "outcome": outcome,
               "detail": f"expected `{e['expect_absent']}` absent on "
                         f"{ev['date']} — it {'is' if outcome == 'resolved' else 'is NOT'}"}
        append_journal(res)
        resolutions.append(res)
    return resolutions


# ---------------------------------------------------------------------------
# Diagnosis: evidence -> findings. Signatures are STABLE — same problem,
# same signature, across days — that is what makes cooldown and escalation
# possible.
# ---------------------------------------------------------------------------
SEV_RANK = {"critical": 0, "warn": 1, "info": 2}

#: alarm code (prefix) -> (severity, remedy kind, playbook)
ALARM_MAP = [
    ("registry_unusable", "critical", "report", None),
    ("done_but_no_report", "critical", "mechanical", "redispatch_phase_b"),
    ("no_posts_", "critical", "authored", None),
    ("chatgpt_media_dropped", "critical", "authored", None),
    ("report_wrong_date", "critical", "authored", None),
    ("retired_format_shipped", "warn", "authored", None),
    ("reserve_bank_low", "warn", "authored", None),
    ("chatgpt_media_partial", "warn", "watch", None),
    ("short_slate_", "warn", "watch", None),
    ("no_bundle", "warn", "watch", None),
]


def diagnose(ev: dict) -> list[dict]:
    findings: list[dict] = []

    def add(sig, sev, title, detail, kind, playbook=None, brief=None):
        findings.append({"signature": sig, "severity": sev, "title": title,
                         "detail": detail, "kind": kind,
                         "playbook": playbook, "brief": brief})

    # 1. The alarm's verdict is the primary sense organ.
    for a in (ev.get("alarm") or {}).get("alarms", []):
        code = str(a.get("code", ""))
        for prefix, sev, kind, playbook in ALARM_MAP:
            if code.startswith(prefix):
                add(f"alarm:{code}", sev, code, a.get("detail", ""), kind,
                    playbook=playbook,
                    brief=f"The daily alarm raised `{code}`: "
                          f"{a.get('detail', '')}\nIts suggested direction: "
                          f"{a.get('fix', '(none)')}\nDiagnose the actual "
                          f"cause and fix it at the root. Acceptance: this "
                          f"alarm code is absent on the next judged day.")
                break
        else:
            add(f"alarm:{code}", "warn", code, a.get("detail", ""), "watch")

    # done_but_no_report's mechanical remedy has preconditions — a
    # re-dispatch only makes sense while the DONE marker is really sitting
    # there unconsumed.
    for f in findings:
        if f["playbook"] == "redispatch_phase_b":
            ex = ev.get("exchange") or {}
            if not (ex.get("done") and not ex.get("report")):
                f["kind"], f["playbook"] = "watch", None
                f["detail"] += " (redispatch preconditions no longer hold)"

    # 2. The showrunner's ledger: a taste problem repeating is a finding,
    # not six independent bad days.
    fails: dict[str, int] = {}
    for rec in ev.get("ledger") or []:
        if rec.get("verdict") == "block":
            for af in rec.get("auto_fails") or ["(low_score)"]:
                fails[af] = fails.get(af, 0) + 1
    for af, n in sorted(fails.items(), key=lambda kv: -kv[1]):
        if n >= 3:
            add(f"showrunner:{af}", "warn",
                f"showrunner blocked {n}x in 7 days on `{af}`",
                f"The taste gate keeps refusing videos for the same reason "
                f"({af}, {n} blocks this week). The gate is right — the "
                f"renders are wrong.", "authored",
                brief=f"The showrunner has blocked {n} videos in 7 days for "
                      f"`{af}`. Read the verdicts in "
                      f"state/showrunner_verdicts.jsonl, find what the "
                      f"renderer keeps doing wrong, and fix the RENDER — "
                      f"never the gate. Acceptance: the block rate on this "
                      f"auto-fail falls; the gate itself is untouched.")

    # 3. ChatGPT's accepted suggestions, oldest highest-scored first.
    for item in (ev.get("triage_accepted") or [])[:3]:
        sig = f"triage:{item.get('signature') or item.get('title')}"
        add(sig, "info",
            f"accepted retro suggestion: {item.get('title')}",
            str(item.get("proposal") or "")[:300], "authored",
            brief=f"ChatGPT's retro reviewer proposed (and the triage "
                  f"accepted): {item.get('title')}\n\n"
                  f"{item.get('proposal')}\n\nFiles it named: "
                  f"{item.get('files')}\nImplement it if the evidence holds "
                  f"when you read the code; if it does not hold, journal why "
                  f"instead of forcing it.")

    # 4. The bank.
    for fmt in ev.get("bank_low") or []:
        add(f"bank:{fmt}", "warn", f"reserve bank low on {fmt}",
            "A dead-brain morning is covered by the bank first.", "authored",
            brief=f"The reserve bank is under its low-water mark on `{fmt}`. "
                  f"Author EVERGREEN {fmt} packages (real data via "
                  f"scripts/story_forge.py sources where applicable — never "
                  f"invented numbers) and deposit them via "
                  f"shared/package_buffer.deposit, which validates and "
                  f"refuses date-anchored language. Content only: no code "
                  f"changes for this finding.")

    findings.sort(key=lambda f: (SEV_RANK.get(f["severity"], 9),
                                 f["signature"]))
    return findings


# ---------------------------------------------------------------------------
# Planning: findings -> today's bounded actions.
# ---------------------------------------------------------------------------
def plan(findings: list[dict], journal: list[dict], date: str) -> dict:
    attempts = failed_attempts(journal)
    already_today = {e.get("signature") for e in journal
                     if e.get("date") == date and e.get("kind") != "verdict"}

    out = {"schema": SCHEMA, "date": date, "mechanical": [], "authored": [],
           "report": [], "watch": []}

    for f in findings:
        sig = f["signature"]
        if sig in already_today:
            continue                            # one shot per signature per day
        if attempts.get(sig, 0) >= MAX_ATTEMPTS:
            out["report"].append({**f, "escalated":
                                  f"tried and failed {attempts[sig]}x — the "
                                  f"doctor stops here; this needs you"})
            continue
        if f["kind"] == "mechanical" and \
                len(out["mechanical"]) < MAX_MECHANICAL_PER_DAY:
            out["mechanical"].append(f)
        elif f["kind"] == "authored" and \
                len(out["authored"]) < MAX_AUTHORED_PER_DAY:
            out["authored"].append(f)
        elif f["kind"] == "authored" and f["severity"] == "critical":
            # The one authored slot is taken and this is still CRITICAL —
            # that must land in front of the operator today, not sit in a
            # "watching" list nobody reads. Findings are severity-sorted, so
            # the slot always went to something at least as severe.
            out["report"].append({**f, "escalated":
                                  "critical, but today's authored slot is "
                                  "taken — queued for tomorrow, flagged now"})
        elif f["kind"] == "report":
            out["report"].append(f)
        else:
            out["watch"].append(f)
    return out


def write_brief(p: dict) -> Path | None:
    """The brain's work order for today's ONE authored fix. Includes the
    constitution verbatim — the brain is told the rules it will be held
    to."""
    if not p["authored"]:
        return None
    f = p["authored"][0]
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    brief = "\n".join([
        f"# Pipeline doctor — authored fix for {p['date']}",
        "",
        f"## Finding `{f['signature']}` ({f['severity']})",
        "",
        f["brief"] or f["detail"],
        "",
        "## How you work",
        "",
        "You are the pipeline doctor's brain: one bounded fix, done well.",
        "Read the code before editing it. Fix causes, not symptoms. Add a",
        "test that fails before your fix and passes after. Run",
        "`python -m unittest discover -s tests` yourself before you finish.",
        "Your final message must be a one-paragraph summary of what you",
        "changed and why — it becomes the PR body.",
        "",
        "## The constitution",
        "",
        constitution_text(),
    ])
    path = STATE_DIR / f"brief-{p['date']}.md"
    path.write_text(brief + "\n")
    return path


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------
def render(p: dict, resolutions: list[dict]) -> str:
    lines = [f"## Pipeline doctor — {p['date']}", ""]
    if resolutions:
        lines.append("### Yesterday's actions, judged by outcome")
        for r in resolutions:
            mark = "✅" if r["outcome"] == "resolved" else "❌"
            lines.append(f"- {mark} `{r['signature']}` — {r['detail']}")
        lines.append("")
    for bucket, label in (("mechanical", "Mechanical actions"),
                          ("authored", "Authored fix (via PR + full gate)"),
                          ("report", "NEEDS YOU"),
                          ("watch", "Watching")):
        if p[bucket]:
            lines.append(f"### {label}")
            for f in p[bucket]:
                lines.append(f"- **`{f['signature']}`** — "
                             f"{f.get('escalated') or f['detail'][:200]}")
            lines.append("")
    if not any(p[b] for b in ("mechanical", "authored", "report")):
        lines.append("Nothing needed doing. Staying quiet.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="gather, diagnose, plan, write brief")
    run.add_argument("--date", default=None, help="judged date (YYYYMMDD, "
                     "default: yesterday UTC — a finished day)")
    run.add_argument("--json", action="store_true")
    run.add_argument("--no-write", action="store_true",
                     help="diagnose only; write no brief/plan/journal")

    rev = sub.add_parser("review-diff",
                         help="constitution check; exit 1 on refusal")
    rev.add_argument("diff", help="path to a unified diff, or - for stdin")

    rec = sub.add_parser("record", help="append a journal entry")
    rec.add_argument("--signature", required=True)
    rec.add_argument("--kind", required=True,
                     choices=["mechanical", "authored", "report"])
    rec.add_argument("--action", required=True)
    rec.add_argument("--date", default=None)
    rec.add_argument("--expect-absent", default=None,
                     help="alarm code this action should clear")
    rec.add_argument("--outcome", default="pending",
                     choices=["pending", "resolved", "failed"])

    args = ap.parse_args()

    if args.cmd == "review-diff":
        text = (sys.stdin.read() if args.diff == "-"
                else Path(args.diff).read_text())
        problems = review_diff(text)
        for pr in problems:
            print(f"REFUSED: {pr}")
        if not problems:
            print("constitution: diff is within the rules")
        return 1 if problems else 0

    if args.cmd == "record":
        date = args.date or datetime.now(timezone.utc).strftime("%Y%m%d")
        append_journal({"date": date, "signature": args.signature,
                        "kind": args.kind, "action": args.action,
                        "action_id": f"{date}:{args.signature}",
                        "expect_absent": args.expect_absent,
                        "outcome": args.outcome})
        print(f"journaled {args.signature} ({args.outcome})")
        return 0

    # default: run
    date = getattr(args, "date", None)
    if not date:
        date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y%m%d")
    ev = gather(date)
    resolutions = [] if getattr(args, "no_write", False) else \
        close_the_loop(ev)
    findings = diagnose(ev)
    p = plan(findings, ev["journal"], date)

    if not getattr(args, "no_write", False):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"plan-{date}.json").write_text(
            json.dumps(p, indent=2) + "\n")
        write_brief(p)

    if getattr(args, "json", False):
        print(json.dumps({"plan": p, "resolutions": resolutions}, indent=2))
    else:
        print(render(p, resolutions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
