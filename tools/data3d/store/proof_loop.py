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
A shot that passes is never re-rendered or re-judged. The loop stops when every shot passes (exit 0) or after
--rounds (exit 2, the last verdict and every round's notes in OUT/loop.json).

usage: python proof_loop.py STORY OUT [--shots 1 2 3] [--rounds 6] [--no-revise] [--step 6] [--spp 8] [--pct 30]
Runs wherever Blender's bpy and the `claude` CLI are: a session's container, or a runner.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORIES = HERE.parent / "stories"
CHECKS = re.compile(r"^(STAGING|CONSEQUENCE|ENDING|ANATOMY|CLIPPING|SHOT|Traceback|\w*Error)")


def render_proof(story, n, out, step, spp, pct, py):
    d = out / f"s{n}"
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    env = dict(os.environ, STORY=story, SHOT=str(n), STEP=str(step), STAGING="on", CLIPPING="report")
    p = subprocess.run([py, "-I", "shots.py", str(d), str(spp), str(pct)], cwd=HERE, env=env,
                       capture_output=True, text=True)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if CHECKS.match(l.strip())]
    (out / f"s{n}.checks.txt").write_text("\n".join(lines))
    return n, p.returncode == 0 and any(d.glob("f*.png")), lines


def judge(story, out, shots):
    env = dict(os.environ, STORY=story, SHOTS=" ".join(map(str, shots)))
    p = subprocess.run([sys.executable, str(HERE / "judge3d.py"), str(out), str(out / "verdict.json")], env=env,
                       capture_output=True, text=True)
    print(p.stdout[-4000:])
    if not (out / "verdict.json").exists():
        return None
    return {s["shot"]: s for s in json.loads((out / "verdict.json").read_text())["shots"]}


def shot_source(src, n):
    m = re.search(rf"^def shot{n}\(\):.*?(?=^def |^# =+|\Z)", src, re.S | re.M)
    return m.group(0) if m else ""


REVISER = """You are the 3D director of a YouTube Short starring Data, a small teal cartoon scientist. Shot {n} of the
story "{story}" just FAILED the judge panel. Fix it by editing ONLY the function shot{n}() in {path}
(and, if the shot truly needs it, constants that ONLY shot{n} uses). Never touch another shot, Data's body or design
(character.py), or the judge.

What the shot is FOR (the storyboard line the judge grades against): {brief}

The judge's verdict (score {score}, pass needs >= 70 and no hard defect):
{verdict}

The measured checks on the same proof (staging = face to lens, back turned, face hidden, head at the frame edge,
size in frame; consequence = the result of the action is on screen; anatomy; clipping):
{checks}

The proof's contact sheet (every few frames, left to right, top to bottom) is {sheet}: READ it first.

Fix the CAUSE the judge names, the way a film director would: stage for this one camera, make the action and its
result big and clear in frame, keep Data's face to the lens, give him acting (a pose, a reaction) rather than a
held stare. Prefer moving the camera, Data's place, timing and props over new machinery. Keep every check above
passing. Keep the function's return dict the same shape. Make the edit, then reply with one line saying what you
changed."""


def revise(story, out, n, v):
    path = STORIES / story / "shots.py"
    script = json.loads((STORIES / story / "script.json").read_text())
    brief = re.sub(r"^\d+\s*", "", script["storyboard"][n - 1])
    verdict = json.dumps({k: v.get(k) for k in ("score", "scores", "hard", "problems", "better")}, indent=1)
    checks = (out / f"s{n}.checks.txt").read_text() if (out / f"s{n}.checks.txt").exists() else "(none)"
    prompt = REVISER.format(n=n, story=story, path=path, brief=brief, score=v.get("score"), verdict=verdict,
                            checks=checks, sheet=out / f"sheet_s{n}.jpg")
    before = shot_source(path.read_text(), n)
    p = subprocess.run(["claude", "-p", prompt, "--model", os.environ.get("REVISER_MODEL", "opus"),
                        "--allowedTools", "Read,Edit", "--output-format", "text"],
                       capture_output=True, text=True, timeout=int(os.environ.get("REVISER_TIMEOUT", "1200")))
    after = shot_source(path.read_text(), n)
    changed = after != before
    print(f"REVISE shot {n}: {'changed' if changed else 'NO CHANGE'}: {(p.stdout or p.stderr).strip()[-300:]}")
    return changed


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
    for rnd in range(1, a.rounds + 1):
        t0 = time.time()
        print(f"=== round {rnd}: proof of shots {todo}", flush=True)
        with ThreadPoolExecutor(a.jobs) as ex:
            res = list(ex.map(lambda n: render_proof(a.story, n, out, a.step, a.spp, a.pct, a.python), todo))
        broken = [n for n, ok, _ in res if not ok]
        for n, ok, lines in res:
            print("\n".join(lines))
        ok_shots = [n for n in todo if n not in broken]
        verdict = judge(a.story, out, ok_shots) if ok_shots else {}
        if verdict is None:
            print("PROOF LOOP: no judge answered: stopping (fail closed)"); return 1
        for n in broken:
            verdict[n] = {"shot": n, "score": 0, "pass": False, "hard": ["the proof did not render: see s%d.checks.txt" % n]}
        log.append({"round": rnd, "secs": round(time.time() - t0), "verdict": verdict})
        (out / "loop.json").write_text(json.dumps(log, indent=1, default=str))
        for n in todo:
            if verdict[n].get("pass"): passed[n] = verdict[n]
        todo = [n for n in todo if not verdict[n].get("pass")]
        print(f"=== round {rnd}: passed {sorted(passed)}  failing {todo}", flush=True)
        if not todo:
            print("PROOF LOOP: every shot passes: the full render is worth starting"); return 0
        if a.no_revise:
            return 2
        for n in todo:
            revise(a.story, out, n, verdict[n])
    print(f"PROOF LOOP: still failing after {a.rounds} rounds: {todo}"); return 2


if __name__ == "__main__":
    sys.exit(main())
