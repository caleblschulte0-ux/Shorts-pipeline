"""THE PROOF LOOP: render a proof of every shot, let the judge panel watch it, have a brain fix what the judge named,
and go again, until every shot passes. Only then is a full render worth its hours.

caaleb, 2026-11-12, after a full render was spent on a take the judge had already failed:
  "we just need to make sure we are not wasting a bunch of time on somthing the judge will reject"
  "make sure it don't stop because the judge don't like it go back to the drawing board fix it up and try again
   until it passes"
  "remember we are building an autonomous system here at the end of the day that needs to make 100s of these"

So the loop belongs to the pipeline, not to a session. Each round:
  1. PROOF   every shot still failing is rendered small (shots.py with STAGING=on: the measured staging, consequence,
             anatomy and clipping checks run on it too), several at once.
  2. JUDGE   judge3d.py's panel watches the proofs of those shots (the same bar the render workflow gates on).
  3. REVISE  for every shot that failed, a headless Claude gets the shot's own function, the judge's notes, the
             measured checks and the proof sheet, and edits ONLY that shot in stories/<story>/shots.py.
             (--no-revise stops after the judge, for a session that makes the fixes itself.)
A shot that passes is never re-rendered or re-judged.
A shot that STALLS (its best score has not risen for STALL revisions) is not polished again: the next revision is a
RETHINK, told which element the judge has named round after round, and it cuts that element or simplifies the beat
to one idea that still says the storyboard line. The banana hook spent ~8 hours and 20+ hand rounds polishing a floor
stain the judge called a "spill" every time; it passed the moment the stain was cut (caaleb, 2026-11-13: "we can't
take 4 days to make one video"). And THE 180 RULE (caaleb, 2026-11-14, of saffron shot 4: "90 degrees didn't work 3
times, try 180"): a shot that has scored under the bar FLIP (3) rounds running on one idea gets NEW_IDEA instead: carry
the narration line with a different idea (different props, a different action), every camera / timing / framing tweak
of the old one forbidden; the new idea is judged on its own (never undone back to the old one) and gets its own rounds.
Every decision goes into loop.json ("rethink") and the story's judge_rounds.md (store/rounds.py). And the file never ends on an unjudged edit: every shot is put back to its best
judged take before the loop exits. The loop stops when every shot passes (exit 0) or after
--rounds (exit 2, the last verdict and every round's notes in OUT/loop.json).

usage: python proof_loop.py STORY OUT [--shots 1 2 3] [--rounds 6] [--no-revise] [--step 6] [--spp 8] [--pct 30]
Runs wherever Blender's bpy and the `claude` CLI are: a session's container, or a runner.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORIES = HERE.parent / "stories"
CHECKS = re.compile(r"^(STAGING|CONSEQUENCE|ENDING|ANATOMY|CLIPPING|TWITCH shot \d+:|FACE|HANDS|BOARD|SHOT|Traceback|\w*Error)")
PASS = int(re.search(r"^PASS_SCORE = (\d+)", (HERE / "judge3d.py").read_text(), re.M).group(1))   # the judge's own bar, read, never restated


def render_proof(story, n, out, step, spp, pct, py):
    d = out / f"s{n}"
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    env = dict(os.environ, STORY=story, SHOT=str(n), STEP=str(step), STAGING="on", CLIPPING="report")
    p = subprocess.run([py, "-I", "shots.py", str(d), str(spp), str(pct)], cwd=HERE, env=env,
                       capture_output=True, text=True)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if CHECKS.match(l.strip())]
    (out / f"s{n}.checks.txt").write_text("\n".join(lines))
    return n, p.returncode == 0 and any(d.glob("f*.png")), lines


def judge(story, out, shots, rnd=None):
    env = dict(os.environ, STORY=story, SHOTS=" ".join(map(str, shots)), JUDGE3D_ROUND=str(rnd or ""), JUDGE3D_LABEL=f"proof loop {out.name}")
    p = subprocess.run([sys.executable, str(HERE / "judge3d.py"), str(out), str(out / "verdict.json")], env=env,
                       capture_output=True, text=True)
    print(p.stdout)
    if not (out / "verdict.json").exists():
        return None
    return {s["shot"]: s for s in json.loads((out / "verdict.json").read_text())["shots"]}


def _span(src, n):
    return re.search(rf"^def shot{n}\(\):.*?(?=^def |^# =+|\Z)", src, re.S | re.M)


def shot_source(src, n):
    m = _span(src, n)
    return m.group(0) if m else ""


def put_shot(path, n, body):
    src = path.read_text(); m = _span(src, n)
    path.write_text(src[:m.start()] + body.rstrip("\n") + "\n\n\n" + src[m.end():].lstrip("\n"))


REVISER = """You are the 3D director of a YouTube Short starring Data, a small teal cartoon scientist. Shot {n} of the
story "{story}" just FAILED the judge panel. Fix it by editing ONLY the file {work}, which
holds the function shot{n}() alone and is spliced back into {path} (Read that file for the helpers and the other
shots; never edit it). Any new constant goes INSIDE the function. Never touch Data's body or design (character.py) or
the judge.

What the shot is FOR (the storyboard line the judge grades against): {brief}

The judge's verdict (score {score}, pass needs >= {pass_score} and no hard defect):
{verdict}

The measured checks on the same proof (staging = face to lens, back turned, face hidden, head at the frame edge,
size in frame; consequence = the result of the action is on screen; anatomy; clipping):
{checks}

The proof's contact sheet (every few frames, left to right, top to bottom) is {sheet}: READ it first.

{history}
Fix the CAUSE the judge names, the way a film director would: stage for this one camera, make the action and its
result big and clear in frame, keep Data's face to the lens, give him acting (a pose, a reaction) rather than a
held stare: data.perform(name, t) acts a feeling with his WHOLE body (happy, surprised, alarmed, sad, worried,
determined, wry: ears, head, shoulders, arms, face, with wind-up and settle), and his mouth opens (grin, gasp, talk). Prefer moving the camera, Data's place, timing and props over new machinery. When an action keeps failing on his hands (a hand that "never touches", a push
of air, an object that "moves on its own"), stop polishing the contact: restage the beat as ONE big action that needs
no fine hand contact (the thing happens on its own while he reacts with his whole body, or he holds one object the
whole shot). The banana short's passing shots were exactly that; its failing ones were all fiddly hand work. This is Blender 5 (bpy 5.0):
an Action has no .fcurves (layered actions), so key with keyframe_insert and the helpers the file already uses. Edit
the copy you were given, never {path} itself: an edit there is lost. Keep every check above passing. Keep the function's return dict the same shape. Make the edit, then reply with one line saying what you
changed."""


STALL = int(os.environ.get("PROOF_STALL", "2"))

RETHINK = """
THIS SHOT HAS STALLED: its best score has not risen in {stalled} revisions ({scores}). Polishing it again will fail
again. Do NOT tweak the same element. The judge keeps naming these, round after round:
{recurring}
Either CUT the element those notes are about (delete it from the shot entirely) or rebuild the beat around ONE
simpler idea that still says the storyboard line. Fewer, bigger things. A shot with one clear object beats a shot
with a clever detail the judge misreads.
"""


FLIP = int(os.environ.get("PROOF_FLIP", "3"))

NEW_IDEA = """
THE 180 RULE (caaleb, 2026-11-14: "90 degrees didn't work 3 times, try 180"): this shot has failed the judge {k} rounds
running ({scores}, the bar is {pass_score}). The IDEA is what fails, not its execution, so this round throws the idea
away. Carry the narration line

    "{line}"

with a DIFFERENT IDEA: different props and a different action doing the work. The idea being thrown away: {idea}
The story's other beats already use these ideas; do not borrow one: {others}
FORBIDDEN this round, because they are tweaks of the old idea and it has had {k} rounds of them: moving, re-aiming or
re-timing the camera, reframing or a new lens, re-timing the same action, making the same props bigger, brighter or
closer, recolouring them, adding a light on them. A revision that keeps the old idea's props and action is a failed
revision. Build the new idea from what the file already has (the helpers, store/prop_kit.py, store/produce.py,
store/props.py), big and in front of Data, carried by a prop or an action, never by his face alone. Start your one-line
reply with "NEW IDEA:" and the idea in a few words.
"""


def needs_new_idea(scores, since=0, k=FLIP, pass_score=PASS):
    """THE 180 RULE: True when the last k rounds of this idea (rounds since the last 180) all scored under the bar"""
    s = scores[since:]
    return len(s) >= k and all((x or 0) < pass_score for x in s[-k:])


def stalled(scores, k=STALL):
    """True when the last k revisions did not beat the best score before them."""
    if len(scores) <= k:
        return False
    return max(scores[-k:]) <= max(scores[:-k])


def recurring(problem_lists, min_rounds=2, top=6):
    """The judge's notes about the same thing in several rounds: content words that show up in >= min_rounds verdicts,
    each with one note that uses it."""
    stop = set("the a an of to and in on is it its his he with for at as by but not no this that from be are was "
               "into out up so or than then very too only one shot data frame scene reads read look looks".split())
    seen, example = {}, {}
    for probs in problem_lists:
        words = set()
        for note in probs or []:
            for w in re.findall(r"[a-z]{4,}", str(note).lower()):
                if w not in stop:
                    words.add(w); example.setdefault(w, str(note))
        for w in words:
            seen[w] = seen.get(w, 0) + 1
    hits = sorted((w for w, c in seen.items() if c >= min_rounds), key=lambda w: (-seen[w], w))[:top]
    return [(w, seen[w], example[w]) for w in hits]


def rethink_kind(scores, probs, since, line, idea, others):
    """(kind, prompt addition) for a failing shot: ("180", NEW_IDEA) after FLIP rounds under the bar on one idea, else
    ("stall", RETHINK) when its best has not risen for STALL revisions, else ("", "")"""
    s = scores[since:]
    if needs_new_idea(scores, since):                    # the 180 comes before any polish
        return "180", NEW_IDEA.format(k=FLIP, scores=", ".join(map(str, s)), pass_score=PASS, line=line, idea=idea,
                                      others="; ".join(others) or "(none listed)")
    if not stalled(s):
        return "", ""
    rec = recurring(probs[since:]) or [("(no single word)", 0, p) for p in (probs[-1] if probs else [])[:3]]
    return "stall", RETHINK.format(stalled=STALL, scores=", ".join(map(str, s)),
                                   recurring="\n".join(f"- {w!r} in {c} rounds, e.g. {ex}" for w, c, ex in rec))


def decision_note(rnd, n, kind, scores, answer):
    """the line the round report gets for what the loop decided about a shot"""
    what = (f"THE 180 RULE: {FLIP} rounds under {PASS} on one idea ({', '.join(map(str, scores))}); the reviser was told to "
            f"carry the line with a DIFFERENT IDEA, no camera, timing or framing tweaks of the old one" if kind == "180" else
            f"STALLED ({', '.join(map(str, scores))}): the reviser was told to cut the element the judge keeps naming")
    tail = f". It answered: {answer.strip().splitlines()[-1][:200]}" if answer and answer.strip() else ". The revision changed nothing."
    return f"round {rnd}, shot {n}: {what}{tail}"


def revise(story, out, n, v, history, rethink=""):
    path = STORIES / story / "shots.py"
    work = out / "rev" / f"shot{n}.py"; work.parent.mkdir(exist_ok=True)
    work.write_text(shot_source(path.read_text(), n))
    script = json.loads((STORIES / story / "script.json").read_text())
    brief = re.sub(r"^\d+\s*", "", script["storyboard"][n - 1])
    verdict = json.dumps({k: v.get(k) for k in ("score", "scores", "hard", "problems", "better")}, indent=1)
    checks = (out / f"s{n}.checks.txt").read_text() if (out / f"s{n}.checks.txt").exists() else "(none)"
    prompt = REVISER.format(n=n, story=story, path=path, brief=brief, score=v.get("score"), verdict=verdict, pass_score=PASS,
                            checks=checks, sheet=out / f"sheet_s{n}.jpg", work=work,
                            history=("Earlier attempts at this shot, and what the judge gave them (the best one is "
                                     "what you are editing now; do not repeat what scored lower):\n" + "\n".join(history) + "\n")
                            if history else "") + rethink
    before = work.read_text()
    p = subprocess.run(["claude", "-p", prompt, "--model", os.environ.get("REVISER_MODEL", "opus"),
                        "--allowedTools", "Read,Edit", "--output-format", "text"],
                       capture_output=True, text=True, timeout=int(os.environ.get("REVISER_TIMEOUT", "1200")))
    after = work.read_text()
    changed = after != before and after.lstrip().startswith(f"def shot{n}(")
    note = (p.stdout or p.stderr).strip()[-400:]
    print(f"REVISE shot {n}: {'changed' if changed else 'NO CHANGE'}: {note}", flush=True)
    return (after if changed else None), note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story"); ap.add_argument("out")
    ap.add_argument("--shots", type=int, nargs="*")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--no-revise", action="store_true")
    ap.add_argument("--step", type=int, default=6); ap.add_argument("--spp", type=int, default=8)
    ap.add_argument("--pct", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--python", default=os.environ.get("BPY_PYTHON", sys.executable))
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    n_shots = len(json.loads((STORIES / a.story / "script.json").read_text())["storyboard"])
    todo = a.shots or list(range(1, n_shots + 1))
    log, passed = [], {}
    path = STORIES / a.story / "shots.py"
    scores, probs = {n: [] for n in todo}, {n: [] for n in todo}
    best, history, pending = {}, {n: [] for n in todo}, {}       # best[n] = (score, source, verdict); pending[n] = what was tried
    base, since, fresh = {}, {n: 0 for n in todo}, set()        # base[n]: the best take of the CURRENT idea (a 180 starts a new one)
    import rounds
    for rnd in range(1, a.rounds + 1):
        t0 = time.time()
        print(f"=== round {rnd}: proof of shots {todo}", flush=True)
        with ThreadPoolExecutor(a.jobs) as ex:
            res = list(ex.map(lambda n: render_proof(a.story, n, out, a.step, a.spp, a.pct, a.python), todo))
        broken = [n for n, ok, _ in res if not ok]
        for n, ok, lines in res:
            print("\n".join(lines))
        ok_shots = [n for n in todo if n not in broken]
        verdict = judge(a.story, out, ok_shots, rnd) if ok_shots else {}
        if verdict is None:
            print("PROOF LOOP: no judge answered: stopping (fail closed)"); return 1
        for n in broken:
            verdict[n] = {"shot": n, "score": 0, "pass": False, "hard": ["the proof did not render: see s%d.checks.txt" % n]}
        log.append({"round": rnd, "secs": round(time.time() - t0), "verdict": verdict})
        (out / "loop.json").write_text(json.dumps(log, indent=1, default=str))
        for n in todo:
            sc = verdict[n].get("score") or 0; src = shot_source(path.read_text(), n)
            if n in pending: history[n].append(f"- {pending.pop(n)} -> scored {sc}")
            scores[n].append(sc); probs[n].append(list(verdict[n].get("problems") or []) + list(verdict[n].get("hard") or []))
            if verdict[n].get("pass"):
                passed[n] = verdict[n]
                if not verdict[n].get("kept"):
                    import judged; judged.record(a.story, n, verdict[n])   # the pass is kept while this code is unchanged
            if n not in best or sc > best[n][0]:
                best[n] = (sc, src, verdict[n])
            if n not in base or sc > base[n][0] or n in fresh:   # a NEW IDEA is judged on its own: never undone back to the old one
                base[n] = (sc, src, verdict[n]); fresh.discard(n)
            else:                                  # a revision that scored no better is undone: the loop never walks backwards
                put_shot(path, n, base[n][1]); verdict[n] = base[n][2]
                if history[n]: history[n][-1] += f" (no better than the best, {base[n][0]}: undone)"
        todo = [n for n in todo if not verdict[n].get("pass")]
        print(f"=== round {rnd}: passed {sorted(passed)}  failing {todo}", flush=True)
        if not todo:
            print("PROOF LOOP: every shot passes: the full render is worth starting"); return 0
        if a.no_revise or rnd == a.rounds:          # never end on an edit nobody judged
            break

        script = json.loads((STORIES / a.story / "script.json").read_text())
        decided = {}

        def rethink_for(n):
            ideas = script.get("ideas") or []
            kind, text = rethink_kind(scores[n], probs[n], since[n], script["lines"][n - 1],
                                      ideas[n - 1] if len(ideas) >= n else "the storyboard line's current staging",
                                      [i for j, i in enumerate(ideas) if j != n - 1])
            if kind:
                decided[n] = kind
                print(f"RETHINK shot {n}: {kind} over {scores[n][since[n]:]}", flush=True)
            return text

        with ThreadPoolExecutor(len(todo)) as ex:       # each brain edits its own copy of its own shot, in parallel
            outs = list(ex.map(lambda n: (n, revise(a.story, out, n, verdict[n], history[n], rethink_for(n))), todo))
        for n, (body, note) in outs:
            kind = decided.get(n)
            if body:
                put_shot(path, n, body); pending[n] = ("[180: NEW IDEA] " if kind == "180" else "") + note.replace("\n", " ")[:300]
                if kind == "180":
                    since[n] = len(scores[n]); fresh.add(n)     # the new idea gets its own rounds, and its own best
            if kind:                                   # the round report says what the loop decided, and why
                log[-1].setdefault("rethink", {})[n] = {"kind": kind, "scores": list(scores[n]), "applied": bool(body), "note": note[:300]}
                rounds.note(a.story, decision_note(rnd, n, kind, scores[n], note if body else None))
        (out / "loop.json").write_text(json.dumps(log, indent=1, default=str))
    for n in todo:                                   # the file holds each failing shot's best JUDGED take
        if n in best:
            put_shot(path, n, best[n][1])
    print(f"PROOF LOOP: still failing after {rnd} rounds: {todo}"); return 2


if __name__ == "__main__":
    sys.exit(main())
