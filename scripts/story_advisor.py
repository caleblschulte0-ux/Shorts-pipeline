#!/usr/bin/env python3
"""STORY ADVISOR — the nextgen creative/viewer cluster over REAL beats.

Maps a real story (data_learning/pro_stories/<slug>.beats.json) into the
merged reference contracts and reports, per beat and whole-story:

  - cognitive load (curiosity_nextgen.cognitive_load): speech density, concept
    stacking, number stacking, consecutive overload runs;
  - retention risk (curiosity_nextgen.retention_risk): early-exit windows,
    static stretches, repeated families;
  - payoff presence: does the ending answer the opening question at all.

HONESTY CONTRACT: everything fed in is derived MECHANICALLY from the authored
text/structure (word counts, digits, visual-family transitions) — subjective
dimensions use documented proxies and the whole report is ADVISORY: it never
blocks the pipeline (the render-time director + blind judge gate on PIXELS,
which outranks metadata). Use it while AUTHORING, before spending a render.

    python3 scripts/story_advisor.py <slug>       -> output/<slug>.advisor.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts", REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from curiosity_nextgen.cognitive_load import (        # noqa: E402
    InformationBeat, analyze_cognitive_load)
from curiosity_nextgen.retention_risk import (        # noqa: E402
    RetentionMoment, analyze_retention_risk)

WORDS_PER_SECOND = 2.6            # calm documentary narration pace
_NUMBERY = re.compile(r"\d|(?:\b(?:million|billion|thousand|hundred|percent"
                      r"|cents?|half|third|quarter)\b)", re.I)


def _visible_words(beat: dict) -> int:
    flat = beat.get("flat") or {}
    text = " ".join(str(flat.get(k, "")) for k in
                    ("title", "sub", "kicker", "text", "label"))
    for row in flat.get("rows", []) or []:
        text += " " + str(row.get("name", "")) + " " + str(row.get("display", ""))
    return len(text.split())


def _family(beat: dict) -> str:
    kind = (beat.get("flat") or {}).get("kind", "")
    if kind.startswith("scene_"):
        return "character_scene"
    if kind.startswith("flat_"):
        return "card"
    if beat.get("image"):
        return "real_media"
    if beat.get("footage"):
        return "real_media"
    return beat.get("mode", "unknown")


def beats_to_information(beats: list[dict]) -> list[InformationBeat]:
    out = []
    for i, b in enumerate(beats):
        narration = str(b.get("narration") or b.get("line") or "")
        words = narration.split()
        dur = max(1.0, len(words) / WORDS_PER_SECOND)
        numbers = len(_NUMBERY.findall(narration))
        # proxies, documented: new concepts ~ distinct capitalized mid-sentence
        # tokens + numeric ideas; entities ~ capitalized tokens.
        caps = [w for j, w in enumerate(words)
                if j and w[:1].isupper() and w.isalpha()]
        flat = b.get("flat") or {}
        vis_elems = 1 + len(flat.get("rows", []) or [])
        out.append(InformationBeat(
            beat_id=f"beat-{i}",
            duration_seconds=round(dur, 2),
            spoken_words=len(words),
            visible_words=_visible_words(b),
            new_concepts=min(6, max(0, len(set(caps)) // 2 + (numbers > 2))),
            numeric_values=numbers,
            named_entities=len(set(caps)),
            simultaneous_visual_elements=vis_elems,
            includes_example=bool(b.get("image") or b.get("footage")),
            includes_visual_mapping=bool(flat.get("rows")),
        ))
    return out


def beats_to_moments(beats: list[dict]) -> list[RetentionMoment]:
    out, t = [], 0.0
    prev_family = None
    for i, b in enumerate(beats):
        narration = str(b.get("narration") or b.get("line") or "")
        dur = max(1.0, len(narration.split()) / WORDS_PER_SECOND)
        fam = _family(b)
        numbers = len(_NUMBERY.findall(narration))
        questions = narration.count("?")
        # mechanical proxies (see module docstring): novelty from family
        # change; curiosity from questions/numbers; visual change from family
        # + designed animation; static estimate for held stills.
        # the reference contract scores on a 0-10 scale
        novelty = 9.0 if fam != prev_family else 4.5
        curiosity = min(10.0, 4.5 + 2.0 * questions + 0.5 * min(numbers, 4))
        visual_change = 8.5 if fam in ("character_scene", "card") else \
            (7.5 if fam == "real_media" else 5.0)
        static = 0.0 if fam != "real_media" else max(0.0, dur - 3.5)
        out.append(RetentionMoment(
            moment_id=f"beat-{i}", start_seconds=round(t, 2),
            duration_seconds=round(dur, 2),
            novelty=novelty, curiosity=curiosity, clarity=7.0,
            emotional_relevance=7.0 if fam == "character_scene" else 5.5,
            visual_change=visual_change, audio_change=6.0,
            proof_strength=7.0 if (b.get("facts") or b.get("claim_ids")) else 5.0,
            cognitive_load=min(10.0, 3.0 + 0.8 * numbers),
            static_seconds=round(static, 2),
            repeated_visual_family=fam == prev_family,
            payoff_moment=i >= len(beats) - 2,
        ))
        prev_family = fam
        t = round(t + round(dur, 2), 2)   # accumulate ROUNDED durations so
        # start+duration never drifts past the next start (overlap guard)
    return out


def advise(slug: str, story_path: Path | None = None) -> dict:
    """Advise on a story. `story_path` lets a caller that already resolved the
    beats file (the producer) pass it in rather than re-resolving by slug."""
    story_path = story_path or (REPO / "data_learning" / "pro_stories"
                                / f"{slug}.beats.json")
    story = json.loads(Path(story_path).read_text())
    beats = story.get("beats", [])
    if not beats:
        # ValueError, NOT SystemExit: callers embed this inside a render
        # (produce.py wraps it in `except Exception`) and an advisory layer
        # must never be able to terminate the producer. main() below still
        # exits nonzero for the CLI.
        raise ValueError(f"{slug}: no beats")
    load = analyze_cognitive_load(beats_to_information(beats))
    retention = analyze_retention_risk(beats_to_moments(beats))
    hook = str(beats[0].get("narration", ""))
    tail = " ".join(str(b.get("narration", "")) for b in beats[-3:])
    payoff_note = None
    hook_terms = {w.lower().strip(".,?!") for w in hook.split() if len(w) > 4}
    if hook_terms and not (hook_terms & {w.lower().strip(".,?!")
                                         for w in tail.split()}):
        payoff_note = ("the ending never re-touches the opening's key terms — "
                       "check that the hook's promise is visibly answered")
    report = {
        "slug": slug,
        "advisory": True,
        "cognitive_load": {
            "decision": load.decision.value,
            "average": load.average_load,
            "peak": load.peak_load,
            "overloaded_beats": list(load.overloaded_beats),
            "overload_runs": [list(r) for r in load.consecutive_overload_runs],
            "repairs": list(load.repairs),
        },
        "retention": {
            "overall_score": retention.overall_risk_score,
            "level": retention.risk_level.value,
            "early_risk": retention.early_risk_score,
            "ending_risk": retention.ending_risk_score,
            "worst_moments": [
                {"id": m.moment_id, "score": m.risk_score,
                 "defects": [d.code for d in m.defects]}
                for m in sorted(retention.moment_risks,
                                key=lambda m: -m.risk_score)[:5]],
        },
        "payoff_note": payoff_note,
    }
    dest = REPO / "output" / f"{slug}.advisor.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[advisor] {slug}: load={report['cognitive_load']['decision']} "
          f"retention={report['retention']['level']} -> {dest}")
    return report


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    a = ap.parse_args(argv)
    try:
        advise(a.slug)
    except ValueError as e:
        print(f"[advisor] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
