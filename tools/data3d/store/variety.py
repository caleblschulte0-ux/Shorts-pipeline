"""BUILD FRESH, REUSE IS RARE (caaleb, 2026-11-18, of the card rewards short: "That was dog shit on so many levels. My
biggest issue is that it was lazy as shit. Sometimes you can reuse stuff. Like, reusing stuff should be like a wow,
crazy one-time and forever event, not we try to reuse everything as much as possible.")

What that video did, every beat: Data centred head-and-shoulders behind a counter, the same lens from the same height,
the same gold card prop (four of five beats), the same wooden counter, the store set twice, and Data WATCHING while
coins moved on their own. Five beats that were one shot. Every check passed it, because every check looked at one
shot at a time. This one looks ACROSS the beats, at three levels, and refuses the repeat before a frame renders:

  script   each beat's `staging` says its CAMERA (from CAMERAS), what DATA DOES (a verb, his body causing the change)
           and its PROPS. Two beats may not share a camera kind back to back, the short needs CAMERA_KINDS of them, no
           two beats share Data's act, Data may only WATCH (a passive verb) in PASSIVE_MAX beats, and a prop in two
           beats is a CALLBACK: named in `callbacks` with why, and a short gets CALLBACK_MAX of them.
  code     a kit or story builder (anything that puts a visible thing in the world) called in two shots' code is the
           same reuse in code, and needs the same callback entry under its own name.
  framing  measured on the storyboard stills (staging.framing): where his head sits, how big he is, which side of him
           the lens sees and from how high. Two beats whose framing is all within SAME of each other are the same
           shot, and the later one is redrawn.

It binds every story not in GRANDFATHERED (shorts made before the rule; they are not re-cut by it).
"""
import ast
import math

CAMERAS = {
    "close":        "a close-up: his face or the prop fills the frame",
    "medium":       "waist-up on Data with the prop beside him",
    "wide":         "the whole place, Data full-body inside it, the change big in the foreground",
    "low":          "the lens near the floor or the tabletop looking up at him or at the thing",
    "high":         "from above looking down on him and the thing",
    "overhead":     "straight down: a map of the table, the floor, the pile",
    "profile":      "side-on (the Crash Bandicoot staging): he and the thing in one line across the frame",
    "over_shoulder": "behind and beside him: what he sees, his shoulder in the near frame",
    "pov":          "his eyes: his hands come into the frame from the bottom",
    "tracking":     "the lens travels with him as he goes somewhere",
}
CAMERA_KINDS = 4         # of a five-beat short: at most one kind used twice, and never back to back
PASSIVE = {"watch", "watches", "look", "looks", "stand", "stands", "react", "reacts", "shrug", "shrugs", "nod", "nods",
           "wait", "waits", "stare", "stares", "sit", "sits", "observe", "observes", "frown", "frowns"}
PASSIVE_MAX = 1          # a beat where he only watches; every other beat his body does the thing (CLAUDE.md: Data is the CAUSE)
CALLBACK_MAX = 1         # "a wow, crazy one-time and forever event"

# code names that put nothing visible in the world (motion, timing, light, camera, the rig, the harness) or are raw
# geometry (a box, a cylinder: the bricks every new thing is built from, not a thing)
NON_VISUAL = {
    "ease", "ease_out", "ease_in", "ease_out_back", "lerp", "F", "follow", "reach", "sides", "path", "heap", "schedule",
    "camera", "camera_path", "soft_key", "load_data", "meshes", "place", "store_set", "build_set", "lob", "arc_into",
    "key_emission", "key_color", "gold", "pour", "tear_off", "spin", "spin_clock", "ring", "wilt", "close", "inflate",
    "shrivel", "frost", "frost_spread", "status", "needle_to", "level_pans", "string_between", "cold_smoke", "cure",
    "mat", "lin", "mute", "_mat", "_area", "sky_light", "mist", "contact_shadow", "seed_mesh", "bill_mesh",
    "Vector", "Euler", "Matrix", "range", "len", "min", "max", "abs", "round", "int", "float", "list", "dict", "zip",
    "box", "cyl", "sph", "empty", "text", "capsule", "bag", "_link", "_smooth", "img", "label_mat", "screen_mat", "strip_mat",
    "enumerate", "sorted", "print", "set", "tuple", "sum", "any", "all", "isinstance", "getattr", "hasattr",
}
KIT_ALIASES = {"CK", "SK", "VK", "HK", "PK", "LOC", "K", "props", "built", "checkout"}

SAME = dict(x=0.12, y=0.10, h=0.25, yaw=30.0, pitch=12.0)   # head centre x/y (frame fraction), height ratio, degrees

GRANDFATHERED = {"checkout", "banana", "saffron", "helium"}


def held(story):
    return story not in GRANDFATHERED


def _verb(s):
    w = (s or "").strip().lower().split()
    return w[0] if w else ""


def script_problems(script):
    """[(where, problem)] for a script's per-beat staging"""
    out = []
    n = len(script.get("lines", []))
    st = script.get("staging")
    if not isinstance(st, list) or len(st) != n:
        return [("staging", f"every beat needs a staging entry (camera, data, props): {n} beats, "
                            f"{len(st) if isinstance(st, list) else 0} entries")]
    cams = []
    for i, b in enumerate(st, 1):
        cam = b.get("camera")
        if cam not in CAMERAS:
            out.append((f"beat {i}", f"camera {cam!r} is not one of {sorted(CAMERAS)}"))
        cams.append(cam)
        if not _verb(b.get("data")):
            out.append((f"beat {i}", "say what DATA DOES (a verb first: 'cranks', 'shovels', 'drags')"))
        if not b.get("props"):
            out.append((f"beat {i}", "name the beat's own props"))
    for i, (a, b) in enumerate(zip(cams, cams[1:]), 1):
        if a == b:
            out.append((f"beats {i}-{i + 1}", f"the same camera ({a}) twice in a row: cut to a different shot"))
    kinds = len(set(cams))
    need = min(CAMERA_KINDS, n - 1) if n > 2 else n
    if kinds < need:
        out.append(("staging", f"{kinds} camera kinds over {n} beats; a short needs {need}"))
    verbs = [_verb(b.get("data")) for b in st]
    seen = {}
    for i, v in enumerate(verbs, 1):
        if v and v in seen:
            out.append((f"beat {i}", f"Data {v} again (beat {seen[v]}): give him a different act"))
        seen.setdefault(v, i)
    passive = [i for i, v in enumerate(verbs, 1) if v in PASSIVE]
    if len(passive) > PASSIVE_MAX:
        out.append(("staging", f"Data only watches in beats {passive}: in all but {PASSIVE_MAX} his body does the thing"))
    cb = script.get("callbacks") or {}
    if len(cb) > CALLBACK_MAX:
        out.append(("callbacks", f"{len(cb)} callbacks; a short gets {CALLBACK_MAX}. Build the rest new"))
    for k, why in cb.items():
        if not str(why).strip():
            out.append(("callbacks", f"{k}: a callback says why the repeat is the point"))
    where = {}
    for i, b in enumerate(st, 1):
        for p in b.get("props") or []:
            where.setdefault(str(p).strip().lower(), []).append(i)
    for p, beats in where.items():
        if len(beats) > 1 and p not in {k.lower() for k in cb}:
            out.append(("props", f"{p!r} is in beats {beats}: build each beat its own, or make it THE callback"))
    sets = script.get("sets") or []
    for s in sorted(set(sets)):
        k = sets.count(s)
        if k > 1 and f"set:{s}" not in cb:
            out.append(("sets", f"the {s} set is used in {k} beats: every beat its own place (or 'set:{s}' as the callback)"))
    return out


def _calls(fn):
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in KIT_ALIASES:
                if f.attr not in NON_VISUAL:
                    names.add(f"{f.value.id}.{f.attr}")
            elif isinstance(f, ast.Name) and f.id not in NON_VISUAL:
                names.add(f.id)
    return names


def code_problems(src, script):
    """[(where, problem)]: a visible builder called in two shots' code"""
    tree = ast.parse(src)
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    shots = {name: fn for name, fn in defs.items() if name.startswith("shot") and name[4:].isdigit()}
    local = {name for name in defs if name not in shots}

    def visible(name, fn_names, depth=0):
        """a local helper counts as a builder when its body calls a visible kit builder"""
        if "." in name: return True
        if name not in local or depth > 3: return False
        return any(visible(c, fn_names, depth + 1) for c in _calls(defs[name]) if c != name)

    cb = {k.lower() for k in (script.get("callbacks") or {})}
    used = {}
    for name, fn in sorted(shots.items(), key=lambda kv: int(kv[0][4:])):
        for c in _calls(fn):
            if c in shots: continue
            if "." in c or (c in local and visible(c, None)):
                used.setdefault(c, []).append(int(name[4:]))
    out = []
    for c, beats in sorted(used.items()):
        if len(beats) > 1 and c.lower() not in cb and c.split(".")[-1].lower() not in cb:
            out.append(("code", f"{c} builds something in shots {beats}: each beat builds its own (or name {c} as the callback)"))
    return out


def framing_problems(fr):
    """fr: {shot: {"x","y","h","yaw","pitch"}} from staging.framing on the storyboard stills.
    [(shot, problem)] for every later shot that is framed like an earlier one."""
    out = []
    ks = sorted(fr)
    for j, b in enumerate(ks):
        for a in ks[:j]:
            A, B = fr[a], fr[b]
            if None in (A.get("h"), B.get("h")) or min(A["h"], B["h"]) <= 0: continue
            if (abs(A["x"] - B["x"]) < SAME["x"] and abs(A["y"] - B["y"]) < SAME["y"]
                    and abs(math.log(A["h"] / B["h"])) < SAME["h"]
                    and abs(A["yaw"] - B["yaw"]) < SAME["yaw"] and abs(A["pitch"] - B["pitch"]) < SAME["pitch"]):
                out.append((b, f"framed like shot {a} (Data's head at {B['x']:.2f},{B['y']:.2f}, {B['h']:.2f} of the frame, "
                                f"seen {B['yaw']:.0f} deg round from {B['pitch']:.0f} deg up): move the lens, a different "
                                f"camera kind, Data somewhere else in the frame"))
                break
    return out
