"""THE BOARD ROUND IN CI: every shot's storyboard stills and its panel on its own runner, at the same time.

A board round in a session (store/board3d.sh) renders a few key stills of a shot and puts them before the panel, about
25 minutes a shot on four cores, one shot after another: two hours for five shots. Shots do not depend on each other,
so .github/workflows/data3d_board.yml gives each its own job (the same shots.py call, the same judge3d.py call, SHOTS=n)
and a five-shot round costs the wall-clock of its slowest shot.

Each job judged in its own checkout, so its round report, ledger and pre-flight record are in that runner and nowhere
else. This module puts them where a session's round puts them, ONCE, on the branch as it is now (never on the commit
the round started from, so a session that pushed meanwhile loses nothing):

  stories/<story>/judge_rounds.md     one section for the round, every shot in it (store/rounds.py)
  stories/<story>/notes_ledger.json   one round: every shot a panel graded (store/notes_ledger.py record)
  stories/<story>/preflight.json      each job's sheet records (store/preflight3d.py)

Nothing is graded here. A verdict is copied as judge3d.py wrote it; code only ever ADDS a block, as the proof loop's
storyboard gate does: a shot whose stills did not render fails with its measured check, two shots of the round framed
alike fail on VARIETY (store/variety.py), a third talking head on TALKING HEAD (store/fresh.py). A shot whose judge
gave no verdict is reported as that and is never a pass.

    python board_ci.py apply STORY ARTIFACTS LABEL [--dry]
ARTIFACTS holds one folder per shot (board-<n>/: status.json, verdict.json, preflight.json, checks.log, judge.log,
s<n>/framing.json). Prints the round as markdown; --dry writes nothing into the story folder."""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
STORIES = HERE.parent / "stories"
PASS = int(re.search(r"^PASS_SCORE = (\d+)", (HERE / "judge3d.py").read_text(), re.M).group(1))   # the judge's own bar, read, never restated
RECORDS = ("judge_rounds.md", "notes_ledger.json", "preflight.json")      # the only files a board round may commit


def _json(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


def gather(art):
    """(shots, graded, framing, sheets): the round's verdicts as each job left them. graded: the ones a panel answered
    (what judge3d.py hands the ledger); framing {shot: framing.json}; sheets: every job's pre-flight records"""
    shots, graded, framing, sheets = [], [], {}, {}
    for d in sorted(Path(art).glob("board-*")):
        st = _json(d / "status.json")
        if not st:                                            # a job that was cancelled left nothing: not in the round
            continue
        n = int(st["shot"])
        sheets.update((_json(d / "preflight.json") or {}).get("sheets") or {})
        fr = _json(d / f"s{n}" / "framing.json")
        if fr: framing[n] = fr
        if not st.get("stills"):
            log = (d / "checks.log").read_text(errors="replace").splitlines() if (d / "checks.log").exists() else []
            said = [l.strip() for l in log if l.strip() and not l.startswith(("TWITCH shot", "  "))]
            bad = [l for l in said if re.search(r"FAIL|fails", l)] or said[-3:] or ["the stills did not render"]   # a refusal with no FAIL word (VARIETY) is the log's last lines
            shots.append({"shot": n, "score": 0, "pass": False, "board": True,
                          "hard": ["a measured pre-check failed: " + b for b in bad[:4]]})
            continue
        v = _json(d / "verdict.json")
        mine = [s for s in (v or {}).get("shots", []) if s.get("shot") == n]
        if not mine:
            log = (d / "judge.log").read_text(errors="replace").splitlines() if (d / "judge.log").exists() else []
            said = [l.strip() for l in log if l.strip() and "round report appended" not in l][-4:] or ["the judge did not run"]
            shots.append({"shot": n, "score": None, "pass": False, "board": True, "hard": ["no verdict: " + " / ".join(said)[:400]]})
            continue
        s = dict(mine[0], board=True)
        shots.append(s)
        if (v.get("panel") or 0) > 0:
            graded.append(s)
    return shots, graded, framing, sheets


def add_blocks(story, shots, framing):
    """the checks that look ACROSS the shots of the round (the proof loop's storyboard gate runs the same two): each
    only ever fails a shot, with the reason as a hard line"""
    import variety, fresh
    by = {s["shot"]: s for s in shots}
    fr = {n: f for n, f in framing.items() if n in by}
    found = ([("VARIETY", n, why) for n, why in variety.framing_problems(fr)] if variety.held(story) else []) + \
            ([("TALKING HEAD", n, why) for n, why in fresh.talking_heads(fr)] if fresh.held(story) else [])
    for tag, n, why in found:
        s = by[n]; s["pass"] = False
        s["hard"] = list(s.get("hard") or []) + [f"{tag}: {why}"]
    return shots


def markdown(story, shots, label):
    out = [f"### Board round: {story} ({label})", "", "| shot | score | panel | result |", "|---|---|---|---|"]
    for s in sorted(shots, key=lambda x: x["shot"]):
        out.append(f"| {s['shot']} | {s.get('score')} | {', '.join(map(str, s.get('scores') or [])) or '-'} | {'PASS' if s.get('pass') else 'FAIL'} |")
    for s in sorted(shots, key=lambda x: x["shot"]):
        notes = [f"- HARD: {h}" for h in s.get("hard") or []] + [f"- problem: {p}" for p in s.get("problems") or []]
        if notes: out += ["", f"**shot {s['shot']}**", ""] + notes
    return "\n".join(out) + "\n"


def apply(story, art, label, dry=False):
    shots, graded, framing, sheets = gather(art)
    if not shots:
        print(f"BOARD CI: no shot of {story} left a result: nothing to record"); return 1
    add_blocks(story, shots, framing)
    Path(art, "board_verdict.json").write_text(json.dumps({"story": story, "label": label, "shots": shots}, indent=2))
    Path(art, "summary.txt").write_text(", ".join(f"shot {s['shot']} {s.get('score')} {'PASS' if s.get('pass') else 'FAIL'}"
                                                  for s in sorted(shots, key=lambda x: x["shot"])) + "\n")
    print(markdown(story, shots, label))
    if dry:
        print("BOARD CI: dry: nothing written into the story folder"); return 0
    if not (STORIES / story).is_dir():
        print(f"BOARD CI: no story folder {story} on this branch any more: nothing to record"); return 1
    import rounds, notes_ledger, preflight3d
    rounds.append(story, shots, mode="storyboard", label=label, pass_score=PASS)
    if graded:
        notes_ledger.record(story, graded)
    if sheets:
        led = preflight3d.load(story); led["sheets"].update(sheets); preflight3d.save(story, led)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 5 or sys.argv[1] != "apply":
        print(__doc__); sys.exit(1)
    sys.exit(apply(sys.argv[2], sys.argv[3], sys.argv[4], dry="--dry" in sys.argv[5:]))
