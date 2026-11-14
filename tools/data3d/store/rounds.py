"""THE ROUND REPORT: every judge3d run writes what it judged, shot by shot, into the story's own folder
(stories/<story>/judge_rounds.md), so the operator can open one file and see what failed each round and why, without
digging a verdict.json out of a CI artifact (2026-11-14). It is APPEND-only: one section per run, newest at the bottom.

  append(story, shots, ...)   judge3d.py, after every panel (proof, storyboard or kept passes)
  note(story, text)           proof_loop.py, for what the loop decided after a round (a rethink, a 180)
A copy of the whole file can be written beside the verdict (the CI artifact) with copy_to."""
import shutil, time
from pathlib import Path

STORIES = Path(__file__).resolve().parents[1] / "stories"
NAME = "judge_rounds.md"


def path(story):
    return STORIES / story / NAME


def _head(story):
    return (f"# Judge rounds: {story}\n\nEvery run of the 3D judge on this story, appended by tools/data3d/store/judge3d.py "
            f"(and the proof loop's decisions). Newest at the bottom. Pass = no hard defect and the panel's median score "
            f"at the bar.\n")


def _write(story, text, copy_to=None):
    p = path(story)
    if not p.parent.is_dir():
        return None
    new = not p.exists()
    with open(p, "a") as fh:
        if new: fh.write(_head(story))
        fh.write(text)
    if copy_to:
        try: shutil.copyfile(p, copy_to)
        except OSError: pass
    return p


def render(shots, mode="proof", round_no=None, label=None, when=None, pass_score=None):
    """the markdown for one judge run: a summary table, then each shot's named problems"""
    when = when or time.strftime("%Y-%m-%d %H:%MZ", time.gmtime())
    title = f"## {when} · {mode}" + (f" · round {round_no}" if round_no else "") + (f" · {label}" if label else "")
    out = [title, "", "| shot | score | panel | result |", "|---|---|---|---|"]
    for s in sorted(shots, key=lambda x: x.get("shot", 0)):
        res = "PASS (kept)" if s.get("kept") else ("PASS" if s.get("pass") else "FAIL")
        panel = ", ".join(map(str, s.get("scores") or [])) or "-"
        out.append(f"| {s.get('shot')} | {s.get('score')} | {panel} | {res} |")
    out.append("")
    for s in sorted(shots, key=lambda x: x.get("shot", 0)):
        if s.get("kept"):
            continue
        lines = [f"- HARD: {h}" for h in s.get("hard") or []]
        lines += [f"- hard (one judge only): {h}" for h in s.get("minority_hard") or []]
        lines += [f"- problem: {p}" for p in s.get("problems") or []]
        if not s.get("pass"):
            lines += [f"- better: {b}" for b in (s.get("better") or [])[:3]]
        if lines:
            out += [f"**shot {s.get('shot')}** ({'PASS' if s.get('pass') else 'FAIL'}, {s.get('score')}" +
                    (f", bar {pass_score}" if pass_score else "") + ")", ""] + lines + [""]
    return "\n".join(out) + "\n"


def append(story, shots, mode="proof", round_no=None, label=None, copy_to=None, pass_score=None):
    if not story:
        return None
    return _write(story, "\n" + render(shots, mode, round_no, label, pass_score=pass_score), copy_to)


def note(story, text):
    """a line the proof loop adds under the last round (its decision about a shot)"""
    if not story:
        return None
    return _write(story, f"> {text}\n")
