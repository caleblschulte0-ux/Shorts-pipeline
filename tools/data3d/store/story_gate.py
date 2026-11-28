"""THE STORY GATE: a 3D short's SCRIPT is judged as a story before a single shot is built (2026-11-23).

caaleb, 2026-11-23: "Ok but why do our scripts suck". Because they were written backwards: a topic, four striking facts,
one line each. A list, not a story; nothing caused the next beat and nothing built to a twist. Lightning shipped with a
payoff (car safety) that did not pay off its title (the ranger struck seven times), and the first honey draft was three
beats of honey trivia under a fake-honey hook. Every check we had looked at the PICTURE; the script was only counted
(pacing caps, a closing question), so a list of trivia passed every gate and was found out after hours of shot work.

Two parts, both binding on every story not grandfathered below:
  links    script.json "links": one word per line after the hook, "so" (it happens because of the line before) or
           "but" (it turns against it). "and" / "and then" is a list, refused. The Twitch channel's stories learned this
           first (validate_edl refuses "and then"); a 3D short is a story too.
  verdict  stories/<story>/story_verdict.json, written by `python story_gate.py judge STORY`: a brain that has never
           seen the topic reads the title and the lines cold, must RETELL the story in one sentence, NAME the twist,
           say whether the ending pays off the title, and name any beat that could be cut without losing the story
           (trivia), and name any line that can't be shown as one big physical event in a real place (caaleb
           2026-11-23, after honey's tests and prices became props on tables: a topic that can't be a spectacle
           never reaches the builder). It is keyed on a hash of the title, lines and links, so changing a word needs a new verdict.
  showable every number and named thing in a spoken line can be seen or counted in ONE phone frame (2026-11-25).
           The lava short failed seven storyboard rounds on lines the gate had passed: "erupted nine times", "a hundred
           diggers and trucks", "only about a hundred people moved back". The board judge grades every shot against its
           spoken line (NOT SHOWN: "every number must be seen as a count or a size"), and no still can show nine
           eruptions or count a hundred of anything, so the shot was lost before it was staged. A floor in code
           (showable_problems: a count above COUNTABLE, "N times", a rate, a percentage, a crowd by magnitude) and a
           question to the cold readers: name, per line, the ONE picture that shows it, or the line fails.
problems(story, script) lists what fails; store/shots.py refuses to build a shot while it is not empty.
"""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

STORIES = Path(__file__).resolve().parents[1] / "stories"
NAME = "story_verdict.json"
PASS = 75
LINKS = {"so", "but"}
# made before the gate existed; never built again. Only shrinks.
GRANDFATHERED = {"checkout", "banana", "saffron", "helium", "cardrewards", "lightning"}

PROMPT = """You are a sharp YouTube Shorts story editor. You have never seen this topic. Read the TITLE and the LINES of a
narrated short (each line is about six seconds on screen, an animated character acts out each one) exactly as a viewer
scrolling past would hear them, and judge it as a STORY, not as a list of facts.

TITLE: {title}
LINES:
{lines}

Answer honestly:
- retell: the story in ONE sentence, as you would tell a friend. If all you can say is "a few facts about X", say that.
- twist: the moment a viewer did not see coming (empty string if there is none).
- payoff: does the last beat pay off what the TITLE and the first line promised? Say how, or why not.
- chain: does every line follow from the one before (it happens BECAUSE of it, or it turns AGAINST it)? Name any line
  that is just "and here is another fact".
- cut: every line (by number) that could be cut without the story losing anything (trivia, a tangent).
- physical: every line (by number) whose fact can NOT be shown as one big physical event in a real place, seen at a
  glance on a phone with the sound off (a storm strike, a dam bursting, seven jars with three going red). A line that
  can only be a number on a sign, a chart, a lab readout or a prop on a table goes here.
- pictures: for EVERY line, in order, the ONE picture that shows it: a single phone frame, sound off, in which every
  number in the line is seen as a count a viewer can count at a glance or as a size beside something familiar, and
  every named thing is recognisably that thing. Say what is in the frame. One entry per line.
- unshowable: every line (by number) no single frame can show that way: a count too big to count, something that
  happened "nine times", a rate, a share of a total nobody sees, a vague crowd, a fact only the voice can state.
- score: 0-100 as a story that makes a stranger watch to the end. pass: true only if score >= {bar}, there is a twist,
  the payoff matches the title, and nothing is in cut, physical or unshowable.
Return ONLY JSON: {{"retell": "...", "twist": "...", "payoff": "...", "chain": "...", "cut": [n, ...],
"physical": [n, ...], "pictures": ["line 1's picture", "..."], "unshowable": [n, ...], "score": n,
"pass": true|false, "problems": ["..."]}}"""


def held(story):
    return story not in GRANDFATHERED


def key(script):
    """the hash a verdict is valid for: the title, the lines and the links, nothing else"""
    s = json.dumps([script.get("title", ""), script.get("lines", []), script.get("links", [])], ensure_ascii=False)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def link_problems(script):
    lines = script.get("lines") or []
    links = script.get("links")
    if not isinstance(links, list) or len(links) != max(0, len(lines) - 1):
        return [f"links: give one link per line after the hook ({max(0, len(lines) - 1)}), each \"so\" or \"but\""]
    return [f"links[{i}] (line {i + 2}): {l!r} is a list, not a story: the line must happen BECAUSE of the one before "
            f"(\"so\") or turn AGAINST it (\"but\")" for i, l in enumerate(links) if str(l).strip().lower() not in LINKS]


# ---------------------------------------------------------------- SHOWABLE LINES (2026-11-25)
COUNTABLE = 10     # the most things a phone frame has shown as a count on this channel: the checkout short's row of ten lanes
_ONES = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                 "seventeen eighteen nineteen".split(), range(20)))
_TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
_MULT = {"hundred": 100, "thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9, "trillion": 10 ** 12}
_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?|[A-Za-z]+(?:'[a-z]+)?")
# a size is seen as a size (a wall three stories tall beside a house), never counted: a number in front of one of these
MEASURE = re.compile(r"\s*-?\s*(feet|foot|ft|inch(es)?|yards?|met(er|re)s?|kilomet(er|re)s?|miles?|stor(y|ies|eys?)|floors?|"
                     r"degrees?|tons?|tonnes?|pounds?|kilos?|kilograms?|gallons?|lit(er|re)s?|acres?)\b", re.I)
TIMES = re.compile(r"\s+(?:\w+\s+)?times\b", re.I)
RATE = re.compile(r"%|\bper\s?cent\b|\b(?:a|an|per|every|each)\s+(?:second|minute|hour|day|week|month|year)\b", re.I)
CROWD = re.compile(r"\b(dozens|scores|hundreds|thousands|millions|billions|trillions|countless|numerous|innumerable)\b", re.I)


def numbers(text):
    """every number in a line, said in digits or in words: [(value, the words, start, end)]. "a hundred" is 100,
    "half a million" 500000, "twenty-five" 25; a year in digits (1950, 2024) is a date, not a count, and is left out"""
    toks = [(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(text)]
    out, i = [], 0
    while i < len(toks):
        w = toks[i][0].lower(); j = i; val = None
        if w[0].isdigit():
            raw = w.replace(",", ""); val = float(raw) if "." in raw else int(raw); j = i + 1
            if "," not in w and "." not in w and 1000 <= val <= 2100:      # a year
                i += 1; continue
            if j < len(toks) and toks[j][0].lower() in _MULT and text[toks[j - 1][2]:toks[j][1]].strip() == "":
                val *= _MULT[toks[j][0].lower()]; j += 1
        else:
            lead = 1
            if w == "half" and i + 2 < len(toks) and toks[i + 1][0].lower() == "a" and toks[i + 2][0].lower() in _MULT:
                val = _MULT[toks[i + 2][0].lower()] // 2; j = i + 3
            elif w in ("a", "an") and i + 1 < len(toks) and toks[i + 1][0].lower() in _MULT:
                cur, total, j = 1, 0, i + 1
            elif w in _ONES or w in _TENS:
                cur, total = 0, 0
            else:
                i += 1; continue
            if val is None:
                seen = j > i
                while j < len(toks):
                    t = toks[j][0].lower()
                    if text[toks[j - 1][2]:toks[j][1]].strip(" -") != "" and j > i: break
                    if t in _ONES: cur += _ONES[t]
                    elif t in _TENS: cur += _TENS[t]
                    elif t == "hundred": cur = max(cur, 1) * 100
                    elif t in _MULT: total += max(cur, 1) * _MULT[t]; cur = 0
                    elif t == "and" and seen and j + 1 < len(toks) and (toks[j + 1][0].lower() in _ONES or toks[j + 1][0].lower() in _TENS): pass
                    else: break
                    seen = True; j += 1
                val = total + cur
        out.append((val, text[toks[i][1]:toks[j - 1][2]], toks[i][1], toks[j - 1][2]))
        i = j
    return out


def line_showable_problems(line):
    """what in ONE spoken line no single phone frame can show, as short sentences ([] when a frame can show it all)"""
    out = []
    for val, said, a, b in numbers(line):
        rest = line[b:]
        if TIMES.match(rest):
            if val > 2:
                out.append(f"'{said}{TIMES.match(rest).group(0)}': a still shows one moment, never something that happened or "
                           f"multiplied {said} times; say the one thing a viewer SEES (\"keeps erupting\", \"taller than a house\")")
        elif val > COUNTABLE and not MEASURE.match(rest):
            out.append(f"'{said}{re.match(r'(?: [A-Za-z-]+){0,2}', rest).group(0)}': {said} is more than a viewer can count "
                       f"in a phone frame (the limit is {COUNTABLE}); say it as one thing seen, or as a size beside something familiar")
    m = RATE.search(line)
    if m and (m.group(0) in "%" or "cent" in m.group(0).lower() or numbers(line)):
        out.append(f"'{m.group(0)}': a rate or a percentage is a number over time or of a total nobody sees; one frame cannot show it")
    for m in CROWD.finditer(line):
        out.append(f"'{m.group(0)}': a crowd by magnitude cannot be counted or recognised in a frame; say what one frame shows")
    return out


def showable_problems(script):
    """the SHOWABLE floor over every spoken line: ["line N: SHOWABLE: ..."]"""
    return [f"line {i}: SHOWABLE: {p}" for i, l in enumerate(script.get("lines") or [], 1) for p in line_showable_problems(str(l))]


def verdict(story):
    try:
        return json.loads((STORIES / story / NAME).read_text())
    except (OSError, ValueError):
        return None


def problems(story, script):
    if not held(story):
        return []
    out = link_problems(script) + showable_problems(script)
    v = verdict(story)
    if not v:
        out.append(f"no story verdict: run python tools/data3d/store/story_gate.py judge {story}")
    elif v.get("key") != key(script):
        out.append(f"the story verdict is for an older script: run python tools/data3d/store/story_gate.py judge {story}")
    elif not v.get("pass"):
        out.append(f"the story judge failed it ({v.get('score')}): {'; '.join(v.get('problems') or [])[:400]} "
                   f"cut: {v.get('cut')} not physical: {v.get('physical')} unshowable: {v.get('unshowable')} "
                   f"payoff: {str(v.get('payoff'))[:200]}")
    return out


def parse(text, lines=None):
    """a cold reader's answer, with the pass decided by code. `lines` is how many spoken lines it was asked about: when
    given, it must have named a picture for every one (a verdict written before 2026-11-25 has none; it stands for the
    script it is keyed to, and the next change to a word asks the question)"""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except ValueError:
        return None
    v["pass"] = bool(v.get("pass")) and int(v.get("score") or 0) >= PASS and bool(str(v.get("twist") or "").strip()) \
        and not v.get("cut") and not v.get("physical") and not v.get("unshowable")
    if lines is not None:
        pics = v.get("pictures") if isinstance(v.get("pictures"), list) else []
        named = [bool(str(p or "").strip()) for p in pics[:lines]] + [False] * max(0, lines - len(pics))
        if not all(named):
            v["pass"] = False
            v["problems"] = list(v.get("problems") or []) + [f"no picture named for line {i + 1}: a line with no one frame "
                                                              f"that shows it fails" for i, ok in enumerate(named) if not ok]
    return v


def judge(story, runs=3):
    """a panel of cold readers; the story passes only if a majority pass it, and the verdict kept is the median one"""
    script = json.loads((STORIES / story / "script.json").read_text())
    lines = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(script["lines"]))
    prompt = PROMPT.format(title=script.get("title", ""), lines=lines, bar=PASS)
    cmd = ["claude", "-p", prompt, "--model", os.environ.get("STORY_GATE_MODEL", "opus"), "--output-format", "text"]
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(runs)]
    vs = [v for v in (parse(p.communicate(timeout=600)[0], lines=len(script["lines"])) for p in procs) if v]
    if not vs:
        raise SystemExit("STORY GATE: no judge answered: nothing written, the gate stays shut")
    vs.sort(key=lambda v: int(v.get("score") or 0))
    v = dict(vs[len(vs) // 2])
    v["pass"] = sum(1 for x in vs if x["pass"]) * 2 > len(vs)
    v["scores"] = [int(x.get("score") or 0) for x in vs]
    v["key"] = key(script)
    (STORIES / story / NAME).write_text(json.dumps(v, indent=1, ensure_ascii=False) + "\n")
    return v


def main(argv):
    if len(argv) == 3 and argv[1] == "judge":
        v = judge(argv[2])
        print(f"STORY GATE {argv[2]}: {'PASS' if v['pass'] else 'FAIL'} {v['scores']}\n  retell: {v.get('retell')}\n"
              f"  twist: {v.get('twist')}\n  payoff: {v.get('payoff')}\n  cut: {v.get('cut')}  physical: {v.get('physical')}  unshowable: {v.get('unshowable')}\n  problems: {v.get('problems')}")
        return 0 if v["pass"] else 1
    if len(argv) == 3 and argv[1] == "check":
        script = json.loads((STORIES / argv[2] / "script.json").read_text())
        ps = problems(argv[2], script)
        print("\n".join(ps) or "STORY GATE: ok"); return 1 if ps else 0
    print("usage: story_gate.py judge STORY | check STORY"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
