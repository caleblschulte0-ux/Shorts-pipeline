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
import hashlib
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
    "shared/package_schema.py": "the one structural gate every package "
                                "producer is held to",
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
    # No \b around these: a good proposal cites a metric name like
    # `median_views` or `avg_view_pct`, and `\bmedian\b` does not match
    # inside snake_case because `_` is a word character. That rejected
    # exactly the well-specified proposals it was meant to reward.
    if how and not _NUM.search(how) and not re.search(
            r"(scoreboard|percentile|rate|count|median|analytics|pct|"
            r"views|duration|impressions|ctr|retention|per hour|vph)",
            how, re.I):
        out.append("how_we_would_know is not measurable — name the metric "
                   "that would move, or the number it must reach")
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


# --------------------------------------------------------------------------
# Evidence validation — a number in prose is not evidence
# --------------------------------------------------------------------------
def _walk(obj, prefix=""):
    """Every leaf in the brief, addressed by dotted path."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def load_brief(date: str) -> dict | None:
    try:
        return json.loads((RETRO_ROOT / date / "brief.json").read_text())
    except Exception:                                # noqa: BLE001
        return None


def _numbers_in(text: str) -> list[str]:
    """Numeric tokens a proposal asserts. Percentages and counts both."""
    return re.findall(r"-?\d+(?:\.\d+)?", str(text or ""))


def check_evidence(p: dict, brief: dict | None) -> list[str]:
    """Every number in the observation must exist in the brief.

    Without this, "graph_race sits at p12 vs 47 for text_card" passes the
    shape check purely because it contains digits — and a confident
    hallucination is far more dangerous than a vague one, because it reads
    like rigour and gets adopted.

    Deliberately lenient about WHERE the number appears: matching an exact
    dotted path would reject honest arithmetic like a ratio or a total. The
    rule is that the raw values must be findable in the brief."""
    if brief is None:
        return ["cannot verify evidence: no brief.json for this date"]

    values = set()
    for _, v in _walk(brief):
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, (int, float)):
            values.add(f"{float(v):g}")
            values.add(f"{round(float(v)):g}")
    paths = {path for path, _ in _walk(brief)}

    out = []
    refs = p.get("evidence") or []
    if not refs:
        out.append("no `evidence` — cite the brief fields you reasoned from")
    for ref in refs:
        ref = str(ref)
        # A reference resolves if it names a path in the brief, or a file
        # the brief itself points at.
        if not (any(path.startswith(ref) or ref.startswith(path.split("[")[0])
                    for path in paths)
                or ref.startswith(("state/", "retro/", "exchange/", "docs/"))):
            out.append(f"evidence reference {ref!r} is not a field in "
                       f"brief.json (or a file it cites)")

    # Which numbers are CLAIMS worth verifying?
    #   decimals        always — "p12.4", "0.16 vph" is asserted precision,
    #                   and hallucinated precision is the dangerous kind
    #   big integers    always — "1,200 impressions" is a measurement
    #   small integers  no — "8 videos", "3 formats" are prose counts, and
    #                   flagging them buries the real cases in noise
    def _is_claim(tok: str) -> bool:
        v = float(tok)
        return (not v.is_integer()) or abs(v) >= 100

    unmatched = [n for n in _numbers_in(p.get("observation"))
                 if _is_claim(n) and f"{float(n):g}" not in values]
    if unmatched:
        out.append(f"observation asserts number(s) not present anywhere in "
                   f"brief.json: {', '.join(unmatched[:6])} — either cite a "
                   f"real value or say the data does not exist")
    return out


# --------------------------------------------------------------------------
# Thrash control — the loop must not rewrite the channel every day
# --------------------------------------------------------------------------
COOLDOWN_DAYS = 21
MAX_ACTIVE_PER_CHANNEL = 1


def signature(p: dict) -> str:
    """Stable identity for "the same idea again".

    Keyed on WHAT THE CHANGE TOUCHES — channel, format, files — not on how
    it was worded. The same edit to the same files on the same channel is
    the same proposal whether it arrives as "shorten the graph hook" or
    "the graph hook should be shorter", and a dedupe that keys on title
    words is defeated by a thesaurus.

    Title words are the fallback only when no files are named (a pure
    editorial proposal), where they are the only identity available."""
    files = sorted(str(f) for f in p.get("files") or [])
    parts = [str(p.get("channel") or ""), str(p.get("format") or "")]
    if files:
        parts.append(",".join(files))
    else:
        words = sorted(set(re.findall(
            r"[a-z]{4,}", str(p.get("title") or "").lower())))
        parts.append(",".join(words[:6]))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def check_duplicates(p: dict, history: list[dict]) -> list[str]:
    """Refuse a re-file of something already decided, unless it brings new
    evidence. A reviewer that re-proposes yesterday's declined idea in new
    words is not learning, and answering it again teaches it that
    persistence works."""
    sig = p.get("signature") or signature(p)
    out = []
    for h in history:
        if h.get("signature") != sig:
            continue
        verdict = h.get("verdict")
        if verdict in ("decline", "needs_evidence") and not p.get(
                "new_evidence_since"):
            out.append(
                f"already {verdict}d on {h.get('date')} "
                f"({h.get('because', '')[:80]}) — re-file only with "
                f"`new_evidence_since` naming what changed")
        elif verdict == "adopt":
            out.append(f"already adopted on {h.get('date')} — if it did not "
                       f"work, that is a readout, not a new proposal")
    return out


def check_capacity(p: dict, active_by_channel: dict) -> list[str]:
    """One editorial experiment per channel at a time. Two overlapping
    changes on one channel make both unreadable — neither verdict can be
    attributed."""
    ch = str(p.get("channel") or "")
    if not ch or p.get("category") in ("watch", None):
        return []
    live = active_by_channel.get(ch) or []
    if len(live) >= MAX_ACTIVE_PER_CHANNEL:
        return [f"{ch} already has an unresolved experiment "
                f"({live[0]}) — a second concurrent change makes both "
                f"unreadable. Wait for the readout, or propose a `watch`."]
    return []


def load_proposals(date: str) -> list[tuple[str, dict]]:
    """(name, proposal) pairs from the ONE answer file, or the legacy
    per-file layout. `proposals.json` is canonical — a single file is what
    makes "already answered" checkable, and therefore idempotent."""
    out: list[tuple[str, dict]] = []
    single = RETRO_ROOT / date / "proposals.json"
    if single.exists():
        try:
            body = json.loads(single.read_text())
            items = body.get("proposals") if isinstance(body, dict) else body
            for i, pr in enumerate(items or []):
                if isinstance(pr, dict):
                    out.append((pr.get("proposal_id") or f"proposals.json[{i}]",
                                pr))
        except Exception as exc:                     # noqa: BLE001
            out.append(("proposals.json", {"_unreadable": str(exc)}))
    pdir = RETRO_ROOT / date / "proposals"
    if pdir.is_dir():
        for f in sorted(pdir.glob("*.json")):
            try:
                out.append((f.name, json.loads(f.read_text())))
            except Exception as exc:                 # noqa: BLE001
                out.append((f.name, {"_unreadable": str(exc)}))
    return out


def prior_decisions() -> list[dict]:
    """Everything Claude has already ruled on — the dedupe memory."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from retro_reply import read_ledger
        return read_ledger()
    except Exception:                                # noqa: BLE001
        return []


def active_experiments_by_channel() -> dict:
    try:
        from shared import experiments as ex
        out: dict[str, list[str]] = {}
        for e in ex.running():
            out.setdefault(e.get("channel") or "", []).append(e.get("id"))
        return out
    except Exception:                                # noqa: BLE001
        return {}


def triage(date: str) -> dict:
    report = {"schema": "shorts-retro-triage/v1", "date": date,
              "reviewed_at": datetime.now(timezone.utc).strftime(
                  "%Y-%m-%dT%H:%M:%SZ"),
              "refused": [], "requires_operator": [], "accepted": [],
              "malformed": [], "duplicate": [], "counts": {}}
    items = load_proposals(date)
    if not items:
        report["note"] = f"no proposals for {date}"
        return report

    brief = load_brief(date)
    history = prior_decisions()
    active = active_experiments_by_channel()

    for name, p in items:
        f = type("F", (), {"name": name})()
        if p.get("_unreadable"):
            report["malformed"].append(
                {"file": name, "problems": [f"unreadable: {p['_unreadable']}"]})
            continue
        entry = {"file": name, "signature": signature(p),
                 "proposal_id": p.get("proposal_id"),
                 "channel": p.get("channel"), "title": p.get("title"),
                 "category": p.get("category"),
                 "confidence": p.get("confidence"),
                 "files": p.get("files") or []}

        forbidden = check_forbidden(p)
        if forbidden:
            # Checked FIRST and unconditionally: a policy violation is not
            # redeemed by being well-formed or well-evidenced.
            report["refused"].append({**entry, "violations": forbidden})
            continue
        dupes = check_duplicates(p, history)
        if dupes:
            # Not malformed and not a policy violation — just already
            # decided. Kept as its own bucket so a reviewer re-filing the
            # same idea sees that it was answered, not ignored.
            report["duplicate"].append({**entry, "because": dupes})
            continue
        shape = check_shape(p) + check_evidence(p, brief) + check_capacity(
            p, active)
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

    for k in ("refused", "requires_operator", "accepted", "duplicate"):
        report[k].sort(key=lambda e: -e.get("score", 0))
    report["counts"] = {k: len(report[k]) for k in
                        ("accepted", "requires_operator", "refused",
                         "malformed", "duplicate")}
    return report


def digest(r: dict) -> str:
    L = [f"# Retro triage — {r['date']}", "",
         f"accepted {r['counts'].get('accepted', 0)} · "
         f"operator {r['counts'].get('requires_operator', 0)} · "
         f"refused {r['counts'].get('refused', 0)} · "
         f"duplicate {r['counts'].get('duplicate', 0)} · "
         f"malformed {r['counts'].get('malformed', 0)}", ""]
    if r.get("note"):
        L += [f"_{r['note']}_", ""]
    for key, head in (("accepted", "## Worth considering"),
                      ("requires_operator", "## Operator decision required"),
                      ("refused", "## REFUSED — policy violation"),
                      ("duplicate", "## Already decided (re-filed)"),
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
