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

#: The kit the brain may call — the reference's own vocabulary.
KIT_NAMES = ("vgrad", "glow", "text", "fit_readout", "by_time", "tree", "stump",
             "cow", "truck", "sack", "cup", "steam", "motes", "birds",
             "dawn_sky", "cafe", "rowhouse", "street", "traffic",
             "heat_shimmer", "shape_path", "stride", "clamp", "ease", "pop",
             "seg", "W", "H", "P", "_c", "scar_path", "SCAR", "FOREST_Y",
             "STREET_Y", "_TREES", "forest_floor", "FRANCE")
SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict)
                 else getattr(__builtins__, n)
                 for n in ("range", "len", "min", "max", "abs", "int", "float",
                           "str", "round", "enumerate", "zip", "sorted", "sum",
                           "list", "dict", "tuple", "isinstance", "reversed",
                           "any", "all", "bool", "divmod", "pow")}
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


def _num_ok(tok, allowed, vmax=100.0):
    try:
        x = float(tok.replace(",", ""))
    except ValueError:
        return True
    if x in (0.0, 25.0, 50.0, 75.0, 100.0) or _is_scale_mark(x, vmax):
        return True
    for a in allowed:
        for d in (0, 1, 2):
            if (round(a, d) == round(x, d) or round(a / 1000, d) == round(x, d)
                    or round(a / 1e6, d) == round(x, d)
                    or round(a / 1e9, d) == round(x, d)):
                return True
    return False


def verify(fn, pts, say: str = "") -> list[str]:
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

    def spy(cr, s, *a, **k):
        texts.append(str(s))
        return real(cr, s, *a, **k)

    def run(rows, u, record=True):
        cr = cairo.Context(surf)
        # Spy on the kit too: a number printed through fit_readout or any
        # other helper is still a number on screen.
        fn.__globals__["text"] = spy
        SS.text = spy
        try:
            fn(cr, 3.0 + u * 10, u, rows,
               lambda role, x, fy, h, pace=True: hosts.append((role, x, fy, h)))
        finally:
            fn.__globals__["text"] = real
            SS.text = real

    try:
        for u in (0.0, 0.5, 1.0):
            texts.clear()
            run(pts, u)
        final = list(texts)
    except Exception as e:  # noqa: BLE001
        return [f"crashed: {type(e).__name__}: {str(e)[:160]}"]
    if len(hosts) < 3:
        problems.append("Data is missing from a frame (host not called)")
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
    for s in final:
        for tok in re.findall(r"\d[\d,]*\.?\d*", s):
            if not _num_ok(tok, allowed, vmax):
                problems.append(f"prints {s!r}, a number the data does not have")
                break
    texts.clear()
    try:
        run(list(reversed(pts)), 1.0)
    except Exception as e:  # noqa: BLE001
        return problems + [f"crashed on reversed data: {e}"]
    if sorted(t for t in final if re.search(r"\d", t)) != \
            sorted(t for t in texts if re.search(r"\d", t)):
        problems.append("the numbers change when the data's order changes")
    px = []
    for f in range(24):
        cr = cairo.Context(surf)
        t = 12.0 + f / 24.0
        fn(cr, t, 0.9 + f / 240.0, pts,
           lambda role, x, fy, h, pace=True, _cr=cr, _f=f, _t=t: SS.place_host(
               _cr, role, (_f % 24) / 24.0, None, x, fy, h, _t, pace))
        surf.flush()
        im = Image.frombuffer("RGBA", (SS.W, SS.H), bytes(surf.get_data()),
                              "raw", "BGRA", 0, 1)
        px.append(list(im.convert("L").resize((192, 341)).getdata()))
    held = sum(sr._max_block_diff(x, y, 192) < sr.BLOCK_MOTION_THRESH
               for x, y in zip(px, px[1:])) / 23.0
    if held > 0.3:
        problems.append(f"its end holds still: {held:.0%} held frames at the gate's scale")
    return problems


# ------------------------------------------------------------------ the ask

_PROMPT = """You are drawing ONE beat of a vertical (1080x1920) YouTube Short about \
data, in the style of the operator's reference animation. Write a single Python \
function:

    def scene(cr, t, u, pts, host):

cr is a pycairo Context for the whole frame; t is seconds since the beat began; \
u is the beat's progress 0..1; pts is the beat's sourced data as [(label, value)]; \
host(role, x, foot_y, height, pace=True) draws the mascot Data standing with his \
feet at (x, foot_y). role is one of {roles}.

THE RULES — every one is checked by code before your scene is used:
1. The frame IS THE SUBJECT, never a chart. Draw the thing the story is about \
(the forest, the street, the scale, the ocean), and make the number a physical \
act made of it (trees falling one per 1,000 km², coins piling on a scale). No \
bars, axes, pie charts, bubble charts, or grids of one repeated icon.
2. Every number you print comes from pts, or is arithmetic on it (a \
difference, a share, a ratio). Never invent a quantity. Sort time data with \
by_time(rows) — never trust list order.
3. Fill the whole frame every frame: start with a full-height background \
(vgrad over 0..H or a kit backdrop). Captions are burned below y=1650; keep \
readouts between y=470 and y=1580 (the big readout: fit_readout(cr, big, small, \
80, 520, ...)).
4. Data ACTS inside the scene, tied to the number — he rides it, pours it, \
climbs it, carries it. Call host(...) every frame, height 180-240.
5. Nothing is ever still: keep something big moving through the whole beat \
(motes, birds, traffic, steam, falling items). Use stride(t) or pace=True so \
Data walks while he presents.
6. No imports; use only these names: {kit}, math, cairo, look, fit_size, \
INK, INK_2, WARN, and plain builtins. _c(rgb, alpha) makes a cairo colour. Colours: tuples (r, g, b) 0..255, or P[...] palette keys: \
{palette}.

THE KIT (signatures):
{sigs}

TWO TEACHER SCENES that pass every check — match this quality and style:
{teachers}

THIS BEAT:
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


def build_prompt(title, topic, say, pts, unit):
    teachers = "\n\n".join(inspect.getsource(f) for f in
                           (SS.amazon_where_it_goes, SS.coffee_drought))
    return _PROMPT.format(roles=", ".join(ROLES), kit=", ".join(KIT_NAMES),
                          palette=", ".join(sorted(SS.P)), sigs=_sigs(),
                          teachers=teachers, title=title, topic=topic, say=say,
                          pts=json.dumps(pts), unit=unit)


def _strip_fence(s: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", s, re.S)
    return m.group(1) if m else s


def ask_brain(prompt: str, model: str | None = None) -> str | None:
    if not shutil.which("claude"):
        return None
    model = model or os.environ.get("SCENE_AUTHOR_MODEL",
                                    os.environ.get("SHOWRUNNER_MODEL", "sonnet"))
    try:
        proc = subprocess.run(["claude", "-p", prompt, "--model", model,
                               "--output-format", "text"],
                              capture_output=True, text=True, timeout=TIMEOUT_S)
    except Exception:  # noqa: BLE001
        return None
    return _strip_fence(proc.stdout or "") if proc.returncode == 0 else None


def author(title, topic, say, pts, unit="", attempts=2, log=print):
    """(scene_fn, code) for a verified brain-drawn scene, or (None, reason)."""
    if os.environ.get("SCENE_AUTHOR", "on").lower() in ("0", "off", "false"):
        return None, "SCENE_AUTHOR=off"
    prompt = build_prompt(title, topic, say, pts, unit)
    why = "no brain"
    for k in range(attempts):
        code = ask_brain(prompt)
        if not code:
            return None, why
        try:
            fn = compile_scene(code)
            problems = verify(fn, pts, say)
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
                     log=log)
    if fn is None:
        log(f"[scene_author] no verified scene for beat {index}: {got}")
        return None
    seg["illustrated_scene"] = got
    return fn
