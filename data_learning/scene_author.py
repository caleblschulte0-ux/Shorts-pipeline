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
             "heat_shimmer", "shape_path", "stride", "walk", "step_through", "landed", "STEP_BOB", "PACE_PERIOD", "EDGE", "clamp", "ease", "pop",
             "seg", "W", "H", "P", "_c", "scar_path", "SCAR", "FOREST_Y",
             "STREET_Y", "_TREES", "forest_floor", "FRANCE")
SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict)
                 else getattr(__builtins__, n)
                 for n in ("range", "len", "min", "max", "abs", "int", "float",
                           "str", "round", "enumerate", "zip", "sorted", "sum",
                           "list", "dict", "tuple", "isinstance", "reversed",
                           "any", "all", "bool", "divmod", "pow", "next",
                           "iter", "map", "filter", "set", "frozenset", "format",
                           "ValueError", "IndexError", "KeyError",
                           "ZeroDivisionError", "Exception")}
ROLES = ("point", "cheer", "strain", "climb", "shock", "think", "hold_up")


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
    return fn


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
           lambda role, x, fy, h, pace=False, _cr=cr, _f=f, _t=t: SS.place_host(
               _cr, role, SS.act_phase(clock, role, _f), None, x, fy, h, _t, pace))
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
    return {"judder": sr.judder_pairs(diffs) / pairs,
            "max_hold_s": max(_runs(still), default=0) / float(fps),
            "still": sum(still) / pairs}


def motion_problems(fn, pts, secs: float = 10.0) -> list[str]:
    m = motion_profile(fn, pts, secs=secs)
    out = []
    if m["judder"] > MAX_JUDDER:
        out.append(f"it judders: {m['judder']:.0%} of frames are 1-3-frame stalls "
                   f"between moves (allowed {MAX_JUDDER:.0%}) — move smoothly or hold")
    if m["max_hold_s"] > MAX_HOLD_S:
        out.append(f"it freezes for {m['max_hold_s']:.1f}s (allowed {MAX_HOLD_S}s) — "
                   f"a hold is fine, a frozen stretch is not")
    if m["still"] > MAX_STILL:
        out.append(f"it is still {m['still']:.0%} of the time (allowed "
                   f"{MAX_STILL:.0%}) — the story has to keep arriving")
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
ACT_ROLES = ("strain", "climb", "hold_up")
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
           lambda role, x, fy, h, pace=False: calls.append((role, x, fy)))
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


#: A number has to stay up long enough to READ. Brain hooks cycled a value
#: every few frames and the judge wrote "a hook number that flickers too fast
#: to register" (Amazon, 2026-09-23).
MIN_DWELL_S = 0.7


def verify(fn, pts, say: str = "", secs: float = 10.0) -> list[str]:
    """Every check a teacher scene passes. Empty list = usable. `say` is the
    beat's narration: a number the story itself states ("the 1930s") may be
    printed; the editorial gate has already held the narration to the data."""
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
        return box

    def run(rows, u, record=True):
        boxes.clear()
        cr = cairo.Context(surf)
        # Spy on the kit too: a number printed through fit_readout or any
        # other helper is still a number on screen.
        fn.__globals__["text"] = spy
        SS.text = spy
        fn.__globals__["fit_readout"] = ro_spy
        def host(role, x, fy, h, pace=False):
            hosts.append((role, x, fy, h))
            # Where Data can be while he performs: his body, widened by his
            # walk and lifted by his step when he paces.
            reach = SS.PACE_AMP if pace else 20.0
            body = (x - 0.3 * h - reach, fy - h - (SS.STEP_BOB if pace else 20.0),
                    x + 0.3 * h + reach, fy)
            for t_, b_ in boxes:              # text drawn BEFORE him, under him
                if _covered(b_, body) > 0.25:
                    covered.append(t_)
        try:
            fn(cr, 3.0 + u * 10, u, rows, host)
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
        return [f"crashed: {type(e).__name__}: {str(e)[:160]}"]
    if len(hosts) < 11:
        problems.append("Data is missing from a frame (host not called)")
    problems += bit_problems(fn, pts)
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
        return problems + [f"crashed on reversed data: {e}"]
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
host(role, x, foot_y, height, pace=False) draws the mascot Data standing with his \
feet at (x, foot_y). role is one of {roles}.

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
still. Keep speeds calm enough to follow (things crossing the frame take \
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
6. No imports; use only these names: {kit}, math, cairo, look, fit_size, \
INK, INK_2, WARN, and these builtins: {builtins}. _c(rgb, alpha) makes a cairo colour. Colours: tuples (r, g, b) 0..255, or P[...] palette keys: \
{palette}.

THE KIT (signatures):
{sigs}

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
                out.append(f"  {n}{inspect.signature(obj)}")
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


def build_prompt(title, topic, say, pts, unit, brief=""):
    teachers = "\n\n".join(inspect.getsource(f) for f in
                           (SS.amazon_where_it_goes, SS.coffee_drought))
    return _PROMPT.format(roles=", ".join(ROLES), kit=", ".join(KIT_NAMES),
                          builtins=", ".join(sorted(SAFE_BUILTINS)),
                          palette=", ".join(sorted(SS.P)), sigs=_sigs(),
                          teachers=teachers, title=title, topic=topic, say=say,
                          pts=json.dumps(pts), unit=unit, brief=brief)


def _strip_fence(s: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", s, re.S)
    return m.group(1) if m else s


def ask_brain(prompt: str, model: str | None = None,
              timeout: float | None = None) -> str | None:
    if not shutil.which("claude"):
        return None
    # The drawing IS the video: the strongest model draws it (the judge that
    # grades it is opus too).
    model = model or os.environ.get("SCENE_AUTHOR_MODEL",
                                    os.environ.get("SHOWRUNNER_MODEL", "opus"))
    try:
        proc = subprocess.run(["claude", "-p", prompt, "--model", model,
                               "--output-format", "text"],
                              capture_output=True, text=True,
                              timeout=timeout or TIMEOUT_S)
    except Exception:  # noqa: BLE001
        return None
    return _strip_fence(proc.stdout or "") if proc.returncode == 0 else None


def author(title, topic, say, pts, unit="", attempts=3, log=print, brief="",
           secs: float = 10.0):
    """(scene_fn, code) for a verified brain-drawn scene, or (None, reason).
    `brief` adds the job on top of the rules: a closing, or a repair."""
    if os.environ.get("SCENE_AUTHOR", "on").lower() in ("0", "off", "false"):
        return None, "SCENE_AUTHOR=off"
    prompt = build_prompt(title, topic, say, pts, unit, brief)
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
        except Exception as e:  # noqa: BLE001 — refused or broken: tell it why
            problems = [f"{type(e).__name__}: {str(e)[:200]}"]
        if not problems:
            return fn, code
        why = "; ".join(problems[:4])
        log(f"[scene_author] attempt {k + 1} refused: {why}")
        prompt += ("\n\nYOUR PREVIOUS SCENE FAILED THESE CHECKS — fix every "
                   "one:\n- " + "\n- ".join(problems[:6]) + "\n\nPREVIOUS CODE:\n" + code)
    return None, why


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
    code = seg.get("illustrated_scene")
    if isinstance(code, str) and code.strip():
        try:
            return compile_scene(code)
        except Exception as e:  # noqa: BLE001 — a stale/edited scene is re-authored
            log(f"[scene_author] saved scene refused ({e}) — re-authoring")
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
            return compile_scene(code)
        except Exception as e:  # noqa: BLE001 — a stale/edited scene is re-authored
            log(f"[scene_author] saved scene refused ({e})")
    return None


HOOK_BRIEF = """THIS IS THE HOOK — the first ~3 seconds, before the story \
starts. Frame 1 must already state the story's surprise as ONE picture made \
of the subject: "{hook}". Open mid-action — the thing is already happening \
in the very first frame; no build-up, no title card. u runs 0..1 over those \
~3 seconds, so move FAST. The hook line is captioned below y=1650. It must \
not be the picture the first beat will show — it is the teaser for the \
whole story, the contrast at its heart.

"""

BRIEFS = {"hook": HOOK_BRIEF, "closing": CLOSING_BRIEF}
#: How long each kind of scene is on screen, for the dwell check (a hook is
#: ~3s of the cold open; a beat ~10s; a closing ~6s).
SCENE_SECS = {"hook": 3.0, "closing": 6.0, "beat": 10.0}


def saved_bookend(story_cfg: dict, kind: str, n_beats: int, log=print):
    """(scene, beat index) for the story's saved `kind` scene ("hook" or
    "closing"), re-checked through the sandbox, or None."""
    code = story_cfg.get(f"{kind}_scene")
    idx = story_cfg.get(f"{kind}_data", 0)
    if isinstance(code, str) and code.strip() and isinstance(idx, int) \
            and 0 <= idx < n_beats:
        try:
            return compile_scene(code), idx
        except Exception as e:  # noqa: BLE001
            log(f"[scene_author] saved {kind} refused ({e})")
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
