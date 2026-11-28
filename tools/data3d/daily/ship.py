"""THE DEADLINE: when a 3D short renders although a shot never passed the panel (2026-11-28).

The operator, 2026-11-25: "a shot should take 2-3 render+judge rounds max"; 2026-11-23: "You've been sitting all day
because you were waiting for me to say render it?"; 2026-11-28, after the lava short spent 90 hours without a video:
"fix whatever is broken and make this into a fully autonomous system that produces a new 3d video in a timely
manner like at the very least 1 a day."

What was broken is that the only way out of the judge loop was a pass. The panel's ceiling is 78, three of four passes
are 70 to 74, it re-rolls 7 points on the same sheet, and 22 strict checks were stacked in front of it, so one shot
could (and did) hold a finished video for days. A round cap existed only as a note to the session.

The rule here is code: a short is SHIPPED (rendered in full, assembled, put on preview-renders for the operator's
yes or no) when every shot has either passed the panel once or been judged CAP times, or when the story was born in
the daily pipeline (script.json "pipeline": "daily"), whose looks and fixes are bounded before this is ever called
(daily/README.md). A shipped render builds every shot with the measured checks REPORTING (STAGING=on): they print
what they find beside the video, and stop nothing. Nothing here posts: the showrunner still watches the finished
cut, and posting is data3d_upload.yml, as before.

    python ship.py check STORY     exit 0 and why it may ship; exit 1 and what it still owes
"""
import json, re, sys
from pathlib import Path

STORIES = Path(__file__).resolve().parents[1] / "stories"
CAP = 3          # judged rounds a shot gets before the best take ships (the operator's "2-3 rounds max")
ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*(PASS(?: \(kept\))?|FAIL)\s*\|\s*$")


def tally(text):
    """{shot: (rounds judged, passed once)} from a story's judge_rounds.md"""
    out = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        n = int(m.group(1)); rounds, passed = out.get(n, (0, False))
        out[n] = (rounds + 1, passed or m.group(4).startswith("PASS"))
    return out


def owed(story, script=None, rounds_text=None):
    """what the story still owes before it may ship: [] means ship it. Pure: tests call it with texts."""
    d = STORIES / story
    script = script if script is not None else json.loads((d / "script.json").read_text())
    if script.get("pipeline") == "daily":
        return []
    if rounds_text is None:
        p = d / "judge_rounds.md"; rounds_text = p.read_text() if p.exists() else ""
    t = tally(rounds_text); out = []
    for n in range(1, len(script["lines"]) + 1):
        rounds, passed = t.get(n, (0, False))
        if not passed and rounds < CAP:
            out.append(f"shot {n}: judged {rounds} time(s), never passed; it gets {CAP} rounds before the best take ships")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        sys.exit(__doc__)
    o = owed(sys.argv[2])
    for line in o:
        print("SHIP", sys.argv[2], line)
    if o:
        sys.exit(1)
    print(f"SHIP {sys.argv[2]}: every shot has passed or had its {CAP} rounds (or the story is the daily pipeline's): the best take ships")
