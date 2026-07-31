#!/usr/bin/env python3
"""VISUAL benchmark (review Phase 4.1): the perceptual half of the suite.
The structural report proves the code emitted what it intended; THIS report has
a vision judge look at the finished videos and answer what a viewer sees:

  contact_looks_real        hands/feet visibly ON the chart object, natural
  action_understandable     you can tell what Data is trying to do
  performance_matches_story the bit embodies the narration's claim
  hook_compelling           the open earns the next 3 seconds
  ending_lands              the last beat resolves with a payoff
  composition_works         frame is used well, no dead zones / collisions
  enjoyable                 you'd watch it, not endure it
  data_clear                the numbers stay legible and honest

Requires a vision backend (the showrunner's own judge). Without one it writes
status "not_run" — which keeps the merged benchmark's fully_passing FALSE, so
a structural-only pass can never masquerade as a full pass.

Usage: python scripts/benchmark_visual.py --slugs a b c
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_sr():
    spec = importlib.util.spec_from_file_location(
        "showrunner_review", REPO / "scripts" / "showrunner_review.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


CHECKS = ["contact_looks_real", "action_understandable",
          "performance_matches_story", "hook_compelling", "ending_lands",
          "composition_works", "enjoyable", "data_clear"]

_PROMPT = """You are the channel's strict VISUAL benchmark judge. Look at the \
labelled frames of this finished short and answer EVERY check with a boolean + \
one line of evidence naming a frame label. Be strict: metadata claims nothing \
here — only what a viewer can SEE counts.

Checks: contact_looks_real (mascot's hands/feet visibly ON the chart object, \
naturally attached, no floating/clipping), action_understandable, \
performance_matches_story, hook_compelling, ending_lands, composition_works, \
enjoyable, data_clear.

STORY CONTEXT: {ctx}

Return ONLY JSON:
{{"checks":{{"contact_looks_real":{{"pass":bool,"evidence":str}},
"action_understandable":{{"pass":bool,"evidence":str}},
"performance_matches_story":{{"pass":bool,"evidence":str}},
"hook_compelling":{{"pass":bool,"evidence":str}},
"ending_lands":{{"pass":bool,"evidence":str}},
"composition_works":{{"pass":bool,"evidence":str}},
"enjoyable":{{"pass":bool,"evidence":str}},
"data_clear":{{"pass":bool,"evidence":str}}}},"one_line":str}}"""


def judge_story(sr, slug: str) -> dict:
    mp4 = REPO / "output" / f"story_{slug}.mp4"
    if not mp4.exists():
        return {"slug": slug, "status": "missing_video", "pass": False}
    ctx = {}
    vp = REPO / "output" / f"story_{slug}.showrunner.json"
    if vp.exists():
        v = json.loads(vp.read_text())
        ctx = {"score": v.get("score"), "one_line": v.get("one_line")}
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        labeled = sr._extract_frames(mp4, tdp, None)
        if not labeled:
            return {"slug": slug, "status": "no_frames", "pass": False}
        try:
            grades, backend = sr._judge(
                _PROMPT.format(ctx=json.dumps(ctx)), labeled)
        except Exception as e:  # noqa: BLE001
            return {"slug": slug, "status": f"no_backend: {e}"[:120],
                    "pass": False, "not_run": True}
    checks = grades.get("checks", {}) or {}
    passed = all(bool((checks.get(c) or {}).get("pass")) for c in CHECKS)
    return {"slug": slug, "status": "ran", "judge": backend, "pass": passed,
            "checks": checks, "one_line": grades.get("one_line", "")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="+", required=True)
    args = ap.parse_args()
    sr = _load_sr()
    results = [judge_story(sr, s) for s in args.slugs]
    ran = [r for r in results if r.get("status") == "ran"]
    all_pass = bool(ran) and all(r["pass"] for r in results)
    status = "ran" if len(ran) == len(results) else "partial_or_not_run"
    out = REPO / "state" / "benchmark_visual.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"results": results, "all_pass": all_pass, "status": status},
        indent=1))
    for r in results:
        line = r.get("one_line", r.get("status"))
        print(f"[{r['slug']}] {'PASS' if r.get('pass') else 'FAIL'} "
              f"({r.get('status')}) {line}")
        for c, v in (r.get("checks") or {}).items():
            if not v.get("pass"):
                print(f"    FAIL {c} — {v.get('evidence', '')[:100]}")
    print(f"visual benchmark: {'ALL PASS' if all_pass else 'NOT PASSING'} "
          f"-> {out}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
