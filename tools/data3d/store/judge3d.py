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
    1: "HOOK. A self-checkout machine with ERROR on a red screen fires banknotes out of its cash slot while Data "
       "flinches, hops back and ducks. Must read in the first second.",
    2: "9 OUT OF 10. Two shots cut together: Data hauls down a MASTER switch at the head of a row of ten checkout "
       "lanes; CUT on the impact to a high view over his shoulder down the row: nine lanes turn into self-checkout "
       "kiosks one after another while a board over the row counts them, 0 / 10 to 9 / 10, and the one staffed lane "
       "(CASHIER sign, a cashier at the till) stays.",
    3: "HALF A MILLION JOBS IN TEN YEARS. On the staff wall, a CASHIER JOBS GONE counter over the OUR TEAM board over "
       "a big calendar. Data rips the years off the calendar (2014 to 2024, every other year) and drops them; with each "
       "one a face falls off the team board to the floor and the counter climbs 100,000, to 500,000. The torn pages "
       "and the fallen photos pile on the floor.",
    4: "TWICE THE LOSSES. Two LOSSES jars, labelled CASHIER and SELF CHECKOUT; Data pours coins from a sack into each; "
       "the coins must be seen falling in, and the self-checkout jar must end over twice as full.",
    5: "CLOSING. Every lane is self-checkout and blinking red; Data shrugs, then waves, then the camera cranes up and "
       "back to the whole red-flashing row.",
}

BAR = """You are the director of a 3D animated YouTube Short starring Data, a small teal cartoon scientist in a lab
coat and glasses. The bar is a professional studio short: the operator will not accept anything they would have to
point out themselves. Grade each shot in two tiers.

HARD DEFECTS (the operator's bare minimums). A shot with ANY of these FAILS, whatever else is good. Name the frame(s):
- BODY: a limb bent the way no body bends, a twisted or snapped wrist, an arm through the body, a hand that should hold
  something visibly not on it, feet sunk in the floor.
- CONSEQUENCE: the shot's action happens but its RESULT is not seen (the money never seen coming out, pages not seen
  falling and landing, coins not seen going into a jar, lanes not seen changing), or it happens off-frame/behind Data.
- BACK TO CAMERA: Data's back, or the back of his head, to the camera for longer than a quick glance.
- BROKEN: a glitch, a pop, an object appearing from nowhere, a subject cut by the frame edge for most of the shot,
  the text that carries the shot's point unreadable on a phone.
- NOT THE POINT: someone seeing only this shot could not say what it shows (the FOR line below).

NOTES: everything else a demanding director would improve (composition, emphasis, acting, timing, polish). List them
in "better", most important first. They lower the score; they do not fail the shot on their own.

How to read the sheets: each is every 4th frame of a 24 fps shot (about six frames a second), so a held pose shows on
a few frames and a fast move may carry motion blur, which is normal. Background people are deliberately minimal
faceless figures (operator ruling), and the store set, its floor and lighting, and Data's design are approved: never
grade those.

score: 0-100 for the shot as a finished piece. pass: true only when there is NO hard defect AND score >= 70.
Return ONLY JSON: {"shots": [{"shot": N, "score": 0-100, "pass": true|false, "hard": ["defect, frames"],
"problems": ["..."], "better": ["..."]}]}"""

PASS_SCORE = 70


def strip(frames, out, h=540, cols=8):
    ims = [Image.open(p).convert("RGB") for p in frames]
    ims = [im.resize((int(im.width * h / im.height), h)) for im in ims]
    rows = (len(ims) + cols - 1) // cols; w = ims[0].width
    S = Image.new("RGB", (w * min(cols, len(ims)), h * rows), (20, 20, 20))
    for i, im in enumerate(ims): S.paste(im, ((i % cols) * w, (i // cols) * h))
    S.save(out, quality=88); return out


def main():
    proof, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()   # the judge Reads absolute paths
    if not shutil.which("claude"):
        print("JUDGE3D: no claude CLI: no judge, no pass"); return 1
    sheets = []
    only = [int(x) for x in os.environ.get("SHOTS", "").split()] or sorted(BRIEFS)   # re-judge just the shots that were sent back
    for n in only:
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
    for s in v.get("shots", []):          # code holds the rule, whatever the judge wrote in "pass"
        s["pass"] = bool(s.get("pass")) and not s.get("hard") and (s.get("score") or 0) >= PASS_SCORE
    out.write_text(json.dumps(v, indent=2))
    fails = [s for s in v.get("shots", []) if not s.get("pass")]
    for s in v.get("shots", []):
        print(f"JUDGE3D shot {s.get('shot')}: {s.get('score')} {'PASS' if s.get('pass') else 'FAIL'}")
        for p in s.get("hard", []): print(f"   HARD: {p}")
        for p in s.get("problems", []): print(f"   problem: {p}")
        for b in s.get("better", []): print(f"   better: {b}")
    return 2 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
