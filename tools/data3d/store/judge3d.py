"""The 3D JUDGE: a headless Claude WATCHES the proof pass of every shot before the full render is allowed to start
(caaleb, 2026-11-12: "I can't come back to you for every prop we ever make and tell you that it's bad one time
before it's good ... these are the bare minimums. You should be taking this and going above and beyond").

The measured checks (staging.py, anatomy.py, staging.consequence) catch what a number can say. This catches what
only an eye can: a pose that is legal but reads wrong, an action whose result is there but has no emphasis, Data
pasted over a set instead of standing in it, a prop that looks like a toy. It gets each shot as a strip of its proof
frames plus what the shot is FOR, and grades it against the bar below. Any shot under the bar fails the proof, the
full render does not start, and its notes are written to proof_verdict.json for the session that fixes it.

usage: python judge3d.py PROOF_DIR OUT_JSON      PROOF_DIR/s1..s5/f*.png      exit 0 pass, 2 fail, 1 no judge
Judges with the `claude` CLI on CLAUDE_CODE_OAUTH_TOKEN (never the paid API); no judge = no pass (fail closed).
"""
import json, os, shutil, subprocess, sys
from pathlib import Path
from PIL import Image

BRIEFS = {
    1: "HOOK. A self-checkout machine spews money while Data reacts in shock. Must read in the first second.",
    2: "9 OUT OF 10. Data throws a master switch at the head of a row of ten checkout lanes; nine of them turn into "
       "self-checkout kiosks one after another, one staffed lane stays. The row and the 9-of-10 must be readable.",
    3: "HALF A MILLION JOBS IN TEN YEARS. Cashiers walk out through a staff door while Data tears years off a wall "
       "calendar; each torn page must visibly fall and pile on the floor.",
    4: "TWICE THE LOSSES. Data pours coins from a sack into two LOSSES jars; the coins must be seen falling in, and "
       "the self-checkout jar must end over twice as full.",
    5: "CLOSING. Every lane is self-checkout and blinking red; Data shrugs then waves as the camera pulls back.",
}

BAR = """You are the director of a 3D animated YouTube Short starring Data, a small teal cartoon scientist in a lab
coat and glasses. Grade each shot as a demanding animation director would. The bar is a professional studio short:
the operator will not accept anything they would have to point out themselves. Look for, and FAIL a shot on, any of:
- BODY: a limb bent the way no body bends, a twisted wrist, an arm through the body, a stiff mannequin pose, hands
  floating instead of gripping what they hold, feet sliding or sunk.
- EMPHASIS: an action whose RESULT is not shown clearly and big enough to read on a phone (things falling, pouring,
  breaking, flipping must be SEEN happen, landing somewhere); a key moment happening off-frame or behind something.
- STAGING: Data's back or the back of his head to the camera for more than a glance; Data out of place, pasted over
  the set, wrong scale, not touching the world; the point of the shot not readable at a glance; awkward framing,
  cropped subjects, big empty areas with nothing in them.
- CRAFT: anything that looks broken, glitchy, toy-like or cheap; text that is cut off or unreadable.
Then add what would make it BETTER, beyond the minimum, even when it passes.

Return ONLY JSON: {"shots": [{"shot": N, "score": 0-100, "pass": true|false, "problems": ["..."],
"better": ["..."]}]}. pass is false whenever any FAIL item above is visible, whatever the score."""


def strip(frames, out, h=540, cols=8):
    ims = [Image.open(p).convert("RGB") for p in frames]
    ims = [im.resize((int(im.width * h / im.height), h)) for im in ims]
    rows = (len(ims) + cols - 1) // cols; w = ims[0].width
    S = Image.new("RGB", (w * min(cols, len(ims)), h * rows), (20, 20, 20))
    for i, im in enumerate(ims): S.paste(im, ((i % cols) * w, (i // cols) * h))
    S.save(out, quality=88); return out


def main():
    proof, out = Path(sys.argv[1]), Path(sys.argv[2])
    if not shutil.which("claude"):
        print("JUDGE3D: no claude CLI: no judge, no pass"); return 1
    sheets = []
    for n in sorted(BRIEFS):
        fr = sorted((proof / f"s{n}").glob("f*.png"))
        if not fr: print(f"JUDGE3D: shot {n} has no proof frames"); return 1
        sheets.append((n, strip(fr, proof / f"sheet_s{n}.jpg"), len(fr)))
    listing = "\n".join(f"- shot {n}: {p} ({k} frames in time order, left to right, top to bottom). FOR: {BRIEFS[n]}"
                        for n, p, k in sheets)
    prompt = (BAR + "\n\nThe shots, each a contact sheet image you must READ with the Read tool:\n" + listing)
    proc = subprocess.run(["claude", "-p", prompt, "--model", os.environ.get("JUDGE3D_MODEL", "opus"),
                           "--allowedTools", "Read", "--output-format", "text"],
                          capture_output=True, text=True, timeout=int(os.environ.get("JUDGE3D_TIMEOUT", "900")))
    if proc.returncode != 0:
        print("JUDGE3D: judge failed:", (proc.stderr or proc.stdout)[:300]); return 1
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from showrunner_review import parse_judge_json
    v = parse_judge_json(proc.stdout)
    out.write_text(json.dumps(v, indent=2))
    fails = [s for s in v.get("shots", []) if not s.get("pass")]
    for s in v.get("shots", []):
        print(f"JUDGE3D shot {s.get('shot')}: {s.get('score')} {'PASS' if s.get('pass') else 'FAIL'}")
        for p in s.get("problems", []): print(f"   problem: {p}")
        for b in s.get("better", []): print(f"   better: {b}")
    return 2 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
