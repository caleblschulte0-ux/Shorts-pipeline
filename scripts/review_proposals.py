#!/usr/bin/env python3
"""Triage the day's retro proposals. REFUSES the ones that lower the bar.

The retro loop's whole risk is that the cheapest way to make the numbers go
up is to weaken a gate — skip the showrunner, relax the claim guard, ship
more of whatever is easiest. A reviewer under pressure to produce findings
will eventually propose exactly that, and it will be well-argued. So the
refusal is mechanical, not a matter of judgement in the moment.

This script never edits anything. It reads
`retro/<date>/proposals/*.json`, sorts them into:

    refused           touches a protected invariant — policy violation
    requires_operator touches load-bearing code; a human decides, always
    accepted          well-formed and safe to consider
    malformed         missing required fields, or an unverifiable claim

and writes `retro/<date>/triage.json` + prints a ranked digest. A reviewer
with commit access reads that and decides. Nothing ships from here.

    python scripts/review_proposals.py                  # today
    python scripts/review_proposals.py --date 20260731
    python scripts/review_proposals.py --strict         # exit 1 on refusals
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETRO_ROOT = ROOT / "retro"

REQUIRED = ("title", "category", "confidence", "observation", "proposal",
            "expected_effect", "how_we_would_know", "risks")
CATEGORIES = ("content", "code", "config", "watch")
CONFIDENCES = ("low", "medium", "high")

# ---------------------------------------------------------------------------
# PROTECTED INVARIANTS. Each of these exists because it already caught a real
# failure; every one is documented in CLAUDE.md or docs/. A proposal that
# touches one is refused as policy, not weighed as an idea.
# ---------------------------------------------------------------------------
PROTECTED_FILES = {
    "scripts/showrunner_review.py": "the showrunner's BLOCK is sovereign",
    "scripts/post_stories.py": "it fails CLOSED on a publish run by design",
    "shared/punchup_guard.py": "it stops rewrites inventing facts",
    "scripts/placement_gate.py": "it keeps shared capability up the funnel",
    "shared/package_buffer.py": "draw-once is what prevents duplicate uploads",
    "docs/DIRECTOR.md": "the rubric the showrunner judges against",
}
PROTECTED_PATTERNS = (
    (r"posted[_ ]log", "posted logs are append-only dedupe state — losing an "
                       "entry means a duplicate upload"),
    (r"showrunner", "the showrunner is the permanent quality authority; code "
                    "may only ever ADD blocks, never remove one"),
)
# Phrases that describe lowering a bar. Matched against the proposal text.
FORBIDDEN_INTENT = (
    (r"\b(disabl|bypass|skip|turn off|switch off|remove)\w*\b[^.]{0,40}"
     r"\b(gate|check|guard|test|showrunner|verdict|review|validation)",
     "proposes disabling a gate"),
    (r"\bshowrunner\s*=\s*off|SHOWRUNNER=off", "proposes SHOWRUNNER=off"),
    (r"\b(lower|reduce|relax|loosen|drop|soften)\w*\b[^.]{0,40}"
     r"\b(bar|floor|threshold|gate|standard|guard|min_score|requirement)",
     "proposes lowering a quality bar"),
    (r"\b(more|increase|raise|boost)\b[^.]{0,30}\b(videos?|posts?|volume|"
     r"output|slots?)\b[^.]{0,40}\b(by|through|via)\b[^.]{0,40}"
     r"\b(lower|relax|skip|reduc)", "proposes more output via a lower bar"),
    (r"\b(fabricat|invent|synthes|make up)\w*\b[^.]{0,30}"
     r"\b(data|number|statistic|analytics|source)",
     "proposes fabricating data"),
    (r"\bdelete\b[^.]{0,30}\btest", "proposes deleting a test"),
)
# Load-bearing but legitimately changeable — a human decides, every time.
OPERATOR_REVIEW_FILES = (
    "daily.yml", "explainer.yml", "third.yml", "curiosity.yml",
    "auto-merge.yml", "exchange_phase_a.yml", "exchange_phase_b.yml",
    "uploaders.py", "run_trending_daily.py", "build_mascot_svg.py",
    "CLAUDE.md", "CLAUDE_ROUTINE_INSTRUCTIONS.md",
)

_NUM = re.compile(r"\d")


def _text_of(p: dict) -> str:
    return " ".join(str(p.get(k) or "") for k in
                    ("title", "observation", "proposal", "expected_effect"))


def check_forbidden(p: dict) -> list[str]:
    """Policy violations. Refusal, not a score."""
    out = []
    blob = _text_of(p).lower()
    for pattern, why in FORBIDDEN_INTENT:
        if re.search(pattern, blob, re.I):
            out.append(why)
    for f in p.get("files") or []:
        f = str(f)
        for prot, why in PROTECTED_FILES.items():
            if f.endswith(prot) or prot.endswith(f):
                out.append(f"touches {prot} — {why}")
        for pattern, why in PROTECTED_PATTERNS:
            if re.search(pattern, f, re.I):
                out.append(f"touches {f} — {why}")
    for pattern, why in PROTECTED_PATTERNS:
        if re.search(pattern, blob, re.I) and re.search(
                r"\b(weaken|remove|relax|bypass|skip|disable|edit|rewrite|"
                r"prune|trim|clean)\w*", blob, re.I):
            out.append(why)
    return sorted(set(out))


def check_shape(p: dict) -> list[str]:
    out = [f"missing `{k}`" for k in REQUIRED if not str(p.get(k) or "").strip()]
    if p.get("category") and p["category"] not in CATEGORIES:
        out.append(f"category {p['category']!r} not in {CATEGORIES}")
    if p.get("confidence") and p["confidence"] not in CONFIDENCES:
        out.append(f"confidence {p['confidence']!r} not in {CONFIDENCES}")
    obs = str(p.get("observation") or "")
    if obs and not _NUM.search(obs):
        out.append("observation cites no numbers — it cannot be checked "
                   "against the brief")
    how = str(p.get("how_we_would_know") or "")
    if how and not _NUM.search(how) and not re.search(
            r"\b(scoreboard|percentile|rate|count|median|analytics|pct|"
            r"per hour|vph)\b", how, re.I):
        out.append("how_we_would_know is not measurable")
    return out


def needs_operator(p: dict) -> list[str]:
    hits = []
    for f in p.get("files") or []:
        for name in OPERATOR_REVIEW_FILES:
            if str(f).endswith(name):
                hits.append(f"{f} is load-bearing")
    if str(p.get("confidence")) == "low" and p.get("files"):
        hits.append("low confidence with a code change attached")
    return sorted(set(hits))


def score(p: dict) -> float:
    """Evidence strength — ranking only, never an approval."""
    s = {"high": 3.0, "medium": 2.0, "low": 1.0}.get(p.get("confidence"), 1.0)
    s += 0.5 * min(len(p.get("evidence") or []), 4)
    if len(_NUM.findall(str(p.get("observation") or ""))) >= 3:
        s += 1.0                                     # argues with numbers
    if p.get("rollback"):
        s += 0.5                                     # reversible
    if str(p.get("risks") or "").strip().lower() in ("none", "no risk", "n/a"):
        s -= 1.0                                     # nothing is riskless
    if len(p.get("files") or []) > 4:
        s -= 0.5                                     # sprawling change
    return round(s, 2)


def triage(date: str) -> dict:
    pdir = RETRO_ROOT / date / "proposals"
    report = {"schema": "shorts-retro-triage/v1", "date": date,
              "reviewed_at": datetime.now(timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ"),
              "refused": [], "requires_operator": [], "accepted": [],
              "malformed": [], "counts": {}}
    if not pdir.is_dir():
        report["note"] = f"no proposals directory for {date}"
        return report

    for f in sorted(pdir.glob("*.json")):
        try:
            p = json.loads(f.read_text())
        except Exception as exc:                     # noqa: BLE001
            report["malformed"].append(
                {"file": f.name, "problems": [f"unreadable: {exc}"]})
            continue
        entry = {"file": f.name, "title": p.get("title"),
                 "category": p.get("category"),
                 "confidence": p.get("confidence"),
                 "files": p.get("files") or []}

        forbidden = check_forbidden(p)
        if forbidden:
            # Checked FIRST and unconditionally: a policy violation is not
            # redeemed by being well-formed or well-evidenced.
            report["refused"].append({**entry, "violations": forbidden})
            continue
        shape = check_shape(p)
        if shape:
            report["malformed"].append({**entry, "problems": shape})
            continue
        entry["score"] = score(p)
        entry["proposal"] = p.get("proposal")
        op = needs_operator(p)
        if op:
            report["requires_operator"].append({**entry, "because": op})
        else:
            report["accepted"].append(entry)

    for k in ("refused", "requires_operator", "accepted"):
        report[k].sort(key=lambda e: -e.get("score", 0))
    report["counts"] = {k: len(report[k]) for k in
                        ("accepted", "requires_operator", "refused",
                         "malformed")}
    return report


def digest(r: dict) -> str:
    L = [f"# Retro triage — {r['date']}", "",
         f"accepted {r['counts'].get('accepted', 0)} · "
         f"operator {r['counts'].get('requires_operator', 0)} · "
         f"refused {r['counts'].get('refused', 0)} · "
         f"malformed {r['counts'].get('malformed', 0)}", ""]
    if r.get("note"):
        L += [f"_{r['note']}_", ""]
    for key, head in (("accepted", "## Worth considering"),
                      ("requires_operator", "## Operator decision required"),
                      ("refused", "## REFUSED — policy violation"),
                      ("malformed", "## Malformed")):
        rows = r.get(key) or []
        if not rows:
            continue
        L += [head, ""]
        for e in rows:
            sc = f" (score {e['score']})" if e.get("score") is not None else ""
            L.append(f"- **{e.get('title')}**{sc}")
            for why in (e.get("violations") or e.get("because")
                        or e.get("problems") or []):
                L.append(f"    - {why}")
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default="")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any proposal was refused")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    date = args.date or datetime.now(timezone.utc).strftime("%Y%m%d")
    r = triage(date)
    print(json.dumps(r, indent=2) if args.json else digest(r))

    out = RETRO_ROOT / date
    if out.is_dir():
        (out / "triage.json").write_text(json.dumps(r, indent=2) + "\n")
        (out / "triage.md").write_text(digest(r))
    for e in r["refused"]:
        print(f"::warning::retro proposal REFUSED — {e.get('title')}: "
              f"{'; '.join(e['violations'])[:150]}")
    return 1 if (args.strict and r["refused"]) else 0


if __name__ == "__main__":
    sys.exit(main())
