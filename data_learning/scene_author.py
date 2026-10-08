"""THE BRAIN DRAWS THE SCENE — subject scenes for stories no one hand-drew.

Operator, 2026-09-23: *"make sure that we can constantly make something that
looks that good in a wide variety of situations and a wide variety of
data."* Three stories have hand-drawn teacher scenes
(`subject_scenes.TEACHERS`). Every other story's beats are drawn by the
Claude HEADLESS BRAIN — the same `claude` CLI on the subscription the
showrunner runs on — which writes one `scene(cr, t, u, pts, host)` per beat
from the kit, two teachers and the operator's reference sample.

Nothing it writes is trusted:

  * SANDBOX: the code is parsed first and refused if it imports anything,
    touches a dunder, or names a builtin outside a small allow-list; it then
    runs with the KIT as its only globals — no files, no network, no os.
  * VERIFIED by the same checks the teachers pass
    (`tests/test_subject_scenes.py`): it renders full-bleed with Data in
    every frame; every number it prints is the data's or arithmetic on it;
    reversing the data's order does not change the numbers; and the end of
    the scene still moves by the showrunner's own temporal measure.
  * Only a verified scene is used and saved (`illustrated_scene` on the
    segment in niche.config.json), so the next render reuses it. Anything
    else returns None, and the renderer falls back to the current look and
    records the fallback.
"""
from __future__ import annotations

import ast
import inspect
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from data_learning import subject_scenes as SS

TIMEOUT_S = int(os.environ.get("SCENE_AUTHOR_TIMEOUT", "420"))

# A VIDEO'S DRAWING TIME IS BOUNDED. An explainer run renders four videos in
# one 300-minute job, each needing up to five first drafts (hook, beats,
# closing) at three attempts apiece — unbounded, one slow brain could time the
# whole job out with nothing posted. `set_budget` starts a video's clock;
# once it is spent `author` stops asking, the video falls back to the current
# look (one video, one look), and the drafts that did land are saved for the
# next run. Drafts are drawn once per story, so this binds on first sight only.
BUDGET_S = float(os.environ.get("SCENE_AUTHOR_BUDGET_S", "1200"))
_DEADLINE = None


def set_budget(seconds: float | None = None) -> None:
    import time
    global _DEADLINE
    _DEADLINE = time.monotonic() + (BUDGET_S if seconds is None else seconds)


def _remaining() -> float:
    import time
    return float("inf") if _DEADLINE is None else _DEADLINE - time.monotonic()

#: The kit the brain may call — the reference's own vocabulary.
KIT_NAMES = ("vgrad", "glow", "text", "fit_readout", "by_time", "tree", "stump",
             "cow", "truck", "sack", "cup", "steam", "birds",
             "dawn_sky", "cafe", "rowhouse", "street", "traffic",
             "heat_shimmer", "shape_path", "stride", "walk", "step_through", "landed", "READOUT_SHOWS", "STEP_BOB", "PACE_PERIOD", "EDGE", "clamp", "ease", "pop",
             "seg", "W", "H", "P", "_c", "scar_path", "SCAR", "FOREST_Y",
             "STREET_Y", "_TREES", "forest_floor", "FRANCE",
             # THE LIGHT (2026-10-05, "the art in general on the B clips
             # needs to be better"): one key light, lit face to shadow face,
             # a rim, an edge, a contact shadow — illustrated.py
             "solid", "box", "cylinder", "disc", "contact_shadow", "haze",
             "vignette", "edge", "KEY", "FINISHES",
             # THE SHOT (2026-10-07, "ok now we are talking"): a low sun,
             # far-to-near depth, a three-quarter hero, things by the camera
             "landscape", "foreground", "building", "cast_shadow", "ridge",
             "treeline", "hen", "SUN", "SETTINGS", "heap_path", "heap_top", "bottle", "PLASTIC",
             # THE SCALE IN THE SHOT (2026-10-07, "boxes on top of the video
             # doesn't help ... glance at it and gauge the scale")
             "then_mark", "ghost", "times_ticks")
SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict)
                 else getattr(__builtins__, n)
                 for n in ("range", "len", "min", "max", "abs", "int", "float",
                           "str", "round", "enumerate", "zip", "sorted", "sum",
                           "list", "dict", "tuple", "isinstance", "reversed",
                           "any", "all", "bool", "divmod", "pow", "next",
                           "iter", "map", "filter", "set", "frozenset", "format",
                           "ValueError", "IndexError", "KeyError",
                           "ZeroDivisionError", "Exception")}
#: The seven stances, plus every TOOL act (mascot_director.TOOL_ACTS): work
#: is done WITH the tool the job needs — operator, 2026-10-02: "give him
#: like a pick axe and have it feel like he is breaking the ice".
from data_learning.mascot_director import TOOL_ACTS, tool_for_cause  # noqa: E402
STANCES = ("point", "cheer", "strain", "climb", "shock", "think", "hold_up")
ROLES = STANCES + tuple(TOOL_ACTS)


def kit_globals() -> dict:
    import cairo
    from shared import look
    g = {n: getattr(SS, n) for n in KIT_NAMES}
    from data_learning import illustrated as _il
    g.update(math=math, cairo=cairo, INK=look.INK, INK_2=look.INK_2,
             WARN=look.WARN, look=look, fit_size=_il.fit_size, I=_il,
             __builtins__=SAFE_BUILTINS)
    return g


class Refused(ValueError):
    pass


def check_source(code: str) -> None:
    """Refuse code that could reach outside the kit, before it runs."""
    tree = ast.parse(code)
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not any(f.name == "scene" for f in fns):
        raise Refused("no `def scene(cr, t, u, pts, host)`")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global,
                             ast.Nonlocal, ast.AsyncFunctionDef, ast.Await)):
            raise Refused(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise Refused(f"dunder access .{node.attr}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise Refused(f"dunder name {node.id}")
        if isinstance(node, ast.Name) and node.id in ("open", "exec", "eval",
                                                      "compile", "getattr",
                                                      "setattr", "globals",
                                                      "locals", "vars", "input"):
            raise Refused(f"{node.id} is not allowed")


def compile_scene(code: str):
    check_source(code)
    ns = kit_globals()
    exec(compile(code, "<brain scene>", "exec"), ns)          # noqa: S102 — sandboxed
    fn = ns.get("scene")
    if not callable(fn):
        raise Refused("scene is not callable")
    fn.__name__ = "brain_scene"
    fn.__scene_code__ = code
    return fn


def crash_at(fn, e: BaseException) -> str:
    """Where in the brain's own code `e` was raised: " (line N: `src`)".

    "ValueError: too many values to unpack (expected 2)" was attempt 1 of
    most brain drafts for a fortnight (2026-10-04..06) and the redraw was
    told nothing else, so attempt 2 guessed again. With the line it can see
    it unpacked `text()`'s four-number box into two names."""
    import traceback
    code = getattr(fn, "__scene_code__", "") or ""
    frames = [f for f in traceback.extract_tb(e.__traceback__)
              if f.filename == "<brain scene>"]
    if not frames:
        return ""
    n = frames[-1].lineno or 0
    lines = code.splitlines()
    src = lines[n - 1].strip()[:120] if 0 < n <= len(lines) else ""
    return f" (line {n}: `{src}`)" if src else f" (line {n})"


# --------------------------------------------- what the scene says it shows

#: The three lines every scene's docstring opens with. They are what the
#: GLANCE (below) checks the picture against — a scene that cannot say what
#: its hero is, what its substance is and what Data does to make the number
#: move has not decided, and the viewer will not be able to either.
DECLARE = ("HERO", "SUBSTANCE", "CAUSE")
_DECL = re.compile(r"^\s*(HERO|SUBSTANCE|CAUSE)\s*:\s*(.+?)\s*$", re.M)


def declared(fn) -> dict:
    """{HERO, SUBSTANCE, CAUSE} from the scene's docstring, each a short
    phrase; a missing line is a missing key."""
    doc = getattr(fn, "__doc__", None) or ""
    out = {}
    for m in _DECL.finditer(doc):
        out.setdefault(m.group(1), m.group(2).rstrip("."))
    return out


def declaration_problems(fn) -> list[str]:
    missing = [k for k in DECLARE if not declared(fn).get(k)]
    if missing:
        return [f"the docstring must open with {', '.join(k + ':' for k in DECLARE)}"
                f" lines (missing {', '.join(missing)}) — the thing the number "
                f"is about, the material that moves, and the act of Data's that "
                f"moves it"]
    return []


# -------------------------------------------------------------- the GLANCE
#
# Operator, 2026-10-01, on the cremation video: the casket "should be more
# easily identifiable on first glance — I can't really tell that this is a
# coffin until I watched it more than once"; the urn Data filled with blue
# "ash" read as "the water pouring one ... out of place, should have been a
# crematorium or fire that Data was throwing fuel on"; and the lantern
# where he "pulls a liquid up with a rope ... makes no sense". None of that
# is measurable from the code — the code checks passed all three — so a
# VIEWER looks at the frame: two frames of the scene, stripped of every
# word and of Data, and a brain with no context but the subject has to name
# the object, say what the material is, and say whether the act would
# really cause the change. The scene's own HERO / SUBSTANCE / CAUSE lines
# are what its answers are held against.

GLANCE_AT = (0.12, 0.55)        # the hero must read EARLY, and mid-beat
GLANCE_MODEL = os.environ.get("SCENE_GLANCE_MODEL", "sonnet")
GLANCE_TIMEOUT = int(os.environ.get("SCENE_GLANCE_TIMEOUT", "150"))

# The look is UNAIDED, BLIND and at PHONE SIZE. Unaided: the viewer names
# what they see before anyone says what it is meant to be — a question
# that said "is this recognisably a casket?" got a yes on the casket the
# operator could not recognise. Blind: the viewer is not told the subject
# either — told "cremation", a plank box in a chapel is a coffin; the
# operator read the title too and still could not tell. Phone size: the
# frames go in at 270x480, how a Short is actually seen; at 1080x1920 the
# same viewer read the posted casket "from its own shape" three times out
# of three, and at phone size "from the setting" three out of three — "no
# lid detail or handles, so it could also be a wooden crate or chest",
# which is the operator's note word for word (2026-10-01). A hero that is
# only recognisable from where it stands is refused.
PHONE = (270, 480)

_LOOK = """You are a viewer glancing at two small frames of a short vertical \
animation. Every word and the mascot have been removed, so only the picture \
is left, and you have not been told what it is about. The frames are these \
image files — READ each with the Read tool:
{listing}

Answer as ONE JSON object, nothing else:
{{"object": "<the main object, in 2-5 words, as you would name it to a \
friend who asked what it was>",
 "object_from": "<'its own shape' if the object's own silhouette and details \
told you what it is on sight; 'the setting' if you worked it out from where \
it is and what is around it; 'a guess' if neither>",
 "tells": "<the 1-3 details of the object ITSELF that identify it, or what \
is missing that would ('no lid detail or handles')>",
 "substance": "<the material that is rising, piling, pouring, burning or \
moving between the frames, in 1-4 words — what it LOOKS like, not what it \
might stand for; 'nothing' if none>",
 "change": "<what happens between the first frame and the second, one \
sentence>",
 "how_much": "<how big that change LOOKS: 'none', 'barely' (you had to \
compare closely), 'clear' or 'dramatic'>",
 "shot": "<'a place' if it is somewhere you could stand, with ground, light \
and near-and-far depth; 'a diagram' if it is an object shown front-on \
against a backdrop>"}}"""

_JUDGE = """A viewer saw two frames of an animated scene with every word \
and the mascot removed, and described it unaided:
  object: {object}
  substance: {substance}
  change: {change}

The scene's author says it shows:
  HERO: {hero}
  SUBSTANCE: {substance_said}
  CAUSE: {cause}

Answer as ONE JSON object, nothing else:
{{"is_hero": <true only if the viewer's object IS the author's hero — the \
same thing under another name counts (coffin/casket), a different thing \
does not (crate/casket, tank/urn)>,
 "substance_fits": <true only if the viewer's substance IS the author's — \
blue liquid is not ash, a glowing fill is not embers>,
 "cause_makes_sense": <true only if the author's CAUSE would physically \
produce the viewer's change — a rope cannot raise a liquid; a bellows does \
not fill a jar>,
 "why": "<one sentence on anything you answered false>"}}"""


def ask_glance(prompt: str, images: list[str]) -> dict | None:
    """The viewer's answers, or None when no brain can look (the caller
    then passes the scene on its code checks and logs that it did)."""
    if not shutil.which("claude"):
        return None
    from scripts import showrunner_review as sr
    try:
        cmd = ["claude", "-p", prompt, "--model", GLANCE_MODEL,
               "--output-format", "text"]
        if images:
            cmd[-2:-2] = ["--allowedTools", "Read"]
        proc = subprocess.run(cmd,
                              capture_output=True, text=True,
                              timeout=max(30.0, min(GLANCE_TIMEOUT, _remaining())))
        if proc.returncode != 0:
            return None
        return sr.parse_judge_json(proc.stdout or "")
    except Exception:  # noqa: BLE001 — a viewer who cannot look is not a verdict
        return None


def glance_frames(fn, pts, out_dir, at=GLANCE_AT) -> list[str]:
    """Render the scene at each `at` with every word and Data REMOVED, at
    PHONE size, to PNGs. What is left is what a viewer has to recognise
    unaided."""
    import cairo
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    real_t, real_ro = SS.text, SS.fit_readout
    g = fn.__globals__

    def no_text(cr, s, *a, **k):
        return None

    def no_readout(cr, big, small, *a, **k):
        return None

    def no_host(role, x, fy, h, pace=False, beat=0):
        return None
    paths = []
    try:
        SS.text, SS.fit_readout = no_text, no_readout
        g["text"], g["fit_readout"] = no_text, no_readout
        for u in at:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
            cr = cairo.Context(surf)
            fn(cr, 3.0 + u * 10, u, pts, no_host)
            surf.flush()
            p = out_dir / f"glance_u{int(u * 100):02d}.png"
            surf.write_to_png(str(p))
            from PIL import Image
            Image.open(p).resize(PHONE, Image.LANCZOS).save(p)   # as a Short is seen
            paths.append(str(p))
    finally:
        SS.text, SS.fit_readout = real_t, real_ro
        g["text"], g["fit_readout"] = real_t, real_ro
    return paths


def glance(fn, pts, log=print) -> list[str]:
    """Problems a VIEWER has with the picture alone: the hero is not
    recognisable, the substance reads as something else, the cause could
    not produce the effect. The viewer describes the frames UNAIDED first;
    only then is that description held against the scene's own HERO /
    SUBSTANCE / CAUSE. Empty when they agree — or when no viewer is
    available, which is logged, never silent."""
    decl = declared(fn)
    if any(not decl.get(k) for k in DECLARE):
        return declaration_problems(fn)
    with tempfile.TemporaryDirectory(prefix="glance_") as td:
        try:
            frames = glance_frames(fn, pts, td)
        except Exception as e:  # noqa: BLE001
            return [f"crashed while rendering the glance frames: {e}"
                    f"{crash_at(fn, e)}"]
        listing = "\n".join(f"- at {int(u * 100)}% of the beat: {p}"
                             for u, p in zip(GLANCE_AT, frames))
        seen = ask_glance(_LOOK.format(listing=listing), frames)
    if not isinstance(seen, dict):
        log("[scene_author] no viewer for the glance — passed on code checks only")
        return []
    obj = str(seen.get("object") or "?").strip()
    sub = str(seen.get("substance") or "?").strip()
    chg = str(seen.get("change") or "?").strip()
    frm = str(seen.get("object_from") or "").strip().lower()
    tells = str(seen.get("tells") or "").strip()
    much = str(seen.get("how_much") or "").strip().lower()
    shot = str(seen.get("shot") or "").strip().lower()
    ans = ask_glance(_JUDGE.format(object=obj, substance=sub, change=chg,
                                   hero=decl["HERO"], substance_said=decl["SUBSTANCE"],
                                   cause=decl["CAUSE"]), [])
    if not isinstance(ans, dict):
        log("[scene_author] no viewer for the glance — passed on code checks only")
        return []
    why = str(ans.get("why") or "").strip()
    problems = []
    if ans.get("is_hero") is False:
        problems.append(f"a viewer could not tell the hero is {decl['HERO']!r} — "
                        f"unaided, they called it {obj!r}. Draw it by its signature "
                        f"silhouette and its tells, big, before any effect "
                        f"touches it. {why}".rstrip())
    elif frm and "own shape" not in frm:
        # named right, but only from where it stands: the operator's casket
        problems.append(f"the hero {decl['HERO']!r} is recognisable only from "
                        f"its setting, not from its own shape — at phone size a "
                        f"viewer said: {tells!r}. Give the object itself the "
                        f"tells that name it at a glance (a casket: the six-sided "
                        f"taper, the lid seam, the handles), big enough to read "
                        f"small".rstrip())
    if ans.get("substance_fits") is False:
        problems.append(f"the substance reads as {sub!r}, not {decl['SUBSTANCE']!r} "
                        f"— a material keeps its own colour and form (ash is grey "
                        f"dust, fire is flame, water is blue); the accent marks "
                        f"the share, it never recolours the stuff. {why}".rstrip())
    if much in ("none", "barely"):
        problems.append(f"a viewer saw the change as {much!r} ({chg!r}) — the "
                        f"thing that moves must change BIG enough to see at a "
                        f"glance; draw what piles up, empties or spreads until "
                        f"it is large, not an object that barely differs")
    if "diagram" in shot:
        problems.append("a viewer called it a diagram, not a place — an object "
                        "front-on on a backdrop; build the SETTING around it "
                        "with near-and-far depth, three-quarter view and "
                        "something by the camera (rule 13)")
    if ans.get("cause_makes_sense") is False:
        problems.append(f"{decl['CAUSE']!r} could not cause what a viewer saw "
                        f"({chg!r}) — Data's act must be the one that would really "
                        f"produce the change (pouring fills, hauling lifts a solid, "
                        f"feeding grows a fire). {why}".rstrip())
    return problems


# ------------------------------------------------------------- verification

def _allowed_numbers(pts):
    vals = [v for _, v in pts]
    tot = sum(vals) or 1.0
    nums = set(vals)
    nums |= {abs(a - b) for a, b in itertools.combinations(vals, 2)}
    nums |= {v / tot * 100 for v in vals}
    nums |= {a / b for a, b in itertools.permutations(vals, 2) if b}
    nums |= {float(m) for l, _ in pts
             for m in re.findall(r"(?:1[6-9]|20)\d{2}", str(l))}
    nums |= {float(m) for l, _ in pts for m in re.findall(r"\d+(?:\.\d+)?", str(l))}
    return nums


def _is_scale_mark(x, vmax):
    """A round mark on a drawn scale (a thermometer's +2° steps, a tank's
    25%s) — a tick, not a claim. Round means a whole multiple of 1, 2 or 5
    times a power of ten, and it must sit inside the data's own range."""
    if x < 0 or x > max(1.0, vmax) * 1.5 or x != int(x):
        return False
    if x == 0:
        return True
    mag = 10 ** int(math.floor(math.log10(x)))
    return any(abs(x / (m * mag) - round(x / (m * mag))) < 1e-9 for m in (1, 2, 5))


def _mispaired(pairs, pts):
    """A readout whose NUMBER is one row's value and whose LABEL names a
    different row: "$1.05" over "2025 · $4.41" (coffee closing, 2026-09-23).
    Returns the problem, or None."""
    rows = [(str(l), float(v)) for l, v in pts]
    for big, small in dict.fromkeys(pairs):
        nums = [float(t.replace(",", "")) for t, _ in _units(big)]
        named = [i for i, (l, _) in enumerate(rows) if l and l in small]
        if not nums or not named:
            continue
        x = nums[0]
        owners = [i for i, (_, v) in enumerate(rows)
                  if any(abs(round(v / sc, 2) - round(x, 2)) < 1e-9
                         for sc in (1.0, 1e3, 1e6, 1e9))]
        if owners and not set(owners) & set(named):
            return (f"prints {big!r} over {small!r} — that number is "
                    f"{rows[owners[0]][0]}'s, not {rows[named[0]][0]}'s")
    return None


def _covered(text_box, body) -> float:
    """How much of a text box lies under Data's body box (0..1)."""
    ix = max(0.0, min(text_box[2], body[2]) - max(text_box[0], body[0]))
    iy = max(0.0, min(text_box[3], body[3]) - max(text_box[1], body[1]))
    area = (text_box[2] - text_box[0]) * (text_box[3] - text_box[1])
    return ix * iy / area if area > 0 else 0.0


def _overlap(a, b) -> float:
    """Intersection of two (x0, y0, x1, y1) boxes over the smaller one."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return ix * iy / small if small > 0 else 0.0


def _is_year(x: float) -> bool:
    return x == int(x) and 1600 <= x <= 2100


_NUM_UNIT = re.compile(r"(\$?)(\d[\d,]*\.?\d*)\s*(%|percent|x\b|×)?", re.I)


def _units(text: str) -> list:
    """[(token, unit)] for every number in `text`; unit is '%', '$', 'x' or ''."""
    out = []
    for m in _NUM_UNIT.finditer(text or ""):
        suf = (m.group(3) or "").lower()
        unit = ("%" if suf in ("%", "percent") else "x" if suf in ("x", "×")
                else "$" if m.group(1) else "")
        out.append((m.group(2), unit))
    return out


def _contradicts(tok: str, said: set, raw=(), vmax: float = 100.0):
    """A DERIVED number within 5% of one the narration SAYS, but not it:
    "10,100%" on screen while the voice says "10,000%" (kelp, 2026-09-23).
    A raw data value or a scale tick is true as printed and never clashes.
    Returns the narration's number, or None."""
    try:
        x = float(tok.replace(",", ""))
    except ValueError:
        return None
    if x in said or _is_year(x) or _is_scale_mark(x, vmax):
        return None
    # `said` may hold (value, unit) pairs: only a number in the SAME unit can
    # contradict — "4.2x" (a ratio) is not a misprint of "$4.41" (a price).
    unit = getattr(tok, "unit", None)
    d = len(tok.split(".", 1)[1]) if "." in tok else 0
    if any(abs(round(v / sc, d) - x) < 1e-9 for v in raw for sc in (1.0, 1e3, 1e6, 1e9)):
        return None
    for n in said:
        if isinstance(n, tuple):
            n, n_unit = n
            if unit is not None and n_unit != unit:
                continue
        if n > 0 and not _is_year(n) and 0 < abs(x - n) / n < 0.05:
            return n
    return None


class _Tok(str):
    """A printed number token that knows its unit."""
    unit = None


def _num_ok(tok, allowed, vmax=100.0):
    """Is the printed token a data value (or arithmetic on it) AT THE
    PRECISION IT IS PRINTED? "2.7" must be something that rounds to 2.7 —
    not anything that rounds to 3, which is how a count-up's in-between
    values used to pass."""
    try:
        x = float(tok.replace(",", ""))
    except ValueError:
        return True
    if x in (0.0, 25.0, 50.0, 75.0, 100.0) or _is_scale_mark(x, vmax):
        return True
    d = len(tok.split(".", 1)[1]) if "." in tok else 0
    for a in allowed:
        for scale in (1.0, 1e3, 1e6, 1e9):
            if abs(round(a / scale, d) - x) < 1e-9:
                return True
    return False


#: The narration is burned in from here down: anchored at y=1734, two lines
#: of fs62 (the hook's fs78) reach up to ~1560. A number or Data's feet below
#: this collide with it — "the caption runs under the sign" (coffee hook),
#: "a red caption drawn over the mascot and a tree" (Amazon, 2026-09-23).
CAPTION_Y = 1540

#: MOTION IS MEASURED THE WAY THE JUDGE NOW GRADES IT: judder (still runs of
#: 1-3 samples between moving frames — a low-fps source), the longest hold,
#: and how much of the scene is still. A deliberate hold is fine; the old
#: check refused ANY held frame, and everything built to pass it — specks
#: drifting over every frame, a mascot pacing and waving nonstop, scenes
#: racing — is what the operator called "snow" and "flailing" (2026-09-23).
MAX_JUDDER = 0.04
MAX_HOLD_S = 1.8          # the judge's frozen-stretch ceiling is 45 samples
MAX_STILL = 0.45          # ...and its duplicate-ratio ceiling


def motion_profile(fn, pts, fps: int = 24, secs: float = 6.8) -> dict:
    """{judder, max_hold_s, still} for a scene, rendered as `render_build`
    renders it — a 30fps clock from t=0, Data's acts on the act clock —
    and sampled at the judge's 24fps with the judge's own detector."""
    import cairo
    from PIL import Image
    from scripts import showrunner_review as sr
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    total, n = int(secs * 30), int(secs * fps)
    clock: dict = {}
    px = []
    for k in range(n):
        f = min(total - 1, int(round(k * 30 / fps)))
        cr = cairo.Context(surf)
        t = f / 30.0
        fn(cr, t, f / max(1, total - 1), pts,
           lambda role, x, fy, h, pace=False, beat=0, _cr=cr, _f=f, _t=t: SS.place_host(
               _cr, role, SS.act_phase(clock, (role, int(beat)), _f), None, x, fy, h,
               _t, pace))
        surf.flush()
        im = Image.frombuffer("RGBA", (SS.W, SS.H), bytes(surf.get_data()),
                              "raw", "BGRA", 0, 1)
        px.append(list(im.convert("L").resize((192, 341)).getdata()))
    diffs = [sr._max_block_diff(a, b, 192) for a, b in zip(px, px[1:])]

    def _runs(flags):
        out, r = [], 0
        for f_ in flags:
            if f_:
                r += 1
            elif r:
                out.append(r)
                r = 0
        return out + ([r] if r else [])
    still = [d < sr.BLOCK_MOTION_THRESH for d in diffs]
    pairs = max(1, len(diffs))
    # WHERE it is still, in the scene's own u. "still 52%" alone left the
    # brain guessing, and two of three drafts on 2026-10-07 came back still
    # again (47-52%) on attempt 2 and 3.
    spans, start = [], None
    for i, f_ in enumerate(still + [False]):
        if f_ and start is None:
            start = i
        elif not f_ and start is not None:
            spans.append((start / pairs, i / pairs))
            start = None
    spans.sort(key=lambda s: s[0] - s[1])
    return {"judder": sr.judder_pairs(diffs) / pairs,
            "max_hold_s": max(_runs(still), default=0) / float(fps),
            "still": sum(still) / pairs,
            "still_spans": [s for s in spans if s[1] - s[0] >= 0.03][:4]}


def motion_problems(fn, pts, secs: float | None = None) -> list[str]:
    # a beat's REAL length (SCENE_SECS), not the 10s it was once assumed to be
    m = motion_profile(fn, pts, secs=SCENE_SECS["beat"] if secs is None else secs)
    out = []
    if m["judder"] > MAX_JUDDER:
        out.append(f"it judders: {m['judder']:.0%} of frames are 1-3-frame stalls "
                   f"between moves (allowed {MAX_JUDDER:.0%}) — move smoothly or hold")
    if m["max_hold_s"] > MAX_HOLD_S:
        out.append(f"it freezes for {m['max_hold_s']:.1f}s (allowed {MAX_HOLD_S}s) — "
                   f"a hold is fine, a frozen stretch is not")
    if m["still"] > MAX_STILL:
        where = ", ".join(f"u {a:.2f}-{b:.2f}" for a, b in sorted(m["still_spans"]))
        if sum(b - a for a, b in m["still_spans"]) < m["still"] * 0.6:
            # most of the stillness is in short gaps all through the beat:
            # the motion is there but too slow to register
            where = (where + "; and in short gaps all through it — what moves "
                     "moves too slowly or too small to register (a 90x160px "
                     "cell has to change by 6+ grey levels a frame), so move "
                     "bigger things further, less often").lstrip("; ")
        out.append(f"it is still {m['still']:.0%} of the time (allowed "
                   f"{MAX_STILL:.0%}) — the story has to keep arriving"
                   + (f"; too little moves at {where}: give each of those "
                      f"stretches a move of the subject itself (the next "
                      f"step starting, the thing settling, Data's next act)"
                      if where else ""))
    return out


#: The rubric's mascot anchor (docs/DIRECTOR.md): "Data is IN the scene
#: DOING a real bit tied to the content (setup -> action -> payoff), and he
#: MOVES / changes position." Measured, not asserted: over the beat he takes
#: at least two acts and his own spot (pacing aside) travels this far.
MIN_ROLES = 2
MIN_TRAVEL = 150.0
#: ...and he PERFORMS more than he presents. mascot was the channel's biggest
#: loss on its first illustrated day (-7.5 of 18 on average, "Data mostly
#: waves"), and the teachers the judge praised (riding the mercury, pushing
#: the rim) were 71-100% physical acts while the ones it called "just waves"
#: were 0%. point / cheer / shock / think are the setup and the reaction.
ACT_ROLES = ("strain", "climb", "hold_up") + tuple(TOOL_ACTS)
MIN_ACT = 0.5


def bit_problems(fn, pts) -> list[str]:
    """Does Data have a BIT in this scene, or is he a sticker? The coffee
    story's teachers failed this and the showrunner called that video's
    mascot decorative (52, 2026-09-23)."""
    import cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    calls = []
    for k in range(11):
        u = k / 10
        fn(cairo.Context(surf), 3.0 + u * 8, u, pts,
           lambda role, x, fy, h, pace=False, beat=0: calls.append((role, x, fy)))
    if not calls:
        return []                        # "host not called" is reported above
    out = []
    roles = {c[0] for c in calls}
    if len(roles) < MIN_ROLES:
        out.append(f"Data has one act ({sorted(roles)[0]!r}) all beat — give him "
                   f"a bit: a setup, an action tied to the number, a reaction")
    act = sum(c[0] in ACT_ROLES for c in calls) / len(calls)
    if act < MIN_ACT:
        out.append(f"Data presents more than he performs: {act:.0%} of the beat "
                   f"in a physical act ({', '.join(ACT_ROLES)}); point/cheer/"
                   f"shock/think are only the setup and the reaction")
    xs, ys = [c[1] for c in calls], [c[2] for c in calls]
    if max(max(xs) - min(xs), max(ys) - min(ys)) < MIN_TRAVEL:
        out.append(f"Data stays on one spot (moves "
                   f"{max(max(xs) - min(xs), max(ys) - min(ys)):.0f}px) — his "
                   f"place should follow what he is doing, >= {MIN_TRAVEL:.0f}px")
    return out


def tool_problems(fn, pts, decl: dict) -> list[str]:
    """The CAUSE names work; does Data do it WITH THE TOOL? "Breaking the
    iceberg ... just flailing his arms around" (operator, 2026-10-02): the
    scene said `strain`, which is a brace with empty hands. A CAUSE whose
    verb has a tool act (mascot_director.VERB_TOOLS) must perform that act
    (or another tool act) for part of the beat."""
    need = tool_for_cause(decl.get("CAUSE", ""))
    if not need:
        return []
    verb, act = need
    import cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    roles = []
    for k in range(11):
        u = k / 10
        fn(cairo.Context(surf), 3.0 + u * 8, u, pts,
           lambda role, x, fy, h, pace=False, beat=0: roles.append(role))
    used = [r for r in roles if r in TOOL_ACTS]
    if used:
        return []
    performing = sorted({r for r in roles if r in ("strain", "climb", "hold_up")}) or sorted(set(roles))
    return [f"CAUSE says Data {verb}s, but he performs {performing} — empty hands "
            f"read as flailing. Do the work with the tool: host({act!r}, x, "
            f"foot_y, h, beat=k) ({TOOL_ACTS[act]}), and advance beat= each time "
            f"the thing changes so one swing lands per change"]


#: THE ART IS LIT, NOT FLAT (operator, 2026-10-05: "the art in general on
#: the B clips needs to be better"). Measured on the posted scenes: the
#: hero band of a brain scene was up to 55% exact-colour slabs — a gold
#: pile of identical flat ellipses, two flat pans, a flat coffin — while
#: the world behind it was soft gradients. A lit solid (illustrated.solid,
#: box, cylinder, disc) has no slab wider than a few pixels. The check
#: counts, in the band the hero lives in, pixels whose colour is EXACTLY
#: the colour `FLAT_STEP` px to the right and below; more than
#: `FLAT_MAX` of the band is clip art.
FLAT_STEP = 12            # a slab: the same colour this far right AND down...
FLAT_FAR = 96             # ...and still the same this far — a slow sky gradient
#                           changes by a level inside it, a flat polygon does not
FLAT_MAX = 0.12           # teachers measure <= 0.07; the posted flat scenes 0.15-0.25
FLAT_BAND = (470, 1500)


def flat_fraction(surf, band=FLAT_BAND, step=FLAT_STEP, far=FLAT_FAR) -> float:
    import numpy as np
    stride = surf.get_stride() // 4
    a = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(SS.H, stride, 4)
    a = a[band[0]:band[1], :SS.W, :3].astype(np.int16)
    h, w = a.shape[:2]
    out = np.ones((h - far, w - far), dtype=bool)
    for k in (step, far):
        r = (np.abs(a[:, k:] - a[:, :-k]).sum(axis=2) == 0)[:h - far, :w - far]
        d = (np.abs(a[k:] - a[:-k]).sum(axis=2) == 0)[:h - far, :w - far]
        out &= r & d
    return float(out.mean())


def craft_problems(fn, pts, at=(0.3, 0.85)) -> list[str]:
    """Refuse a scene whose hero band is mostly flat colour. Rendered with
    Data in it (his rig is cel-shaded and small) and with the text."""
    import cairo
    from data_learning import illustrated as I
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    worst = 0.0
    for u in at:
        cr = cairo.Context(surf)
        clock: dict = {}
        f = int(u * 180)

        def host(role, x, fy, h, pace=False, beat=0, _cr=cr, _f=f):
            SS.place_host(_cr, role, SS.act_phase(clock, (role, int(beat)), _f),
                          None, x, fy, h, _f / 30.0, pace)
        with I.text_layer(cr):
            fn(cr, 3.0 + u * 8, u, pts, host)
        surf.flush()
        worst = max(worst, flat_fraction(surf))
    if worst > FLAT_MAX:
        return [f"the picture is {worst:.0%} flat colour in the band the hero "
                f"lives in (max {FLAT_MAX:.0%}) — clip art. Light every solid: "
                f"draw its path and call solid(cr, rgb) (box(), cylinder(), "
                f"disc() for those shapes), a contact_shadow() under what "
                f"stands on the ground, haze() over the distance, vignette() "
                f"last. Never cr.fill() a subject in one flat colour"]
    return []


#: A number has to stay up long enough to READ. Brain hooks cycled a value
#: every few frames and the judge wrote "a hook number that flickers too fast
#: to register" (Amazon, 2026-09-23).
MIN_DWELL_S = 0.7

#: Operator, 2026-10-07, of a bone-loss scene with -1.5%, 1% and 1.5x stacked
#: beside the bone (the plastic pile beside it, one number and its x2.9, was
#: the one he liked): a viewer glances. Text at or above HEADLINE_PX with a
#: digit in it is a headline number; no frame shows more than MAX_HEADLINES.
HEADLINE_PX = 64
MAX_HEADLINES = 2


#: Operator, 2026-10-07, of the bird flu closing: "the picket fence at the
#: end is already hard to understand, then we only have it on screen for like
#: a second ... it's like whiplash, I didn't even have time to process." Its
#: last number landed at 80% of a 4-second scene, so the finished picture was
#: up for 0.8s before the video ended. Not longer beats: an EARLIER payoff.
#: Every number a scene ends on must be up, unbroken, from PAYOFF_BY of the
#: beat — or earlier, so it holds READ_S seconds — to the end. The world may
#: keep moving after that; the story may not.
PAYOFF_BY = 0.6
READ_S = 1.8


def land_by(secs: float | None = None) -> float:
    """The u by which a ~`secs` scene must have its whole payoff up."""
    secs = SCENE_SECS["beat"] if secs is None else secs
    return min(PAYOFF_BY, 1.0 - READ_S / max(secs, READ_S + 0.1))


def payoff_problems(fn, pts, secs: float | None = None) -> list[str]:
    """The scene's FINISHED picture lands too late to be read: a number it
    ends on first appears (and stays) after `land_by` of the beat."""
    import cairo
    secs = SCENE_SECS["beat"] if secs is None else secs
    by = land_by(secs)
    real = SS.text
    real_ro = SS.fit_readout
    g = fn.__globals__
    frames = []

    def spy(cr, s, *a, **k):
        box = real(cr, s, *a, **k)
        alpha = k.get("alpha", a[6] if len(a) > 6 else 1.0)
        if box and re.search(r"\d", str(s)) and (alpha or 0) > 0.3:
            frames[-1].add(str(s))
        return box
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    try:
        g["text"], SS.text = spy, spy
        g["fit_readout"] = real_ro
        for k in range(41):
            frames.append(set())
            fn(cairo.Context(surf), 3.0 + k / 40 * 10, k / 40, pts,
               lambda *a, **kw: None)
    finally:
        g["text"], SS.text = real, real
    last = frames[-1]
    late = []
    for t_ in last:
        k = 40
        while k > 0 and t_ in frames[k - 1]:
            k -= 1
        if k / 40 > by + 1e-9:
            late.append((k / 40, t_))
    if not late:
        return []
    u_, t_ = max(late)
    return [f"its last number {t_!r} only lands at u={u_:.2f} and the scene "
            f"ends at u=1 — about {(1 - u_) * secs:.1f}s of a ~{secs:.0f}s "
            f"beat to read the finished picture. Land the WHOLE payoff (every "
            f"number it ends on, the end state of the hero) by u={by:.2f} "
            f"and HOLD it; after that keep the world moving (Data, birds, "
            f"steam, light), never the story"]


def verify(fn, pts, say: str = "", secs: float | None = None) -> list[str]:
    """Every check a teacher scene passes. Empty list = usable. `say` is the
    beat's narration: a number the story itself states ("the 1930s") may be
    printed; the editorial gate has already held the narration to the data.
    `secs` is how long the scene is on screen; a beat's by default."""
    secs = SCENE_SECS["beat"] if secs is None else secs
    import cairo
    import numpy as np
    from PIL import Image
    from scripts import showrunner_review as sr
    problems = []
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    texts, hosts = [], []
    real = SS.text

    real_ro = SS.fit_readout
    pairs = []                         # (big, small) of every readout

    def ro_spy(cr, big, small, *a, **k):
        pairs.append((str(big), str(small)))
        return real_ro(cr, big, small, *a, **k)

    low = []
    boxes = []                         # (text, box) visible in THIS frame
    overlaps = []
    covered = []                       # text Data is drawn on top of

    bodies = []                        # Data's body in THIS frame, once drawn
    on_data = []                       # text drawn AFTER him, over him
    crowded = []                       # (frame u, headline numbers in it)
    heads = []                         # headline numbers visible in THIS frame

    def spy(cr, s, *a, **k):
        texts.append(str(s))
        if len(a) >= 2 and isinstance(a[1], (int, float)) and a[1] > CAPTION_Y:
            low.append((str(s), a[1]))
        box = real(cr, s, *a, **k)
        alpha = k.get("alpha", a[6] if len(a) > 6 else 1.0)
        if box and str(s).strip() and (alpha or 0) > 0.3:
            for other, ob in boxes:
                if _overlap(box, ob) > 0.15:
                    overlaps.append((other, str(s)))
            boxes.append((str(s), box))
            for body in bodies:
                if _covered(box, body) > 0.25:
                    on_data.append(str(s))
            size = a[2] if len(a) > 2 else k.get("size", 0)
            if (isinstance(size, (int, float)) and size >= HEADLINE_PX
                    and re.search(r"\d", str(s))):
                heads.append(str(s))
        return box

    def run(rows, u, record=True):
        boxes.clear()
        bodies.clear()
        heads.clear()
        cr = cairo.Context(surf)
        # Spy on the kit too: a number printed through fit_readout or any
        # other helper is still a number on screen.
        fn.__globals__["text"] = spy
        SS.text = spy
        fn.__globals__["fit_readout"] = ro_spy
        def host(role, x, fy, h, pace=False, beat=0):
            hosts.append((role, x, fy, h))
            # Where Data can be while he performs: his body, widened by his
            # walk and lifted by his step when he paces.
            reach = SS.PACE_AMP if pace else 20.0
            body = (x - 0.3 * h - reach, fy - h - (SS.STEP_BOB if pace else 20.0),
                    x + 0.3 * h + reach, fy)
            for t_, b_ in boxes:              # text drawn BEFORE him, under him
                if _covered(b_, body) > 0.25:
                    covered.append(t_)
            bodies.append(body)
        try:
            fn(cr, 3.0 + u * 10, u, rows, host)
            if record and len(set(heads)) > MAX_HEADLINES:
                crowded.append((u, list(dict.fromkeys(heads))))
        finally:
            fn.__globals__["text"] = real
            SS.text = real
            fn.__globals__["fit_readout"] = real_ro

    # Numbers are read at ELEVEN points in the beat, not three: a readout
    # that counts up between two data points printed "$3.24 · February 2025"
    # mid-glide, and u=0/0.5/1 all happened to land on real values.
    seen = []
    shown, streak = {}, {}             # number text -> longest unbroken run
    try:
        for k in range(41):
            texts.clear()
            run(pts, k / 40)
            seen += texts
            now = {t_ for t_ in texts if re.search(r"\d", t_)}
            streak = {t_: streak.get(t_, 0) + 1 for t_ in now}
            for t_, c in streak.items():
                shown[t_] = max(shown.get(t_, 0), c)
        final = list(texts)
    except Exception as e:  # noqa: BLE001
        return [f"crashed: {type(e).__name__}: {str(e)[:160]}{crash_at(fn, e)}"]
    problems += declaration_problems(fn)
    if not declaration_problems(fn):
        problems += tool_problems(fn, pts, declared(fn))
    try:
        problems += craft_problems(fn, pts)
    except Exception as e:  # noqa: BLE001 — a crash here is reported above
        problems.append(f"craft check crashed: {e}")
    if len(hosts) < 11:
        problems.append("Data is missing from a frame (host not called)")
    problems += bit_problems(fn, pts)
    problems += payoff_problems(fn, pts, secs)
    brief_ = [t_ for t_, c in shown.items() if c / 40 * secs < MIN_DWELL_S]
    if brief_:
        problems.append(f"shows {brief_[0]!r} for under {MIN_DWELL_S}s of a "
                        f"~{secs:.0f}s scene — a number must stay up long "
                        f"enough to read ({len(brief_)} such)")
    mis = _mispaired(pairs, pts)
    if mis:
        problems.append(mis)
    if covered:
        problems.append(f"Data is drawn over {covered[0]!r} — he stands in front "
                        f"of text drawn before him; draw the text after him or "
                        f"keep him clear of it")
    if on_data:
        problems.append(f"prints {on_data[0]!r} over Data — a label drawn on top "
                        f"of him hides him and neither reads; put it where he "
                        f"is not")
    if crowded:
        u_, hs = crowded[0]
        problems.append(f"shows {len(hs)} big numbers at once at u={u_:.2f} "
                        f"({', '.join(map(repr, hs))}) — a viewer glances, they "
                        f"do not read a table; at most {MAX_HEADLINES} big "
                        f"numbers on screen, and let the PICTURE carry the rest")
    if overlaps:
        a_, b_ = overlaps[0]
        problems.append(f"prints {b_!r} over {a_!r} — two pieces of text overlap "
                        f"in one frame and neither can be read")
    if low:
        problems.append(f"prints {low[0][0]!r} at y={low[0][1]:.0f}, in the caption "
                        f"band (below y={CAPTION_Y}) where the narration burns in")
    if any(fy > CAPTION_Y for _, _, fy, _ in hosts):
        problems.append(f"Data stands in the caption band (feet below "
                        f"y={CAPTION_Y}), where the narration burns in")
    for role, x, fy, h in hosts:
        if role not in ROLES:
            problems.append(f"unknown role {role!r}")
        if not (0 < x < SS.W and 0 < fy < SS.H and h >= 150):
            problems.append(f"Data placed off-frame or too small: {(x, fy, h)}")
            break
    a = np.ndarray((SS.H, SS.W, 4), np.uint8, surf.get_data())
    if int((a[..., 3] < 255).sum()):
        problems.append("not full-bleed: transparent pixels")
    allowed = _allowed_numbers(pts)
    allowed |= {float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*\.?\d*", say or "")}
    vmax = max((abs(v) for _, v in pts), default=100.0)
    said = {(float(t.replace(",", "")), u) for t, u in _units(say)}
    for s in dict.fromkeys(seen):
        for tok0, unit in _units(s):
            tok = _Tok(tok0)
            tok.unit = unit
            if not _num_ok(tok, allowed, vmax):
                problems.append(f"prints {s!r}, a number the data does not have")
                break
            clash = _contradicts(tok, said, [v for _, v in pts], vmax)
            if clash is not None:
                problems.append(f"prints {s!r} where the narration says {clash:,g} "
                                f"— print the narration's number")
                break
    texts.clear()
    try:
        run(list(reversed(pts)), 1.0)
    except Exception as e:  # noqa: BLE001
        return problems + [f"crashed on reversed data: {e}{crash_at(fn, e)}"]
    if sorted(t for t in final if re.search(r"\d", t)) != \
            sorted(t for t in texts if re.search(r"\d", t)):
        problems.append("the numbers change when the data's order changes")
    problems += motion_problems(fn, pts, secs)
    return problems


# ------------------------------------------------------------------ the ask

_PROMPT = """You are drawing ONE beat of a vertical (1080x1920) YouTube Short about \
data, in the style of the operator's reference animation. Write a single Python \
function:

    def scene(cr, t, u, pts, host):

cr is a pycairo Context for the whole frame; t is seconds since the beat began; \
u is the beat's progress 0..1; pts is the beat's sourced data as [(label, value)]; \
host(role, x, foot_y, height, pace=False, beat=0) draws the mascot Data standing \
with his feet at (x, foot_y). role is a STANCE — {stances} — or a TOOL ACT:
{tools}
An act plays ONCE (wind up, do it, hold) when the role changes; pass beat=k \
and advance k each time the thing changes, and it plays again — one swing of \
the pick per crack.

THE RULES — every one is checked by code before your scene is used:
1. The frame IS THE SUBJECT, never a chart. Draw the thing the story is about \
(the forest, the street, the scale, the ocean), and make the number a physical \
act made of it (trees falling one per 1,000 km², coins piling on a scale). No \
bars, axes, pie charts, bubble charts, or grids of one repeated icon. A kit \
object is for ITS subject only: when the kit has no kelp, urchin or reactor, \
draw one from paths — never stand a land tree in for kelp.
2. Every number you print comes from pts, or is arithmetic on it (a \
difference, a share, a ratio). Never invent a quantity. Sort time data with \
by_time(rows) — never trust list order.
3. Fill the whole frame every frame: start with a full-height background \
(vgrad over 0..H or a kit backdrop). Captions are burned from y=1540 down: \
keep Data's feet and every number above it, readouts between y=470 and y=1500 (the big readout: fit_readout(cr, big, small, \
80, 520, ...)).
4. Data ACTS inside the scene, tied to the number — he rides it, pours it, \
climbs it, carries it. Give him a BIT: a setup, an action, a reaction — at \
least two different roles over the beat — and his spot follows what he is \
doing (at least 150px of travel, not counting pace). He PERFORMS for at \
least half the beat — roles strain, climb or hold_up, doing something to \
the thing the number is made of; point, cheer, shock and think are only \
the setup and the reaction. A Data who waves beside the data is marked \
down every time. Call host(...) every \
frame, height 180-240.
5. DECISIVE motion, not constant motion. The story moves when the story \
moves: the subject changes, arrives, falls, fills — then HOLDS a beat so it \
can be read — then the next thing happens. Holds of up to ~1.5s are good; \
nothing may freeze longer than that, and the scene must not be mostly \
still: BUDGET IT so something of the subject is moving at least 60% of \
the beat — each change takes longer than the hold after it, and the first \
change starts within the first second. HOW IT IS MEASURED: the frame is \
cut into a 12x12 grid (cells ~90x160px) and a frame counts as moving only \
when some cell's average grey level changes by 6+ from the frame before — \
so a big, contrasty thing travelling several px a frame counts, and a \
small, pale or slow one does not. Keep speeds calm enough to follow (things crossing the frame take \
a second or more; nothing flickers back and forth). NEVER draw a particle \
overlay — no snow, dust, motes, sparkles, bokeh or rain drifting across the \
frame: it reads as a glitch on every second of the video. Data stands where \
you put him and moves when you move him — his acts play once when his role \
changes, then he holds; don't jiggle him.
7. The object the number is ABOUT is the HERO of the frame: big (a third of \
the frame or more), centred in the upper-middle, the first thing the eye \
lands on. If the idea is a vape cloud turning into a nicotine pouch, that \
cloud and that pouch fill the frame — Data and the setting support it, \
they never shrink it into a corner.
8. RECOGNISABLE AT A GLANCE. The hero must read as itself to someone who \
has not been told — by its SIGNATURE SILHOUETTE and its tells (a casket: \
the six-sided taper, the lid seam, the handles, the flowers on it; a \
lantern: the ring, the panes, the flame) — drawn whole BEFORE the data's \
effect touches it, and still readable through the effect (a burning \
casket is still casket-shaped). A plain box with plank lines was "a \
coffin I couldn't tell was a coffin until I watched it more than once".
9. THE SUBSTANCE IS THE SUBJECT'S OWN MATERIAL. What rises, piles, pours \
or burns is the thing the number is made of, in that thing's own colour \
and form: ash is grey dust, fire is flame, water is blue, coins are gold. \
The accent marks the SHARE; it never recolours the stuff — a blue "ash" \
in a glass is water, and a cremation share that fills as water was "out \
of place — it should have been a crematorium or fire that Data throws \
fuel on". When the subject has a fire, the share GROWS AS FIRE he feeds.
10. THE CAUSE IS REAL PHYSICS. Data's act is the act that would actually \
produce the change: pouring fills, hauling a rope lifts a SOLID, a bellows \
fans a flame, feeding grows a fire. A rope that raises a liquid "makes no \
sense". If a viewer could not predict the result from the act, pick \
another act.
11. PURPOSEFUL MOVEMENT, NEVER FLAILING. Work is done WITH THE TOOL the job \
needs, and the tool's business end lands on the thing: breaking ice is \
swing_pick with the pick on the ice, felling is chop into the trunk, a hole \
is dig, a fire is pump at its base, a pile moved is broom. `strain` is for \
BEARING a load (a wall, a weight), never for doing work — "he is breaking \
the iceberg and he is just flailing his arms around" is what strain looks \
like on a job. Your CAUSE line names the verb; the verifier knows which \
tool that verb takes and refuses a scene that does the work empty-handed. \
Time the change to the strike: the crack appears on the beat the pick \
lands, not while he winds up.
12. THE ART IS LIT, NOT FLAT. One key light from the upper-left (KEY). \
Nothing solid is a flat fill: draw its path, then solid(cr, rgb) — lit face \
falling to shadow face, a rim on the lit edge, an ink edge — with a finish \
when the material has one (gloss, metal, glass, ice). Boxes are box(), \
round things disc() and cylinder(). Everything that stands on the ground \
stands on a contact_shadow() drawn first. Far things go under haze(); \
vignette() last, before the text. Build the hero from several lit pieces \
(a scale is a post, a beam, two pans, chains — each shaded), not one \
silhouette. A frame whose hero band holds more than {flat_max} of large exact \
flat colour is MEASURED and refused as clip art — a gold pile of identical flat ellipses, \
two flat pans and a flat box were the look this rule replaces.
13. IT IS A SHOT, NOT A DIAGRAM. A front-on elevation of the hero over an \
empty field was "still very much lacking"; the same beat as a shot was "ok \
now we are talking". So: start from a SETTING — landscape(cr, t, kind) for \
anything outdoors (or a kit interior like cafe()) — never a bare gradient. \
Show the hero in THREE-QUARTER view with a side going back into the \
picture (building() for anything built; box() and cylinder() already turn), \
throwing a long cast_shadow() to the lower right, away from the sun. Give \
the frame three depths: the far setting under haze, the hero in the \
middle, and something of the subject RIGHT BY THE CAMERA in the bottom \
third (hens in the yard, a sack in the foreground, a rock), then \
foreground(cr, kind) before vignette(). THE SHOT below is the bar.
14. THE SCALE IS IN THE PICTURE, read at a glance. Never a chart, key or \
legend laid over the scene — "freaking boxes on top of the video doesn't \
help ... it just needs to be able to more easily glance at it and gauge \
the scale". Show the comparison ON the subject: the earlier size as a \
ghost() outline where it stood, a then_mark() where the old level reached \
with its year on it, times_ticks() up the side when it is a multiple, or \
something everyone knows the size of next to it (Data, a person, a car). \
With the sound off, one look must say "about three times as much".
15. ONE NUMBER, AND THE CHANGE IS BIG ON SCREEN. The operator liked a \
pile of plastic that grew to three times its size under one number; he \
did not like a bone standing still in a window with -1.5%, 1% and 1.5x \
stacked beside it. At most {max_heads} big numbers in any frame — MEASURED \
— and never a label on top of Data. What moves must be the biggest thing \
in the frame and change shape you can see from across a room. A small \
percentage drawn literally (a bone 1.5% thinner) is invisible: draw what \
piles up, empties or spreads until it is large, or set the thing beside \
what it equals, so the PICTURE makes the comparison and the words do not.
16. LAND IT, THEN HOLD IT. A scene is on screen for about {secs:.0f} seconds, and the owner called a fence whose last number arrived with under a second left "whiplash — I didn't even have time to process". Finish the story — every number, the final size, the last label — by u={payoff_by}, then HOLD that finished picture to the end so it can be read. After it lands the WORLD keeps moving (wind, a bottle rolling) and Data KEEPS DOING HIS ACT to the end (another toss, holding the load up, one more shove) — he never stands and points at what he made; the story does not move. A readout steps through at most {shows} values (landed(rows, k, f) does this). MEASURED: a number still arriving after u={payoff_by} is refused.
Open the docstring of scene() with three lines, exactly this shape — a \
viewer who sees two of your frames with every word and Data removed will \
be asked whether they agree with each one, and the scene is refused if \
they do not:
    HERO: <the object the number is about, 2-5 words>
    SUBSTANCE: <the material that moves, 1-4 words>
    CAUSE: <what Data does that makes it move, one line>
HOW TO SHOW A SHARE (the showrunner's most repeated note on this look): a \
percentage is ONE WHOLE, split. Draw the whole once — one field, one ship's \
cargo, one crowd, one plate — and cut it at the true proportion, both parts \
visible at their real sizes, the share in the accent and the rest in a \
neutral. Never two separate objects with labels doing the arithmetic ("the \
80/20 split relies on labels", "the 20% remainder is a tiny truck at the \
right edge", "flying cards do not show the 33% or 25% share").
6. No imports; use only these names: {kit}, math, cairo, look, fit_size, \
INK, INK_2, WARN, and these builtins: {builtins}. _c(rgb, alpha) makes a cairo colour. Colours: tuples (r, g, b) 0..255, or P[...] palette keys: \
{palette}.

THE KIT (signatures):
{sigs}

THE SHOT — the look every scene is held to (this exact code passes every check):
{shot}

THE PILE — drawn by a brain like you from this kit, and the scene the owner \
picked over another that passed every check ("I like the pile one but the \
bone one no"): one number, a heap that triples, its old size on it:
{pile}

TWO TEACHER SCENES that pass every check — match this quality and style:
{teachers}

{brief}THIS BEAT:
story title: {title}
beat topic: {topic}
narration: {say}
data pts: {pts}
unit: {unit}

Return ONLY the Python code of `def scene(...)` (helper defs above it are \
fine), no prose, no fences."""


def _sigs():
    out = []
    for n in KIT_NAMES:
        obj = getattr(SS, n)
        if callable(obj):
            try:
                line = f"  {n}{inspect.signature(obj)}"
                # WHAT IT RETURNS. A bare signature let the brain guess, and
                # it guessed `w, h = text(...)` — text() returns its
                # (x0, y0, x1, y1) box — so the commonest first draft
                # crashed on an unpack (2026-10-04..06). The docstring's
                # first sentence states the contract.
                doc = (inspect.getdoc(obj) or "").strip().split("\n\n")[0]
                doc = " ".join(doc.split())
                if doc:
                    line += f"  # {doc[:160]}"
                out.append(line)
            except (TypeError, ValueError):
                pass
    return "\n".join(out)


CLOSING_BRIEF = """THIS IS THE CLOSING, not a beat. It lands the story's last \
line as ONE picture made of the subject: "{closing}". Show that line \
HAPPENING — both halves of it if it has two — in the world the story opened \
in, using the numbers in pts: they are what the story BUILT TO, its last \
finding. Never restate the hook's contrast; the viewer has seen it. Keep y \
140..480 free of any text: the closing line is drawn there over your sky. \
Data's act is the payoff, and it fits the news — a reaction to a loss, \
never a celebration of it.

"""

REPAIR_BRIEF = """THE SHOWRUNNER WATCHED THE CURRENT VERSION OF THIS SCENE AND \
SAID:
{critique}

Redraw it to fix exactly that, and keep what it did not complain about. The \
current code:
{prior}

"""


def build_prompt(title, topic, say, pts, unit, brief="", secs=None):
    teachers = "\n\n".join(inspect.getsource(f) for f in
                           (SS.amazon_where_it_goes, SS.coffee_drought))
    tools = "\n".join(f"  {k}: {v}" for k, v in TOOL_ACTS.items())
    return _PROMPT.format(stances=", ".join(STANCES), tools=tools,
                          flat_max=f"{FLAT_MAX:.0%}", max_heads=MAX_HEADLINES,
                          secs=SCENE_SECS["beat"] if secs is None else secs,
                          payoff_by=f"{land_by(secs):.2f}",
                          shows=SS.READOUT_SHOWS,
                          kit=", ".join(KIT_NAMES),
                          builtins=", ".join(sorted(SAFE_BUILTINS)),
                          palette=", ".join(sorted(SS.P)), sigs=_sigs(),
                          shot=inspect.getsource(SS.bird_flu_barn),
                          pile=inspect.getsource(SS.recycling_pile),
                          teachers=teachers, title=title, topic=topic, say=say,
                          pts=json.dumps(pts), unit=unit, brief=brief)


def _strip_fence(s: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", s, re.S)
    return m.group(1) if m else s


def ask_brain(prompt: str, model: str | None = None,
              timeout: float | None = None, images: bool = False) -> str | None:
    """The drawing brain's code for `prompt`. `images`: the prompt names
    image files it must READ (the look-again round), so it may use Read."""
    if not shutil.which("claude"):
        return None
    # The drawing IS the video: the strongest model draws it (the judge that
    # grades it is opus too).
    model = model or os.environ.get("SCENE_AUTHOR_MODEL",
                                    os.environ.get("SHOWRUNNER_MODEL", "opus"))
    try:
        proc = subprocess.run(["claude", "-p", prompt, "--model", model,
                               *(["--allowedTools", "Read"] if images else []),
                               "--output-format", "text"],
                              capture_output=True, text=True,
                              timeout=timeout or TIMEOUT_S)
    except Exception:  # noqa: BLE001
        return None
    return _strip_fence(proc.stdout or "") if proc.returncode == 0 else None


def author(title, topic, say, pts, unit="", attempts=3, log=print, brief="",
           secs: float | None = None):
    """(scene_fn, code) for a verified brain-drawn scene, or (None, reason).
    `brief` adds the job on top of the rules: a closing, or a repair."""
    if os.environ.get("SCENE_AUTHOR", "on").lower() in ("0", "off", "false"):
        return None, "SCENE_AUTHOR=off"
    prompt = build_prompt(title, topic, say, pts, unit, brief, secs)
    why = "no brain"
    for k in range(attempts):
        if _remaining() < 90:
            return None, "this video's drawing budget is spent"
        code = ask_brain(prompt, timeout=min(TIMEOUT_S, _remaining()))
        if not code:
            return None, why
        try:
            fn = compile_scene(code)
            problems = verify(fn, pts, say, secs)
            if not problems:
                # the code agrees; now a VIEWER has to (hero, substance, cause)
                problems = glance(fn, pts, log=log)
        except Exception as e:  # noqa: BLE001 — refused or broken: tell it why
            problems = [f"{type(e).__name__}: {str(e)[:200]}"]
        if not problems:
            return look_again(fn, code, prompt, pts, say, secs, log=log) or (fn, code)
        why = "; ".join(problems[:4])
        log(f"[scene_author] attempt {k + 1} refused: {why}")
        prompt += ("\n\nYOUR PREVIOUS SCENE FAILED THESE CHECKS — fix every "
                   "one:\n- " + "\n- ".join(problems[:6]) + "\n\nPREVIOUS CODE:\n" + code)
    return None, why


# ----------------------------------------------------------- look again ----
# Operator, 2026-10-07: "I like the pile one but the bone one no." Both had
# passed every check; the bone was a femur built of circles and rectangles,
# small, in a bare room. The brain that DRAWS had never seen either one: it
# wrote code, the code was measured, a separate viewer named the object.
# So a scene that passes gets ONE more round: the brain READS its own frames
# as they will be seen (words, Data and all) beside THE SHOT, and redraws
# what looks cheap. The redraw goes through every same check; if it fails
# any, the scene that passed is kept. A look again can only replace a
# passing scene with another passing scene.

LOOK_AGAIN_AT = (0.3, 0.85)
LOOK_AGAIN_TRIES = 2
LOOK_AGAIN_MIN_S = 300            # budget a redraw needs, or it is skipped
LOOK_SIZE = (540, 960)
#: THE SHOT is drawn with stand-in rows: it is shown for its art, not its data.
SHOT_ROWS = [["2021", 2.0], ["2022", 6.0], ["2023", 11.0], ["2024", 19.0]]
PILE_ROWS = [["2019", 353.0], ["2060 (projected)", 1014.0]]

_LOOK_AGAIN = """

YOUR SCENE PASSED EVERY CHECK. Now LOOK at it, the way the channel owner \
will. READ these image files with the Read tool — your scene as a viewer \
sees it:
{yours}
and the two frames the owner loved — THE SHOT (the barn) and THE PILE \
(plastic, drawn by a brain like you from this same kit):
{shot}

Two scenes that passed every check went to the owner together: a pile of \
plastic in a field that grew to three times its size under one number, and \
a thigh bone built of circles and rectangles, small, in a bare room, with \
three numbers beside it. His words: "I like the pile one but the bone one \
no." Find the three things in YOUR frames that look most amateur beside \
THE SHOT and THE PILE — a hero assembled from primitive shapes, a hero too small to \
read, an empty backdrop, crowded or tiny text, a change you cannot see, \
Data lost or covered — and fix them. Keep the idea, the data, the numbers \
and the HERO / SUBSTANCE / CAUSE declaration; redraw what looks cheap.

YOUR CODE:
{code}

Return the WHOLE improved scene code, nothing else."""


def seen_frames(fn, pts, out_dir, at=LOOK_AGAIN_AT, size=LOOK_SIZE) -> list[str]:
    """`fn` rendered as it ships — words, Data, finish — at each `at`, to PNGs."""
    import cairo
    from PIL import Image
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    clock, paths = {}, []
    for u in at:
        f = int(round(u * 299))
        cr = cairo.Context(surf)

        def host(role, x, fy, h, pace=False, beat=0, _cr=cr, _f=f):
            SS.place_host(_cr, role, SS.act_phase(clock, (role, int(beat)), _f),
                          None, x, fy, h, _f / 30.0, pace)
        with SS.I.text_layer(cr):
            fn(cr, f / 30.0, u, pts, host)
            SS.I.finish(cr, SS.I.FINISH)
        surf.flush()
        p = out_dir / f"{getattr(fn, '__name__', 'scene')}_u{int(u * 100):02d}.png"
        surf.write_to_png(str(p))
        Image.open(p).resize(size, Image.LANCZOS).save(p)
        paths.append(str(p))
    return paths


def look_again(fn, code, prompt, pts, say="", secs=None, log=print):
    """(fn, code) of the brain's redraw of a PASSING scene after it has seen
    its own frames beside THE SHOT and THE PILE, or None — no budget, no
    brain, or every redraw failed a check — in which case the passing scene
    stands. A redraw that fails is told why and may try again, up to
    LOOK_AGAIN_TRIES, while the budget lasts."""
    if _remaining() < LOOK_AGAIN_MIN_S:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="look_again_") as td:
            yours = seen_frames(fn, pts, Path(td) / "yours")
            shot = seen_frames(SS.bird_flu_barn, SHOT_ROWS, Path(td) / "shot",
                               at=(0.85,))
            shot += seen_frames(SS.recycling_pile, PILE_ROWS, Path(td) / "pile",
                                at=(0.95,))
            ask = prompt + _LOOK_AGAIN.format(
                yours="\n".join(f"- {p}" for p in yours),
                shot="\n".join(f"- {p}" for p in shot), code=code)
            for k in range(LOOK_AGAIN_TRIES):
                if k and _remaining() < LOOK_AGAIN_MIN_S:
                    break
                code2 = ask_brain(ask, timeout=min(TIMEOUT_S, _remaining()),
                                  images=True)
                if not code2 or code2.strip() == code.strip():
                    return None
                try:
                    fn2 = compile_scene(code2)
                    problems = verify(fn2, pts, say, secs) or glance(fn2, pts, log=log)
                except Exception as e:  # noqa: BLE001
                    problems = [f"{type(e).__name__}: {str(e)[:200]}"]
                if not problems:
                    log("[scene_author] look-again redraw passed and replaces "
                        "the first draft")
                    return fn2, code2
                log(f"[scene_author] look-again redraw {k + 1} refused: "
                    f"{'; '.join(problems[:2])}")
                ask += ("\n\nYOUR REDRAW FAILED THESE CHECKS — keep what you "
                        "improved and fix every one:\n- "
                        + "\n- ".join(problems[:6]) + "\n\nYOUR REDRAW:\n" + code2)
    except Exception as e:  # noqa: BLE001 — a look that cannot happen keeps the pass
        log(f"[scene_author] look again skipped: {type(e).__name__}: {e}")
        return None
    log("[scene_author] no redraw passed; keeping the scene that did")
    return None


def scene_for_segment(story_cfg: dict, index: int, insight, log=print):
    """The brain's scene for beat `index` of this story: the verified one
    already saved on the segment (re-checked through the sandbox), else a
    freshly authored and verified one — which is written onto the segment
    as `illustrated_scene` for the renderer to persist. None when there is
    no brain or nothing it drew passed."""
    segs = story_cfg.get("segments") or []
    if not 0 <= index < len(segs):
        return None
    seg = segs[index]
    # The saved scene goes through the SAME load check as everywhere else —
    # compile AND craft. This used to compile only, so a flat scene from
    # before the light (2026-10-05) that `saved_scene` had just refused
    # came straight back through here and shipped flat anyway.
    fn = saved_scene(seg, log=log)
    if fn is not None:
        return fn
    pts = [[str(getattr(p, "label", "")), float(getattr(p, "value", 0) or 0)]
           for p in (getattr(insight, "items", None) or [])]
    if not pts:
        return None
    fn, got = author(story_cfg.get("title", ""), seg.get("topic", ""),
                     seg.get("say", ""), pts, str(getattr(insight, "unit", "") or ""),
                     log=log, brief=siblings(story_cfg, index))
    if fn is None:
        log(f"[scene_author] no verified scene for beat {index}: {got}")
        return None
    seg["illustrated_scene"] = got
    return fn


def _about(code_or_fn) -> str:
    """What a scene draws, in a line or two: its docstring, else its head."""
    try:
        src = code_or_fn if isinstance(code_or_fn, str) else inspect.getsource(code_or_fn)
        tree = ast.parse(src)
        fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        doc = ast.get_docstring(fns[-1]) if fns else None
        doc = _DECL.sub("", doc) if doc else doc     # the prose, not the labels
        return " ".join((doc or src[:300]).split())[:400]
    except Exception:  # noqa: BLE001
        return "(unreadable)"


def siblings(story_cfg: dict, exclude) -> str:
    """The OTHER scenes of this video, for the brain to NOT repeat. The
    coffee video re-ran one balance machine in two beats and the judge
    marked it down; a brain drawing one beat could not know what the others
    were."""
    slug = story_cfg.get("slug", "")
    rows = []
    for kind in ("hook", "closing"):
        if kind == exclude:
            continue
        code = story_cfg.get(f"{kind}_scene")
        fn = ((SS.hook_for if kind == "hook" else SS.closing_for)(slug) or (None,))[0]
        if code or fn:
            rows.append(f"- the {kind}: {_about(code or fn)}")
    for i, g in enumerate(story_cfg.get("segments") or []):
        if i == exclude:
            continue
        code = g.get("illustrated_scene")
        fn = SS.scene_for(slug, i)
        if code or fn:
            rows.append(f"- beat {i}: {_about(code or fn)}")
    if not rows:
        return ""
    return ("OTHER SCENES IN THIS VIDEO — yours must be a DIFFERENT picture: "
            "different objects, a different setting or angle, a different act "
            "for Data. Never re-run one of these:\n" + "\n".join(rows) + "\n\n")


def _pts(insight):
    return [[str(getattr(p, "label", "")), float(getattr(p, "value", 0) or 0)]
            for p in (getattr(insight, "items", None) or [])]


def _story_say(story_cfg: dict) -> str:
    """Every number the story's narration states, for the closing's check."""
    return " ".join([story_cfg.get("hook") or "", story_cfg.get("closing") or ""]
                    + [g.get("say") or "" for g in story_cfg.get("segments") or []])


def saved_scene(seg_cfg: dict, log=print):
    """The verified scene saved on a segment, re-checked through the
    sandbox, or None."""
    code = (seg_cfg or {}).get("illustrated_scene")
    if isinstance(code, str) and code.strip():
        try:
            fn = compile_scene(code)
        except Exception as e:  # noqa: BLE001 — a stale/edited scene is re-authored
            log(f"[scene_author] saved scene refused ({e})")
            return None
        # A scene saved before the light (2026-10-05) is flat clip art; it is
        # redrawn under the new rules rather than shipped again.
        probs = _saved_craft(fn, seg_cfg, log, SCENE_SECS["beat"])
        if probs:
            log(f"[scene_author] saved scene refused — {probs[0][:90]}")
            return None
        return fn
    return None


def _saved_craft(fn, seg_cfg, log, secs: float | None = None) -> list[str]:
    try:
        from shared import rewrite_mailbox as _rw
        d = _rw._dataset(seg_cfg or {}) or {}
        pts = [(str(p["label"]), float(p["value"])) for p in d.get("points") or []
               if p.get("value") is not None]
        if not pts:
            return []
        # And one saved before the payoff rule (2026-10-07) that lands its
        # last number with under a second left is redrawn, not replayed:
        # the bird flu fence's ending did exactly that.
        return craft_problems(fn, pts) + payoff_problems(fn, pts, secs)
    except Exception as e:  # noqa: BLE001 — cannot judge it: keep it
        log(f"[scene_author] saved scene craft check skipped ({e})")
        return []


HOOK_BRIEF = """THIS IS THE HOOK — the first ~3 seconds, before the story \
starts. Frame 1 must already state the story's surprise as ONE picture made \
of the subject: "{hook}". Open mid-action — the thing is already happening \
in the very first frame; no build-up, no title card. u runs 0..1 over those \
~3 seconds, so move FAST. The hook line is captioned below y=1650. It must \
not be the picture the first beat will show — it is the teaser for the \
whole story, the contrast at its heart.

"""

BRIEFS = {"hook": HOOK_BRIEF, "closing": CLOSING_BRIEF}
#: How long each kind of scene is REALLY on screen, for the dwell and payoff
#: checks. These were 3 / 10 / 6 until 2026-10-07, when the posted log said
#: otherwise: since the 8-second beat (pacing, 2026-10-05) the median hook
#: ran 4.4s, beat 6.0s and closing 4.6s (shortest 4.0s). A check that thinks
#: a beat is 10 seconds passed a payoff held for 0.8 of a real second.
SCENE_SECS = {"hook": 4.0, "closing": 4.0, "beat": 6.0}


def saved_bookend(story_cfg: dict, kind: str, n_beats: int, log=print):
    """(scene, beat index) for the story's saved `kind` scene ("hook" or
    "closing"), re-checked through the sandbox, or None."""
    code = story_cfg.get(f"{kind}_scene")
    idx = story_cfg.get(f"{kind}_data", 0)
    if isinstance(code, str) and code.strip() and isinstance(idx, int) \
            and 0 <= idx < n_beats:
        try:
            fn = compile_scene(code)
        except Exception as e:  # noqa: BLE001
            log(f"[scene_author] saved {kind} refused ({e})")
            return None
        segs = story_cfg.get("segments") or []
        probs = _saved_craft(fn, segs[idx] if idx < len(segs) else {}, log,
                             SCENE_SECS.get(kind, SCENE_SECS["beat"]))
        if probs:
            log(f"[scene_author] saved {kind} refused — {probs[0][:90]}")
            return None
        return fn, idx
    return None


def saved_closing(story_cfg: dict, n_beats: int, log=print):
    return saved_bookend(story_cfg, "closing", n_beats, log)


def _brief(kind: str, story_cfg: dict) -> str:
    line = (story_cfg.get(kind) or "").strip()
    return BRIEFS[kind].format(hook=line, closing=line)


def scene_for_bookend(story_cfg: dict, kind: str, insights: list, log=print):
    """(scene, beat index whose data it draws) for the story's HOOK or
    CLOSING: the verified one saved on the story, else a freshly authored
    one saved as `<kind>_scene` + `<kind>_data`. None when nothing passed —
    the renderer then does what it did before."""
    saved = saved_bookend(story_cfg, kind, len(insights), log=log)
    if saved is not None:
        return saved
    line = (story_cfg.get(kind) or "").strip()
    if not line:
        return None
    # The HOOK draws the opening beat's data: it teases where the story
    # goes. The CLOSING draws the LAST beat's: it lands what the story built
    # to. Both used to take the first beat, so the payoff restated the
    # hook — "the closing reuses the 2004/2024 figures from the hook ... a
    # soft payoff" (amazon-still-shrinking, 2026-09-24) while "the 750k-km²
    # France reveal in seg2 is the stronger punchline". A beat with no data
    # is skipped.
    order = (range(len(insights) - 1, -1, -1) if kind == "closing"
             else range(len(insights)))
    for idx in order:
        ins = insights[idx]
        pts = _pts(ins)
        if pts:
            break
    else:
        return None
    fn, got = author(story_cfg.get("title", ""), f"the {kind}: " + line,
                     _story_say(story_cfg), pts,
                     str(getattr(insights[idx], "unit", "") or ""), log=log,
                     brief=_brief(kind, story_cfg) + siblings(story_cfg, kind),
                     secs=SCENE_SECS[kind])
    if fn is None:
        log(f"[scene_author] no verified {kind}: {got}")
        return None
    story_cfg[f"{kind}_scene"], story_cfg[f"{kind}_data"] = got, idx
    return fn, idx


def scene_for_closing(story_cfg: dict, insights: list, log=print):
    return scene_for_bookend(story_cfg, "closing", insights, log)


def redraw(story_cfg: dict, index, insight, prior_code: str, critique: str,
           log=print):
    """A REPAIR: the brain redraws beat `index` (or "hook"/"closing") given what the
    showrunner said about it and the code that drew it. Verified exactly like
    a first draft. Returns (scene, code) or (None, reason); nothing is saved
    here — the caller keeps it only if the re-judged video scores higher."""
    segs = story_cfg.get("segments") or []
    if index in BRIEFS:
        topic = f"the {index}: " + (story_cfg.get(index) or "")
        say = _story_say(story_cfg)
    else:
        topic = segs[index].get("topic", "")
        say = segs[index].get("say", "")
    brief = REPAIR_BRIEF.format(critique=critique, prior=prior_code) \
        + siblings(story_cfg, index)
    if index in BRIEFS:
        brief = _brief(index, story_cfg) + brief
    return author(story_cfg.get("title", ""), topic, say, _pts(insight),
                  str(getattr(insight, "unit", "") or ""), log=log, brief=brief,
                  secs=SCENE_SECS.get(index, SCENE_SECS["beat"]))
