"""THE KIT LINT: a shot that builds its fire, smoke, lava, house, road, ground, water or sky BY HAND from spheres,
boxes and cylinders, or that makes something glow and casts no light from it, is refused before a frame renders
(2026-11-26).

The panel's most repeated hard defect is OFF THE LOOK, and in the lava short's twenty-six board rounds it was always
the same class of thing: a smoke of "clay balls", a fountain that was "a flat flame sprite" and "lights nothing",
"popcorn" bombs, a road that was one flat box, "Monopoly houses". Every one was written in the shot's own code as a
primitive named after the thing it stood for (a sphere called "lava bomb splat", a box called "street asphalt"). The
elements the panel accepted are in store/fx_kit.py. This reads a story's shots.py and says so first.

  HAND   a primitive (K.sph, K.box, K.cyl, K.capsule, or a sphere puff) whose name says it IS one of the kit's
         elements. The fix is the kit's element, named in the message.
  UNLIT  a shot whose own code makes something glow (an emission material, a fire or lava material) and creates no
         lamp at all: the glow is paint, it lights nothing. The fix is the kit's emitter (it brings its lamp) or
         FX.glow_light beside the glowing thing.
  OWN    the story defines its own builder for an element the kit has (def ...fire..., def ...house...). Binding only
         on stories written after the kit.
  scene_problems()  the same UNLIT question asked of the BUILT scene, by measurement: every glowing object that is not
         the kit's has a lamp near it.

It only ever ADDS a block. It has no say in a score and cannot pass a shot. Run by store/shots.py on the shot being
built (STAGING=strict fails it); stories written before the kit are named in BEFORE with the reason, and the test
fails when an entry is no longer needed, so the list only shrinks. tests/test_data3d_the_kit_not_by_hand.py.

usage: python fx_lint.py STORY [SHOT]
"""
import ast, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORIES = HERE.parent / "stories"

POSTED = {"checkout", "banana"}           # already on the channel (the same set store/boardlint.py exempts)
# written before the kit and not rebuilt on it; each says why and who fixes it
BEFORE = {
    "lava": "in work on 2026-11-26 by another session; its world.py is where the kit's elements were lifted from. Shots 1 and 2 "
            "(not yet passed) are flagged and should move to FX.lava_fountain / FX.embers / FX.road; binds once they do",
    "honey": "boarded before the kit; whoever takes it up again builds its yard, sky and smoke from the kit",
    "lightning": "posted 2026-11-23 and never built again",
}

GLOW_MIN = 0.5        # an emission weaker than this is a tint, not a light source
PRIMS = {"sph", "box", "cyl", "capsule", "cone"}                 # scene_kit's raw shapes
PUFFS = {"lw_puff", "lw_flame", "lw_billow"}                     # a sphere dressed as gas
# element word -> the kit's element that replaces it
ELEMENTS = [
    (r"lava bombs?|embers?|clots?|spatter", "FX.embers"),
    (r"lava fountains?|fire fountains?|fissure|eruption", "FX.lava_fountain"),
    (r"lava|magma|molten", "FX.lava_flow or FX.lava_pool"),
    (r"fire|fires|flames?|blaze", "FX.fire"),
    (r"smoke|soot|plume|ash cloud", "FX.smoke_column"),
    (r"steam|vapou?r", "FX.steam"),
    (r"dust", "FX.dust_puff"),
    (r"houses?|cottage|shack", "FX.house"),
    (r"sky|clouds?", "FX.sky"),
    (r"sea|ocean|lake|water", "FX.water"),
    (r"road|asphalt|tarmac|street", "FX.road"),
    (r"ground|lawn|grass|terrain|mountains?|hills?|field", "FX.ground"),
    (r"boulders?", "FX.rocks"),
]
# "fire hydrant" is not a fire: an element word followed by one of these names a different thing
NOT_THE_ELEMENT = {"hydrant", "hose", "extinguisher", "alarm", "engine", "truck", "escape", "door", "number", "sign", "tank", "bottle",
                   "can", "jug", "bucket", "cooler", "tower", "pipe", "main", "meter", "light", "lamp", "station", "plate", "rack",
                   "key", "keys", "mark", "line", "lines", "kerb", "barrier", "cone", "works", "worker", "map", "glass", "gauge", "mask",
                   "detector", "blanket", "axe", "helmet", "pit", "place", "wood", "log", "logs", "roller", "scraper", "bag", "pan",
                   "lamp", "lantern", "cover", "bar", "bowl", "basin", "column", "fountain", "bomb", "bombs", "jacket", "wheel", "pump", "tap", "trough", "butt", "level", "pole", "post"}
OWN_WORDS = {"fire", "flame", "flames", "smoke", "steam", "lava", "fountain", "embers", "house", "houses", "sky", "clouds", "asphalt"}
EMITS = re.compile(r"emit|fire|flame|lava_mat|glow_mat|neon")
LIGHTS = re.compile(r"point|area|light|lamp|spot|sun")


def _name(call):
    f = call.func
    if isinstance(f, ast.Attribute): return f.attr, (f.value.id if isinstance(f.value, ast.Name) else "")
    if isinstance(f, ast.Name): return f.id, ""
    return "", ""


def _text(node):
    """the fixed words of a name argument ("lava bomb splat", or an f-string's constant parts)"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
    if isinstance(node, ast.JoinedStr): return " ".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add): return (_text(node.left) + " " + _text(node.right)).strip()
    return ""


def element_of(name):
    """the kit element a thing's name says it is, or None ("fire hydrant" is no fire)"""
    low = re.sub(r"[^a-z ]+", " ", name.lower())
    for rx, fx in ELEMENTS:
        for m in re.finditer(rf"\b(?:{rx})\b", low):
            nxt = low[m.end():].split()
            if nxt and nxt[0] in NOT_THE_ELEMENT: continue
            return m.group(0), fx
    return None


def functions(src):
    return {n.name: n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}


def _refs(fn, names):
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id in names and n.id != fn.name}


def shot_scope(src, n):
    """the functions that are shot n's OWN: shot<n>, and every story function only it reaches (a helper two shots
    share is the story's world, judged by the OWN rule, not charged to one shot)"""
    fns = functions(src); names = set(fns)
    shots = sorted(k for k in fns if re.fullmatch(r"shot\d+", k))

    def reach(root):
        seen, todo = set(), [root]
        while todo:
            k = todo.pop()
            if k in seen or k not in fns: continue
            seen.add(k); todo += list(_refs(fns[k], names))
        return seen
    mine = reach(f"shot{n}")
    others = set().union(*[reach(s) for s in shots if s != f"shot{n}"]) if len(shots) > 1 else set()
    return [fns[k] for k in sorted(mine - others) if not re.fullmatch(r"shot\d+", k) or k == f"shot{n}"]


def _kit_alias(src):
    """the names this story calls the kit by (import fx_kit as FX)"""
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            out |= {a.asname or a.name for a in n.names if a.name == "fx_kit"}
    return out or {"FX", "fx_kit"}


def scope_problems(fns, kit=("FX", "fx_kit")):
    """HAND and UNLIT over a set of functions: [problem]"""
    out = []; emitters = []; lights = 0
    for fn in fns:
        for c in (x for x in ast.walk(fn) if isinstance(x, ast.Call)):
            name, mod = _name(c)
            if mod in kit:
                lights += 1 if _kit_emits(name) else 0     # the kit's emitters bring their lamp
                continue
            label = _text(c.args[0]) if c.args else ""
            if (name in PRIMS and mod) or name in PUFFS:
                hit = element_of(label)
                if hit:
                    out.append(f"HAND: {fn.name} line {c.lineno}: a {'sphere' if name in PUFFS | {'sph'} else name} named \"{label.strip()}\" stands in for "
                               f"{hit[0]}. The panel fails a hand-built one as OFF THE LOOK (a toy, a flat sprite, clay); build it with {hit[1]}")
            emit_kw = any(k.arg == "emit" and not (isinstance(k.value, ast.Constant) and isinstance(k.value.value, (int, float))
                                                  and k.value.value < GLOW_MIN) for k in c.keywords)
            if (EMITS.search(name) and not LIGHTS.search(name)) or (name == "mat" and emit_kw):
                emitters.append((fn.name, c.lineno, name, label.strip()))
            elif LIGHTS.search(name) and name not in ("lights_off",):
                lights += 1
            elif name == "new" and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Attribute) and c.func.value.attr == "lights":
                lights += 1
    if emitters and not lights:
        what = ", ".join(sorted({f"{nm}(\"{lb}\")" if lb else nm for _, _, nm, lb in emitters})[:5])
        out.append(f"UNLIT: {emitters[0][0]} makes things glow ({what}) and creates no lamp anywhere: the glow is paint and lights "
                   f"nothing near it (the panel: \"the fountain lights nothing\", \"pasted on\"). Use the kit's emitter, which brings "
                   f"its lamp, or put FX.glow_light beside each glowing thing")
    return out


def _kit_emits(name):
    try:
        import fx_kit
        return bool(fx_kit.REGISTRY.get(name, {}).get("emits"))
    except Exception:
        return name in ("fire", "house_fire", "glow_light", "lava_flow", "lava_pool", "embers", "lava_fountain", "sky")


def shot_problems(src, n):
    """what shot n's own code builds by hand or leaves unlit"""
    return scope_problems(shot_scope(src, n), kit=_kit_alias(src))


def own_problems(src):
    """the story's own builders of things the kit has"""
    out = []
    for name, fn in functions(src).items():
        words = set(name.lower().split("_")) & OWN_WORDS
        builds = any(_name(c)[0] in PRIMS | PUFFS | {"new"} for c in ast.walk(fn) if isinstance(c, ast.Call))
        if words and builds:
            out.append(f"OWN: the story defines {name}() (line {fn.lineno}), its own {sorted(words)[0]}: the kit has one the panel accepted "
                       f"(python store/fx_kit.py lists them). Call the kit's, or add what is missing TO the kit")
    return out


def problems(story, n, src=None):
    """[problem] for shot n of a story: its own code (HAND, UNLIT) and, for a story written after the kit, OWN"""
    src = src if src is not None else (STORIES / story / "shots.py").read_text()
    return shot_problems(src, n) + (own_problems(src) if held(story) else [])


def held(story):
    """True when the lint binds this story (not posted, not written before the kit)"""
    return story not in POSTED and story not in BEFORE


# ---------------------------------------------------------------- the built scene, measured
NEAR_MIN = 4.0        # metres: a lamp this near a small glowing thing lights what it would light
SCENE_GLOW = 1.0      # on the built scene only a real light source counts (a hi-vis stripe at 0.6 is a tint)


def _glows(mat):
    """how strongly a material emits: a number (its strength, or the constant a node-driven strength is multiplied by:
    a cooled lava crust at 0.6 is no light source), or True when its emission is driven by nodes with no such bound"""
    if mat is None or not getattr(mat, "use_nodes", False) or mat.node_tree is None: return 0.0
    best = 0.0
    for nd in mat.node_tree.nodes:
        inp = None
        if nd.type in ("BSDF_PRINCIPLED", "PRINCIPLED_VOLUME"): inp = nd.inputs.get("Emission Strength")
        elif nd.type == "EMISSION": inp = nd.inputs.get("Strength")
        if inp is None or not any(o.is_linked for o in nd.outputs): continue
        if inp.is_linked:                               # driven by nodes: a constant it is multiplied by bounds it
            src = inp.links[0].from_node
            consts = [float(i.default_value) for i in src.inputs[:2] if not i.is_linked] if src.type == "MATH" and src.operation == "MULTIPLY" else []
            if len(consts) != 1: return True
            best = max(best, consts[0]); continue
        best = max(best, float(inp.default_value))
    return best


def _moves(o):
    """True when the object's own place, or a parent's, is keyed"""
    while o is not None:
        ad = o.animation_data
        if ad and ad.action and any(c.data_path in ("location", "hide_render") for c in _fcurves(ad.action)): return True
        o = o.parent
    return False


def _fcurves(action):
    if hasattr(action, "fcurves"): return list(action.fcurves)
    return [fc for layer in action.layers for strip in layer.strips for cb in strip.channelbags for fc in cb.fcurves]


def scene_problems(objects, near=NEAR_MIN):
    """UNLIT, measured on the built scene: every visible object that glows and is not the kit's (no "fx" tag) has a
    lamp (not the sun) within three times its own size or `near` metres. A thing whose place is keyed (a clot in
    flight, a block that rises later) is not measured: where it is at one frame says nothing. Generous on purpose: the
    three lava shots that passed measure clean (2026-11-26), so what it reports is a glow with no light anywhere near.
    [problem], one per glowing material."""
    import bpy
    from mathutils import Vector
    bpy.context.view_layer.update()                  # a thing just built has no world matrix yet
    lamps = [o.matrix_world.translation.copy() for o in objects if o.type == 'LIGHT' and o.data.type != 'SUN']
    out = []; seen = set()
    for o in objects:
        if o.type not in ('MESH', 'FONT', 'CURVE') or o.get("fx") or o.hide_render or _moves(o): continue
        for slot in o.material_slots:
            g = _glows(slot.material)
            if not (g is True or g >= SCENE_GLOW) or slot.material.name in seen: continue
            pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
            ctr = sum(pts, Vector()) / 8; size = max((p - ctr).length for p in pts) * 2
            reach = max(near, 3.0 * size)
            if not any((l - ctr).length <= reach + size / 2 for l in lamps):
                seen.add(slot.material.name)
                out.append(f"UNLIT: \"{o.name}\" glows (material \"{slot.material.name}\") and no lamp stands within {reach:.1f} m of it: "
                           f"it lights nothing. Build it with the kit's emitter or put FX.glow_light beside it")
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    story = argv[1]; src = (STORIES / story / "shots.py").read_text()
    shots = sorted(int(k[4:]) for k in functions(src) if re.fullmatch(r"shot\d+", k))
    bad = 0
    for n in ([int(argv[2])] if len(argv) > 2 else shots):
        for p in shot_problems(src, n):
            bad += 1; print(f"FX {story} shot {n}: {p}")
    for p in own_problems(src):
        print(f"FX {story}: {p}" + ("" if held(story) else " (not binding: written before the kit)"))
    print(f"{story}: {bad} hand-built or unlit" + ("" if held(story) else f" (not binding: {'posted' if story in POSTED else BEFORE[story]})"))
    return 2 if bad and held(story) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
