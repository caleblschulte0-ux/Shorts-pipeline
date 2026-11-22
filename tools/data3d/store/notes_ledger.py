"""THE NOTES LEDGER: a judge's note is not closed until a round has been run AGAINST it (2026-11-22).

The lightning opening got the same hard note, NOT THE WORLD ("no narrow crest, no drop, no hazy valley"), in round
after round for three days. The fix it asked for (a lens beside him that shows the drop) tripped one of our own checks,
so the session worked around the note instead: three new gag ideas, each scored against a storyboard rewritten to
match it, each bringing new defects, and the one note nobody fixed stayed under all of them. caaleb: "You should have
to get notes 2, maybe 3 times tops, and then the video should be perfect."

So every hard defect the panel names is kept here per story and per shot, keyed on its TAG (NOT THE WORLD, BROKEN,
TALKING HEAD ...), never on the shot's idea or wording, so rewriting the idea does not wipe it.

  record(story, shots)    judge3d.py after every panel: each failing shot's tags, one round
  repeated(story, shot)   a tag named in 2+ rounds for the shot that the shot has not since passed
  fix(story, shot, tag, what)   the session writes WHAT it changed against that note (python notes_ledger.py fix ...)
  gate(story, shots)      judge3d.py BEFORE a panel: a repeated note with no fix written since it was last named
                          blocks the run, so no judge run is spent on a round that did not touch it
  for_judge(story, shot)  the repeated notes and their claimed fixes, put in front of the judges, who must name the
                          tag again if it is still there; a claimed fix that did not work is a new round of the note

If one of our own checks blocks the fix a note asks for, the check gets fixed, not the note. Nothing here lowers a bar.
"""
import json, re, sys, time
from pathlib import Path

STORIES = Path(__file__).resolve().parents[1] / "stories"
NAME = "notes_ledger.json"
REPEAT = 2      # a tag named in this many rounds is a repeated note

# the hard-defect names judge3d.py's BAR defines; a hard line is tagged by the one it opens with
TAGS = ["BACK TO CAMERA", "NOT THE POINT", "NOT THE WORLD", "OFF THE LOOK", "ONE-SECOND GAG", "TALKING HEAD",
        "TINY DATA", "STOCK GAG", "NO PAYOFF", "CONSEQUENCE", "BROKEN", "BODY"]


def tag(line):
    """the hard defect a judge line names: the TAG it opens with (after an optional 'HARD:'), else None"""
    s = re.sub(r"^\s*(hard\s*(\(one judge only\))?\s*:\s*)", "", str(line), flags=re.I).lstrip("-* ").upper()
    for t in sorted(TAGS, key=len, reverse=True):
        if s.startswith(t) or s.startswith(t.replace("-", " ")):
            return t
    return None


def path(story):
    return STORIES / story / NAME


def load(story):
    try:
        return json.loads(path(story).read_text())
    except (OSError, ValueError):
        return {"rounds": 0, "shots": {}}


def save(story, led):
    p = path(story)
    if p.parent.is_dir():
        p.write_text(json.dumps(led, indent=1, sort_keys=True) + "\n")
    return p


def record(story, shots, when=None):
    """one panel's verdict into the ledger: a failing shot's tags each get this round; a passing shot is cleared"""
    if not story:
        return None
    led = load(story); led["rounds"] = led.get("rounds", 0) + 1; rnd = led["rounds"]
    when = when or time.strftime("%Y-%m-%d %H:%MZ", time.gmtime())
    for s in shots:
        if s.get("kept"):
            continue
        k = str(s.get("shot")); sh = led["shots"].setdefault(k, {})
        if s.get("pass"):
            for t in sh.values(): t["closed"] = rnd
            continue
        for line in list(s.get("hard") or []) + list(s.get("minority_hard") or []):
            t = tag(line)
            if not t:
                print(f"NOTES LEDGER: shot {k}: a hard line with no tag, not tracked: {str(line)[:80]}")
                continue
            e = sh.setdefault(t, {"named": [], "fixes": []})
            if not e["named"] or e["named"][-1]["round"] != rnd:
                e["named"].append({"round": rnd, "at": when, "said": str(line)[:400]})
            e.pop("closed", None)
    save(story, led)
    return led


def repeated(story, shot, led=None):
    """{tag: entry} for every note named in REPEAT or more rounds on this shot and not closed by a pass since"""
    led = led or load(story)
    sh = led.get("shots", {}).get(str(shot), {})
    out = {}
    for t, e in sh.items():
        if e.get("closed"):
            continue
        if len({n["round"] for n in e.get("named", [])}) >= REPEAT:
            out[t] = e
    return out


def unanswered(e):
    """a repeated note whose last naming came after its last written fix"""
    last_named = max(n["round"] for n in e["named"])
    last_fix = max((f["round"] for f in e.get("fixes", [])), default=-1)
    return last_fix < last_named


def fix(story, shot, t, what):
    """write what this round changed against a note; it holds until the panel names the note again"""
    t = tag(t) or t.upper()
    led = load(story); e = led.get("shots", {}).get(str(shot), {}).get(t)
    if not e:
        raise SystemExit(f"NOTES LEDGER: shot {shot} has no note {t!r} in {path(story)}")
    if len(what.strip()) < 20:
        raise SystemExit("NOTES LEDGER: say what changed against the note (20 characters or more), not 'fixed'")
    e.setdefault("fixes", []).append({"round": led.get("rounds", 0), "at": time.strftime("%Y-%m-%d %H:%MZ", time.gmtime()),
                                      "what": what.strip()})
    save(story, led)
    return e


def gate(story, shots):
    """the repeated notes on these shots with no fix written since they were last named: each one blocks the panel"""
    led = load(story); probs = []
    for n in shots:
        for t, e in repeated(story, n, led).items():
            if unanswered(e):
                rounds = sorted({x["round"] for x in e["named"]})
                probs.append(f"shot {n}: {t} named in rounds {rounds} and nothing written against it since round "
                             f"{rounds[-1]}. Fix what it says, then: python tools/data3d/store/notes_ledger.py fix "
                             f"{story} {n} \"{t}\" \"<what changed>\". Last said: {e['named'][-1]['said'][:200]}")
    return probs


def for_judge(story, shot):
    """the repeated notes on a shot with the session's claimed fix, for the judges to check by name"""
    rep = repeated(story, shot)
    if not rep:
        return ""
    lines = [f"  NOTES THIS SHOT HAS FAILED ON BEFORE (shot {shot}). Look for each first. If it is still there, name it "
             f"again as a HARD defect opening with the same tag, whatever else changed:"]
    for t, e in rep.items():
        fx = e.get("fixes") or [{"what": "(no fix written)"}]
        lines.append(f"  - {t}, named in {len({x['round'] for x in e['named']})} rounds; last said: "
                     f"{e['named'][-1]['said'][:240]} | what was changed against it: {fx[-1]['what'][:240]}")
    return "\n".join(lines)


def seed_from_rounds(story, rounds_md):
    """build a story's ledger from its judge_rounds.md history (rounds.py's format), oldest first"""
    text = Path(rounds_md).read_text()
    led = {"rounds": 0, "shots": {}}
    save(story, led)
    for sec in re.split(r"\n(?=## )", text)[1:]:
        when = sec.splitlines()[0][3:].split(" · ")[0]
        shots = []
        for m in re.finditer(r"\*\*shot (\d+)\*\* \((PASS|FAIL)[^)]*\)\n\n((?:- .*\n?)*)", sec):
            hard = [l[2:] for l in m.group(3).splitlines() if l.lower().startswith(("- hard", "- hard (one"))]
            shots.append({"shot": int(m.group(1)), "pass": m.group(2) == "PASS", "hard": hard})
        for row in re.finditer(r"^\| (\d+) \| [^|]* \| [^|]* \| PASS", sec, re.M):
            if not any(s["shot"] == int(row.group(1)) for s in shots):
                shots.append({"shot": int(row.group(1)), "pass": True, "hard": []})
        if shots:
            record(story, shots, when)
    return load(story)


def main(argv):
    if len(argv) >= 5 and argv[1] == "fix":
        fix(argv[2], argv[3], argv[4], " ".join(argv[5:])); print("NOTES LEDGER: fix written"); return 0
    if len(argv) >= 3 and argv[1] == "show":
        led = load(argv[2])
        for k in sorted(led.get("shots", {}), key=int):
            for t, e in repeated(argv[2], k, led).items():
                print(f"shot {k}: {t} x{len({x['round'] for x in e['named']})}"
                      f" {'UNANSWERED' if unanswered(e) else 'fix written: ' + e['fixes'][-1]['what'][:100]}")
        return 0
    if len(argv) == 4 and argv[1] == "seed":
        seed_from_rounds(argv[2], argv[3]); return main(["", "show", argv[2]])
    print("usage: notes_ledger.py show STORY | fix STORY SHOT TAG WHAT... | seed STORY judge_rounds.md"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
