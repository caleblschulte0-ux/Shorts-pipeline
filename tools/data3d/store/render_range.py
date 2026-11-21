"""Render GLOBAL frames A..B of a multi-shot short: each shot that overlaps the range renders its own part.
    usage: python render_range.py A B OUTDIR SPP PCT      env: STORY, NARR (required on CI), VBPY (the bpy python)
The shot boundaries come from clock.span, exactly as shots.py computes them (from the narration windows).
env RESHOOT="3 4": render only those shots (a fix to two shots re-renders two shots; the rest of the frames are
reused from an earlier run's shards, see data3d_render.yml reuse_run)."""
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(here))
import clock
A, B, OUT, SPP, PCT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
story = os.environ.get("STORY", "checkout")
W = (json.load(open(os.environ["NARR"])) if os.environ.get("NARR") else
     json.load(open(os.path.join(os.path.dirname(here), "stories", story, "script.json"))))["windows" if os.environ.get("NARR") else "draft_windows"]
py = os.environ.get("VBPY", sys.executable)
only = {int(x) for x in os.environ.get("RESHOOT", "").split()}
for shot in range(1, len(W) + 1):
    if only and shot not in only: continue
    T0, T1, G0, NF = clock.span(W, shot)
    a, b = max(A, G0 + 1) - G0, min(B, G0 + NF) - G0
    if a > b: continue
    print(f"shot {shot}: local {a}-{b} (global {G0 + a}-{G0 + b})", flush=True)
    env = dict(os.environ, SHOT=str(shot), FRAMES=f"{a}-{b}")
    subprocess.run([py, "-I", os.path.join(here, "shots.py"), OUT, SPP, PCT], env=env, check=True)
print("TOTAL", clock.total(W))
