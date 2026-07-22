#!/usr/bin/env python3
"""Serialize + ENFORCE the blind vision taste verdict.

The taste verdict (data_learning/TASTE_JUDGE.md) is the one gate a script cannot
compute: it is a fresh vision subagent looking at the blind evidence package
``<out>_pkg/`` (contact_sheet.png, frame_{begin,mid,end}.png, camera_trace.*,
clip_lowres.mp4) with NO code / intent / beat names, answering the one-second
question "would anyone actually watch this, or is it a soulless infographic?".

Until now that verdict lived only in commit messages — so ``produce.py`` fails
closed on every real render because ``<out>_pkg/verdict.json`` never exists. This
module is the missing serialization step: the orchestrator pipes the subagent's
JSON through here, which VALIDATES it against the TASTE_JUDGE contract and writes
it atomically to the package. A malformed or dishonest verdict is rejected here,
not silently trusted.

The contract ``produce.py`` reads (TASTE_JUDGE.md lines 69-72):

    {"pass": bool, "reject_labels": [...], "card_fraction_estimate": 0.0-1.0,
     "personality": 0-5, "one_line": "...", "worst_beat": "…", "fix": "…"}

    pass is true ONLY with no reject_labels AND personality >= 3.

Usage (orchestrator, after the subagent returns its object):
    python scripts/judge_verdict.py <out.mp4> verdict_from_agent.json
    cat verdict_from_agent.json | python scripts/judge_verdict.py <out.mp4> -
    # exit 0 = written & PASS, 6 = written & REJECT, 2 = invalid verdict (nothing written)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# The automatic-REJECT vocabulary, verbatim from TASTE_JUDGE.md ("any one = fail").
REJECT_LABELS = frozenset({
    "INFOGRAPHIC_REEL", "NO_CHARACTER", "NO_SOUL", "SAMENESS",
    "EMPTY_COMPOSITION", "BORING", "LOW_ENERGY", "CARDS_OVER_BUDGET",
    "CHEAP_TYPOGRAPHY", "UI_WIDGET",
})
PERSONALITY_PASS = 3            # TASTE_JUDGE.md: personality >= 3 to pass


class InvalidVerdict(ValueError):
    """The subagent's verdict does not satisfy the TASTE_JUDGE contract."""


def validate(v: dict) -> dict:
    """Normalize + enforce the TASTE_JUDGE object. Raises InvalidVerdict on any
    contract violation (unknown label, out-of-range personality, a `pass` that
    disagrees with the pass rule). Returns the canonical verdict dict."""
    if not isinstance(v, dict):
        raise InvalidVerdict(f"verdict must be a JSON object, got {type(v).__name__}")

    labels = v.get("reject_labels", [])
    if not isinstance(labels, list):
        raise InvalidVerdict("reject_labels must be a list")
    labels = [str(x).strip().upper() for x in labels if str(x).strip()]
    unknown = [x for x in labels if x not in REJECT_LABELS]
    if unknown:
        raise InvalidVerdict(
            f"unknown reject_labels {unknown}; the vocabulary is "
            f"{sorted(REJECT_LABELS)} (TASTE_JUDGE.md)")

    if "personality" not in v:
        raise InvalidVerdict("verdict missing required 'personality' (0-5)")
    try:
        personality = float(v["personality"])
    except (TypeError, ValueError):
        raise InvalidVerdict(f"personality must be a number, got {v['personality']!r}")
    if not 0 <= personality <= 5:
        raise InvalidVerdict(f"personality {personality} out of range 0-5")

    # The pass rule is derived, never taken on faith. If the agent supplied a
    # `pass`, it must AGREE with the rule — a mismatch means the agent misjudged
    # its own rubric, and we fail closed rather than trust the boolean.
    rule_pass = (not labels) and personality >= PERSONALITY_PASS
    if "pass" in v and bool(v["pass"]) != rule_pass:
        raise InvalidVerdict(
            f"pass={v['pass']} contradicts the rule (no reject_labels AND "
            f"personality>={PERSONALITY_PASS}): labels={labels} "
            f"personality={personality} => pass should be {rule_pass}")

    cfe = v.get("card_fraction_estimate")
    if cfe is not None:
        try:
            cfe = float(cfe)
        except (TypeError, ValueError):
            raise InvalidVerdict(f"card_fraction_estimate must be numeric, got {cfe!r}")
        if not 0 <= cfe <= 1:
            raise InvalidVerdict(f"card_fraction_estimate {cfe} out of range 0-1")

    return {
        "pass": rule_pass,
        "reject_labels": labels,
        "personality": personality,
        "card_fraction_estimate": cfe,
        "one_line": str(v.get("one_line", "")).strip(),
        "worst_beat": str(v.get("worst_beat", "")).strip(),
        "fix": str(v.get("fix", "")).strip(),
        "judge": "taste",            # provenance of which rubric produced this
        "source": "vision_subagent",
    }


def pkg_dir(out: Path) -> Path:
    """The evidence-package dir for a render, matching pro_render/produce
    (`<out>` -> `<stem>_pkg` beside it)."""
    return out.with_name(out.stem + "_pkg")


def write(out: Path, verdict: dict) -> Path:
    """Validate `verdict` and write it to `<out>_pkg/verdict.json` atomically.
    Returns the path written. The package dir must already exist (the render
    built it) — we never publish a verdict for a render that never happened."""
    pkg = pkg_dir(out)
    if not pkg.exists():
        raise FileNotFoundError(
            f"no evidence package at {pkg} — render the story (which builds the "
            "blind package) before writing its verdict")
    clean = validate(verdict)
    dest = pkg / "verdict.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2))
    tmp.replace(dest)
    return dest


def _load(src: str) -> dict:
    text = sys.stdin.read() if src == "-" else Path(src).read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise InvalidVerdict(f"verdict is not valid JSON: {e}")


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Validate + write a taste verdict.")
    ap.add_argument("out", type=Path, help="the rendered mp4 (its _pkg/ holds the package)")
    ap.add_argument("verdict", help="verdict JSON file, or '-' to read stdin")
    a = ap.parse_args(argv)
    try:
        verdict = _load(a.verdict)
        dest = write(a.out, verdict)
    except (InvalidVerdict, FileNotFoundError) as e:
        print(f"[judge_verdict] REFUSED: {e}", file=sys.stderr)
        return 2
    clean = json.loads(dest.read_text())
    tag = "PASS" if clean["pass"] else "REJECT"
    print(f"[judge_verdict] {tag} -> {dest} "
          f"(personality={clean['personality']}, labels={clean['reject_labels']})")
    return 0 if clean["pass"] else 6


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
