#!/usr/bin/env python3
"""NO DULL BEATS — the pipeline may not ship a dull beat.

The judges (interest, cool) can already TELL when a beat is dull or dead. This
director does something about it automatically: render → judge → for every dull
beat, ESCALATE its treatment (land it on MOTION of its subject instead of a flat
card or a still) → re-render → re-judge, looping until no beat is dull (or we run
out of escalations, which is reported, never hidden).

"Dull" is judged on PIXELS, not intent:
  - appeal below DULL_APPEAL (a flat card nobody stops scrolling for), OR
  - the cool judge flagged it DULL / LOW_MOTION / STILL_WHEN_MOTION_EXISTS, OR
  - it sits inside an interest-judge boring stretch AND isn't a high-appeal beat.
The HOOK is exempt when its appeal is high — a designed slam is allowed to hold.

Escalation (per beat, one level per round):
  a flat/designed card or a still  ->  `_force_motion`: the planner re-emits the
  beat as a depict shot, so the motion-first gate puts a MOVING clip of the
  subject under the text (still fallback only if no clip clears the bar).

    python scripts/no_dull_beats.py <story.beats.json> <out.mp4> [--rounds 3]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DULL_APPEAL = 0.55        # below this a beat is dull on looks alone
SOFT_APPEAL = 0.68        # inside a boring stretch, below this counts as dull
DULL_FLAGS = {"DULL", "LOW_MOTION", "STILL_WHEN_MOTION_EXISTS"}
_STOP = {"the", "a", "an", "of", "and", "in", "on", "at", "from", "to", "with",
         "it", "its", "is", "are", "that", "this", "as", "by", "for", "into",
         "every", "you", "your", "they", "their", "— ", "even", "more", "own"}


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# the render logs subjects via repr(): single-quoted normally, but DOUBLE-quoted
# when the subject itself contains an apostrophe ("Earth's night ..."). Match both.
_WON_RE = re.compile(r"""MOTION WINS for (['"])(.+?)\1""")
_MISS_RE = re.compile(r"""no moving clip cleared the bar for (['"])(.+?)\1""")


def _motion_outcomes(render_stderr: str) -> tuple[set[str], set[str]]:
    """From a render's log, which escalation subjects actually GOT motion vs fell
    back. An escalation that missed must revert to the beat's ORIGINAL treatment
    (a designed card with real motion), never a dead still — that would be a
    downgrade, not a repair."""
    won = {m.group(2) for m in _WON_RE.finditer(render_stderr)}
    missed = {m.group(2) for m in _MISS_RE.finditer(render_stderr)}
    return won, missed


def _judge(render: Path, beatmap: Path, out: Path) -> tuple[dict, list[dict]]:
    out.mkdir(parents=True, exist_ok=True)
    _run([sys.executable, str(REPO / "scripts" / "interest_judge.py"),
          str(render), "--out", str(out / "interest")])
    _run([sys.executable, str(REPO / "scripts" / "cool_judge.py"), str(render),
          "--beatmap", str(beatmap), "--out", str(out / "cool")])
    interest = json.loads((out / "interest" / "interest.json").read_text())
    cool = json.loads((out / "cool" / "cool_prescreen.json").read_text())
    return interest, cool


def _in_boring(t: str, boring: list) -> bool:
    try:
        a, z = (float(x) for x in str(t).split("-"))
    except (ValueError, IndexError):
        return False
    return any(not (z < bs[0] or a > bs[1]) for bs in boring)


def dull_beats(interest: dict, cool: list[dict]) -> list[dict]:
    """Return the cool rows that are dull, each with a WHY."""
    boring = interest.get("boring_stretches", [])
    out = []
    for r in cool:
        job = str(r.get("job", "")).upper()
        appeal = r.get("appeal", 1.0)
        suspects = set(r.get("suspect", []))
        why = None
        if "HOOK" in job and appeal >= 0.72:
            continue                                  # a bright hook may hold
        if appeal < DULL_APPEAL:
            why = f"appeal {appeal} < {DULL_APPEAL}"
        elif suspects & DULL_FLAGS:
            why = "+".join(sorted(suspects & DULL_FLAGS))
        elif _in_boring(r.get("t", ""), boring) and appeal < SOFT_APPEAL:
            why = f"dead stretch, appeal {appeal}"
        if why:
            out.append({"beat": r["beat"], "job": job, "why": why})
    return out


def _subject(beat: dict) -> str:
    """A REAL subject to search motion for — declared by the author, never a
    keyword-salad guessed from prose (that just fetches off-topic junk). A beat
    with no declared subject cannot be auto-escalated to footage; the director
    reports it instead of shipping a bad clip."""
    for q in (beat.get("motion_query"), beat.get("subject"),
              (beat.get("image") or {}).get("query"),
              (beat.get("footage") or {}).get("query"),
              (beat.get("footage") or {}).get("intent")):
        if q and len(str(q).split()) >= 2:
            return str(q)
    return ""


def run(story_path: Path, out: Path, rounds: int = 3) -> int:
    story = json.loads(story_path.read_text())
    beats = story["beats"]
    work = out.parent / f"{out.stem}_ndb_work"
    escalated: set[int] = set()
    for rnd in range(1, rounds + 1):
        tmp_story = work / f"story_r{rnd}.json"
        work.mkdir(parents=True, exist_ok=True)
        tmp_story.write_text(json.dumps(story))
        print(f"\n=== NO-DULL-BEATS round {rnd} — render ===")
        proc = _run([sys.executable, "-m", "data_learning.pro_render",
                     str(tmp_story), str(out), "--work", str(work)],
                    capture_output=True, text=True)
        # REVERT-ON-MISS: any beat we escalated whose motion probe FELL BACK to a
        # still keeps a designed card that had motion — reverting is a repair, a
        # dead still is a downgrade. Restore its original treatment.
        _, missed = _motion_outcomes(proc.stderr or "")
        reverted = 0
        for i in list(escalated):
            if (i < len(beats) and beats[i].get("_force_motion")
                    and beats[i].get("subject", "") in missed):
                beats[i].pop("_force_motion", None)
                reverted += 1
                print(f"[ndb] revert beat {i}: no dynamic clip for "
                      f"{beats[i].get('subject')!r} — keeping its designed card")
        if reverted:                        # a revert changed the story: re-render
            continue
        beatmap = out.parent / f"{out.stem}_pkg" / "beatmap.json"
        interest, cool = _judge(out, beatmap, work / f"judge_r{rnd}")
        dull = dull_beats(interest, cool)
        print(f"[ndb] round {rnd}: dead={interest.get('dead_fraction')} "
              f"appeal={interest.get('mean_appeal')} — {len(dull)} dull beat(s)")
        for d in dull:
            print(f"      beat {d['beat']} {d['job']}: {d['why']}")
        if not dull:
            print(f"[ndb] CLEAN — no dull beats after {rnd} round(s).")
            return 0
        # escalate each dull beat we haven't already escalated
        progressed = False
        for d in dull:
            i = d["beat"]
            if i in escalated or i >= len(beats):
                continue
            subj = _subject(beats[i])
            if not subj:
                continue
            beats[i]["_force_motion"] = True
            beats[i]["subject"] = subj
            escalated.add(i)
            progressed = True
            print(f"[ndb] escalate beat {i} -> motion of {subj!r}")
        if not progressed:
            print(f"[ndb] STUCK — {len(dull)} dull beat(s) with no escalation "
                  "left (likely motion access-gated). Reported, not hidden.")
            return 2
    print(f"[ndb] reached round limit ({rounds}); some beats may remain dull.")
    return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("story", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args(argv)
    return run(a.story, a.out, a.rounds)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
