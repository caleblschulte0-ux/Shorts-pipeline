"""Render GLOBAL frames A..B of the multi-shot short: each shot that overlaps the range renders its own part.
    usage: python render_range.py A B OUTDIR SPP PCT      env: NARR (required on CI), VBPY (the bpy python)
The shot boundaries are computed exactly as shots.py computes them (from the narration windows)."""
import json, os, subprocess, sys
A, B, OUT, SPP, PCT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
W = json.load(open(os.environ["NARR"]))["windows"] if os.environ.get("NARR") else [[0, 4.2], [4.2, 9.2], [9.2, 14.7], [14.7, 19.7], [19.7, 25.2]]
FPS = 24; here = os.path.dirname(os.path.abspath(__file__)); py = os.environ.get("VBPY", sys.executable)
for shot in range(1, 6):
    T0 = 0.0 if shot == 1 else W[shot - 1][0]; T1 = W[shot][0] if shot < 5 else W[4][1] + 0.6
    G0 = int(round(T0 * FPS)); NF = int(round(T1 * FPS)) - G0 + (1 if shot == 5 else 0)
    a, b = max(A, G0 + 1) - G0, min(B, G0 + NF) - G0
    if a > b: continue
    print(f"shot {shot}: local {a}-{b} (global {G0 + a}-{G0 + b})", flush=True)
    env = dict(os.environ, SHOT=str(shot), FRAMES=f"{a}-{b}")
    subprocess.run([py, "-I", os.path.join(here, "shots.py"), OUT, SPP, PCT], env=env, check=True)
print("TOTAL", int(round((W[4][1] + 0.6) * FPS)) + 1)
