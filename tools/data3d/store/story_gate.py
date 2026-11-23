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
           (trivia). It is keyed on a hash of the title, lines and links, so changing a word needs a new verdict.
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
- score: 0-100 as a story that makes a stranger watch to the end. pass: true only if score >= {bar}, there is a twist,
  the payoff matches the title, and nothing is in cut.
Return ONLY JSON: {{"retell": "...", "twist": "...", "payoff": "...", "chain": "...", "cut": [n, ...], "score": n,
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


def verdict(story):
    try:
        return json.loads((STORIES / story / NAME).read_text())
    except (OSError, ValueError):
        return None


def problems(story, script):
    if not held(story):
        return []
    out = link_problems(script)
    v = verdict(story)
    if not v:
        out.append(f"no story verdict: run python tools/data3d/store/story_gate.py judge {story}")
    elif v.get("key") != key(script):
        out.append(f"the story verdict is for an older script: run python tools/data3d/store/story_gate.py judge {story}")
    elif not v.get("pass"):
        out.append(f"the story judge failed it ({v.get('score')}): {'; '.join(v.get('problems') or [])[:400]} "
                   f"cut: {v.get('cut')} payoff: {str(v.get('payoff'))[:200]}")
    return out


def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except ValueError:
        return None
    v["pass"] = bool(v.get("pass")) and int(v.get("score") or 0) >= PASS and bool(str(v.get("twist") or "").strip()) \
        and not v.get("cut")
    return v


def judge(story, runs=3):
    """a panel of cold readers; the story passes only if a majority pass it, and the verdict kept is the median one"""
    script = json.loads((STORIES / story / "script.json").read_text())
    lines = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(script["lines"]))
    prompt = PROMPT.format(title=script.get("title", ""), lines=lines, bar=PASS)
    cmd = ["claude", "-p", prompt, "--model", os.environ.get("STORY_GATE_MODEL", "opus"), "--output-format", "text"]
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(runs)]
    vs = [v for v in (parse(p.communicate(timeout=600)[0]) for p in procs) if v]
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
              f"  twist: {v.get('twist')}\n  payoff: {v.get('payoff')}\n  cut: {v.get('cut')}\n  problems: {v.get('problems')}")
        return 0 if v["pass"] else 1
    if len(argv) == 3 and argv[1] == "check":
        script = json.loads((STORIES / argv[2] / "script.json").read_text())
        ps = problems(argv[2], script)
        print("\n".join(ps) or "STORY GATE: ok"); return 1 if ps else 0
    print("usage: story_gate.py judge STORY | check STORY"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
