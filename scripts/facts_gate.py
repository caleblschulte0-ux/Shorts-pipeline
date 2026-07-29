#!/usr/bin/env python3
"""FACTS GATE (Phase 9) — machine-readable provenance for every spoken number.

A curiosity story that opts in with top-level ``"require_provenance": true``
must ship a claim registry ``data_learning/pro_stories/<slug>.facts.json``
whose claims satisfy the schema below, and every beat whose narration speaks a
number must be covered by a claim. Publishing BLOCKS when any of these fail
(assignment Phase 9):

    - a major number has no claim          -> uncovered numeric beat
    - a source is missing / described vaguely
    - geography missing on a statistical claim
    - a modeled figure presented as universal fact (presentation field)
    - calculation absent on derived/modeled claims
    - assumptions hidden (empty)
    - a time-sensitive source is stale (publication_date too old)
    - the source type is unacceptable

Distinct from media credits: this gate sources the CLAIMS the narration makes,
not the images shown. Writes ``<out>.facts-report.json`` next to the video so
the verdict is auditable.

SEMANTIC LAYER (PR#173 adoption: semantic_claims): beyond spoken numbers, a
sentence-level detector finds historical / superlative / comparative / causal
/ scientific / attributed claims in EVERY beat's narration and audits them
against the same registry. Advisory by default (coverage + uncovered
sentences land in the report as warnings); a story that opts in with
top-level ``"require_semantic_provenance": true`` turns uncovered semantic
claims into hard blocks. A registry claim may declare ``"claim_type"``
(numeric/historical/superlative/comparative/causal/scientific/attributed/
geographic); without one it counts as general-fact and covers any claim
type on its beats.

    python3 scripts/facts_gate.py <slug> [--out output/curiosity_<slug>.mp4]
    exit 0 = pass, 7 = blocked, 2 = story/registry unreadable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRO_STORIES = REPO / "data_learning" / "pro_stories"
if str(REPO / "experiments") not in sys.path:
    sys.path.insert(0, str(REPO / "experiments"))

ACCEPTABLE_SOURCE_TYPES = {"primary", "official", "academic", "journalistic",
                           "reference", "derived"}
# 'derived' is acceptable ONLY with a reproducible calculation (checked below).
REQUIRED_KEYS = ("id", "claim", "source_title", "publisher", "source_type",
                 "publication_date", "accessed_date", "geography",
                 "assumptions")
VAGUE_SOURCES = re.compile(
    r"^(the internet|online|google|various|misc|unknown|studies|research"
    r"|experts|sources)\.?$", re.I)
# Narration that speaks a quantity: digits, or spelled money/percent scale words.
NUMERIC = re.compile(
    r"\d|(?:\b(?:million|billion|thousand|hundred|percent|cents?\b|"
    r"half|third|quarter)\b)", re.I)
STALE_YEARS = 6          # a time-sensitive source older than this blocks


def _load(slug: str) -> tuple[dict, dict | None]:
    story = json.loads((PRO_STORIES / f"{slug}.beats.json").read_text())
    fpath = PRO_STORIES / f"{slug}.facts.json"
    registry = json.loads(fpath.read_text()) if fpath.exists() else None
    return story, registry


def _check_claim(c: dict, today: date) -> list[str]:
    errs = []
    cid = c.get("id", "<no id>")
    for k in REQUIRED_KEYS:
        v = c.get(k)
        if v in (None, "", []):
            errs.append(f"{cid}: missing required field {k!r}")
    st = c.get("source_type")
    if st and st not in ACCEPTABLE_SOURCE_TYPES:
        errs.append(f"{cid}: source_type {st!r} not in "
                    f"{sorted(ACCEPTABLE_SOURCE_TYPES)}")
    src = f"{c.get('source_title', '')} {c.get('publisher', '')}".strip()
    if src and VAGUE_SOURCES.match(src):
        errs.append(f"{cid}: source described too vaguely: {src!r}")
    if st in ("derived",) and not (c.get("calculation") or "").strip():
        errs.append(f"{cid}: derived claim with no reproducible calculation")
    if c.get("presentation") == "universal_fact" and c.get("calculation"):
        errs.append(f"{cid}: modeled figure (has calculation) presented as "
                    "universal fact — label it illustrative_model or drop the "
                    "calculation framing")
    try:
        pub = datetime.strptime(c.get("publication_date", ""),
                                "%Y-%m-%d").date()
        if c.get("time_sensitive", True) and st != "derived" and \
                (today - pub).days > STALE_YEARS * 365:
            errs.append(f"{cid}: source published {pub.isoformat()} is stale "
                        f"(> {STALE_YEARS}y) for a time-sensitive claim")
    except ValueError:
        errs.append(f"{cid}: publication_date not YYYY-MM-DD")
    return errs


def _semantic_audit(beats: list[dict], claims: list[dict]) -> dict:
    """Sentence-level claim discovery over ALL narrations, audited against
    the registry (semantic_claims adapter). Returns a JSON-ready section;
    raises nothing — callers decide whether its findings block."""
    from curiosity_nextgen.claim_registry import Claim, ClaimType
    from curiosity_nextgen.semantic_claims import (
        audit_semantic_coverage, extract_semantic_signals)

    beat_texts = {f"beat-{i}": str(b.get("narration") or b.get("line") or "")
                  for i, b in enumerate(beats)}
    signals = extract_semantic_signals(beat_texts, minimum_confidence=0.6)

    def _ctype(raw) -> ClaimType:
        try:
            return ClaimType(str(raw))
        except ValueError:
            return ClaimType.GENERAL_FACT   # covers any type on its beats

    mapped = []
    for c in claims:
        beat_ids = []
        if isinstance(c.get("beat_index"), int):
            beat_ids.append(f"beat-{c['beat_index']}")
        beat_ids += [f"beat-{eb}" for eb in c.get("echo_beats", [])
                     if isinstance(eb, int)]
        if not beat_ids:
            continue
        mapped.append(Claim(
            claim_id=str(c.get("id") or f"claim-{len(mapped)}"),
            beat_ids=tuple(beat_ids),
            claim_text=str(c.get("claim") or ""),
            claim_type=_ctype(c.get("claim_type")),
            geography=c.get("geography"),
            calculation=c.get("calculation")))
    # inline facts[] / claim_ids on a beat cover that beat as general-fact
    for i, b in enumerate(beats):
        if b.get("facts") or b.get("claim_ids"):
            mapped.append(Claim(
                claim_id=f"inline-beat-{i}",
                beat_ids=(f"beat-{i}",),
                claim_text="inline facts[] on the beat",
                claim_type=ClaimType.GENERAL_FACT))

    audit = audit_semantic_coverage(signals, mapped)
    sig_by_key = {s.key: s for s in signals}
    return {
        "detected": audit.detected_count,
        "covered": audit.covered_count,
        "coverage_ratio": audit.coverage_ratio,
        "uncovered": [
            {"key": k,
             "types": [t.value for t in sig_by_key[k].claim_types],
             "sentence": sig_by_key[k].sentence[:110]}
            for k in audit.uncovered_signals if k in sig_by_key],
        "type_mismatches": list(audit.type_mismatches),
        "overbroad_claims": list(audit.overbroad_claims),
        "duplicate_claim_ids": list(audit.duplicate_claim_ids),
    }


def evaluate(slug: str, today: date | None = None) -> dict:
    today = today or date.today()
    story, registry = _load(slug)
    required = bool(story.get("require_provenance"))
    beats = story.get("beats", [])
    report: dict = {"slug": slug, "require_provenance": required,
                    "errors": [], "warnings": [],
                    "claims_total": 0, "claims_valid": 0}

    if not required:
        report["pass"] = True
        report["warnings"].append("story does not require provenance "
                                  "(opt-in flag absent) — gate is advisory")
        if registry is None:
            return report

    if registry is None:
        report["pass"] = False
        report["errors"].append(
            f"require_provenance set but no claim registry "
            f"data_learning/pro_stories/{slug}.facts.json")
        return report

    claims = registry.get("claims", [])
    report["claims_total"] = len(claims)
    by_beat: dict[int, list[dict]] = {}
    seen_ids = set()
    for c in claims:
        errs = _check_claim(c, today)
        if c.get("id") in seen_ids:
            errs.append(f"duplicate claim id {c.get('id')!r}")
        seen_ids.add(c.get("id"))
        if errs:
            report["errors"].extend(errs)
        else:
            report["claims_valid"] += 1
        bi = c.get("beat_index")
        if isinstance(bi, int):
            by_beat.setdefault(bi, []).append(c)
        # echo_beats: beats that RESTATE this claim (running totals, hook and
        # payoff repeats of the model's arithmetic) are covered by it too.
        for eb in c.get("echo_beats", []):
            if isinstance(eb, int):
                by_beat.setdefault(eb, []).append(c)

    # Coverage: every beat whose NARRATION speaks a number needs a claim
    # (registry beat_index or explicit claim_ids or inline facts[]).
    numeric_beats, covered, uncovered = [], [], []
    for i, b in enumerate(beats):
        narration = str(b.get("narration") or b.get("line") or "")
        if not NUMERIC.search(narration):
            continue
        numeric_beats.append(i)
        has = (i in by_beat or b.get("claim_ids") or b.get("facts"))
        (covered if has else uncovered).append(i)
        if not has:
            report["errors"].append(
                f"beat {i} speaks a number with NO claim: "
                f"{narration[:90]!r}")
    report["coverage"] = {"numeric_beats": len(numeric_beats),
                          "covered": len(covered), "uncovered": uncovered}

    # SEMANTIC LAYER — non-numeric claims (historical/superlative/comparative/
    # causal/scientific/attributed) audited sentence-by-sentence. Advisory by
    # default; hard when the story opts in with require_semantic_provenance.
    sem_required = bool(story.get("require_semantic_provenance"))
    try:
        sem = _semantic_audit(beats, claims)
        sem["enforced"] = sem_required
        report["semantic"] = sem
        problems = []
        if sem["uncovered"]:
            problems.append(f"{len(sem['uncovered'])} semantic claim(s) "
                            "with no registry coverage, e.g. "
                            + "; ".join(f"{u['key']} [{','.join(u['types'])}] "
                                        f"{u['sentence'][:70]!r}"
                                        for u in sem["uncovered"][:3]))
        if sem["type_mismatches"]:
            problems.append(f"{len(sem['type_mismatches'])} claim-type "
                            "mismatch(es): "
                            + "; ".join(sem["type_mismatches"][:2]))
        if sem["duplicate_claim_ids"]:
            problems.append("duplicate claim ids: "
                            + ", ".join(sem["duplicate_claim_ids"][:4]))
        sink = report["errors"] if sem_required else report["warnings"]
        for p in problems:
            sink.append(("semantic: " if sem_required
                         else "semantic (advisory): ") + p)
    except Exception as e:  # noqa: BLE001
        # advisory layer must not crash the gate; ENFORCED layer fails closed
        if sem_required:
            report["errors"].append(
                f"semantic audit could not run ({str(e)[:70]}) — "
                "require_semantic_provenance fails closed")
        else:
            report["warnings"].append(
                f"semantic audit skipped ({str(e)[:70]})")

    report["pass"] = not report["errors"]
    return report


def run(slug: str, out: Path | None = None) -> int:
    try:
        report = evaluate(slug)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[facts_gate] cannot evaluate {slug}: {e}", file=sys.stderr)
        return 2
    dest = (out or (REPO / "output" / f"curiosity_{slug}.mp4"))\
        .with_suffix(".facts-report.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    tag = "PASS" if report["pass"] else "BLOCKED"
    print(f"[facts_gate] {tag} {slug}: {report['claims_valid']}/"
          f"{report['claims_total']} claims valid, coverage "
          f"{report.get('coverage', {})} -> {dest}")
    for e in report["errors"]:
        print(f"  ERROR: {e}", file=sys.stderr)
    return 0 if report["pass"] else 7


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out", type=Path, default=None,
                    help="video path the report sits beside "
                         "(default output/curiosity_<slug>.mp4)")
    a = ap.parse_args(argv)
    return run(a.slug, a.out)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
